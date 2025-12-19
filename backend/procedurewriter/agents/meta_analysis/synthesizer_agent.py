"""Evidence synthesis agent implementing DerSimonian-Laird random-effects model.

Performs quantitative meta-analysis with heterogeneity assessment (I², Q, τ²)
and generates GRADE-compliant summary of findings.

Reference: DerSimonian R, Laird N. Meta-analysis in clinical trials.
Control Clin Trials. 1986;7(3):177-88.

Rectification: Implements deterministic GRADE logic (no LLM discretion) and
Hartung-Knapp adjustment for small k.
"""
from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field
from scipy import stats

from procedurewriter.agents.base import AgentResult, BaseAgent
from procedurewriter.agents.meta_analysis.models import StudyResult
from procedurewriter.llm.providers import LLMProvider

logger = logging.getLogger(__name__)


# =============================================================================
# Deterministic GRADE Logic (No LLM Discretion)
# =============================================================================


class GRADEDowngrade(str, Enum):
    """GRADE downgrade reasons per Cochrane guidelines."""

    RISK_OF_BIAS = "risk_of_bias"
    INCONSISTENCY = "inconsistency"
    IMPRECISION = "imprecision"
    INDIRECTNESS = "indirectness"
    PUBLICATION_BIAS = "publication_bias"


@dataclass
class GRADEResult:
    """Deterministic GRADE certainty calculation result."""

    certainty_level: Literal["High", "Moderate", "Low", "Very Low"]
    downgrades: list[GRADEDowngrade] = field(default_factory=list)
    downgrade_reasons: dict[str, str] = field(default_factory=dict)


def calculate_deterministic_grade(
    i_squared: float,
    high_risk_proportion: float,
    n_studies: int,
) -> GRADEResult:
    """Calculate GRADE certainty deterministically without LLM.

    Implements hard-coded GRADE downgrade rules per Censor's Report:
    - I² > 50% → Downgrade for Inconsistency
    - >25% high RoB studies → Downgrade for Risk of Bias
    - k < 5 studies → Downgrade for Imprecision

    Args:
        i_squared: I² heterogeneity percentage (0-100).
        high_risk_proportion: Proportion of studies with high RoB (0-1).
        n_studies: Number of studies included (k).

    Returns:
        GRADEResult with certainty level and downgrade reasons.
    """
    downgrades: list[GRADEDowngrade] = []
    reasons: dict[str, str] = {}

    # Rule 1: I² > 50% → Inconsistency
    if i_squared > 50.0:
        downgrades.append(GRADEDowngrade.INCONSISTENCY)
        reasons["inconsistency"] = f"I² > 50% ({i_squared:.1f}%): substantial heterogeneity"

    # Rule 2: >25% high RoB → Risk of Bias
    if high_risk_proportion > 0.25:
        downgrades.append(GRADEDowngrade.RISK_OF_BIAS)
        reasons["risk_of_bias"] = f">25% studies with high risk of bias ({high_risk_proportion * 100:.0f}%)"

    # Rule 3: k < 5 → Imprecision
    if n_studies < 5:
        downgrades.append(GRADEDowngrade.IMPRECISION)
        reasons["imprecision"] = f"k < 5 studies ({n_studies}): insufficient precision"

    # Determine certainty level based on downgrade count
    n_downgrades = len(downgrades)
    if n_downgrades == 0:
        certainty = "High"
    elif n_downgrades == 1:
        certainty = "Moderate"
    elif n_downgrades == 2:
        certainty = "Low"
    else:
        certainty = "Very Low"

    return GRADEResult(
        certainty_level=certainty,
        downgrades=downgrades,
        downgrade_reasons=reasons,
    )


# =============================================================================
# Hartung-Knapp Adjustment for Small k
# =============================================================================


def get_t_critical_value(df: int, alpha: float = 0.05) -> float:
    """Get t-distribution critical value for Hartung-Knapp adjustment.

    Args:
        df: Degrees of freedom (k - 1).
        alpha: Significance level (default 0.05 for 95% CI).

    Returns:
        t critical value for two-tailed test.
    """
    if df <= 0:
        return 1.96  # Fallback to z for degenerate case
    return stats.t.ppf(1 - alpha / 2, df)


def calculate_random_effects_pooled_hk(
    effects: list[float], variances: list[float]
) -> "PooledEstimate":
    """Calculate random-effects pooled estimate with Hartung-Knapp adjustment.

    Uses t-distribution instead of z=1.96 when k < 5 for wider, more
    conservative confidence intervals.

    Reference: Hartung J, Knapp G. A refined method for the meta-analysis
    of controlled clinical trials with binary outcome. Stat Med. 2001.

    Args:
        effects: List of effect sizes.
        variances: List of within-study variances.

    Returns:
        PooledEstimate with Hartung-Knapp adjusted CI.
    """
    k = len(effects)

    if k == 0:
        return PooledEstimate(
            pooled_effect=0.0,
            ci_lower=0.0,
            ci_upper=0.0,
            effect_size_type="OR",
            p_value=1.0,
        )

    if k == 1:
        se = math.sqrt(variances[0])
        ci_lower = effects[0] - 1.96 * se
        ci_upper = effects[0] + 1.96 * se
        z = effects[0] / se if se > 0 else 0
        p_value = 2 * (1 - stats.norm.cdf(abs(z)))
        return PooledEstimate(
            pooled_effect=effects[0],
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            effect_size_type="OR",
            p_value=p_value,
            se=se,
        )

    # Calculate τ²
    tau_sq = calculate_tau_squared(effects, variances)

    # Random-effects weights
    re_weights = [1.0 / (v + tau_sq) for v in variances]
    sum_re_weights = sum(re_weights)

    # Pooled effect
    pooled_effect = sum(e * w for e, w in zip(effects, re_weights)) / sum_re_weights

    # Standard error of pooled effect
    pooled_variance = 1.0 / sum_re_weights
    pooled_se = math.sqrt(pooled_variance)

    # Hartung-Knapp adjustment: use t-distribution when k < 5
    df = k - 1
    if k < 5:
        # Use t-distribution for wider CI
        t_crit = get_t_critical_value(df, alpha=0.05)

        # Hartung-Knapp variance adjustment
        # q* = Σ w_i * (θ_i - θ̂)² / (k - 1)
        q_star = sum(
            w * (e - pooled_effect) ** 2
            for e, w in zip(effects, re_weights)
        ) / df if df > 0 else 1.0

        # Adjusted SE
        hk_se = pooled_se * math.sqrt(max(1.0, q_star))

        ci_lower = pooled_effect - t_crit * hk_se
        ci_upper = pooled_effect + t_crit * hk_se

        # P-value using t-distribution
        t_stat = pooled_effect / hk_se if hk_se > 0 else 0
        p_value = 2 * (1 - stats.t.cdf(abs(t_stat), df))
    else:
        # Standard z-based CI for k >= 5
        ci_lower = pooled_effect - 1.96 * pooled_se
        ci_upper = pooled_effect + 1.96 * pooled_se
        z = pooled_effect / pooled_se if pooled_se > 0 else 0
        p_value = 2 * (1 - stats.norm.cdf(abs(z)))

    return PooledEstimate(
        pooled_effect=pooled_effect,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        effect_size_type="OR",
        p_value=p_value,
        se=pooled_se,
    )


# =============================================================================
# Statistical Functions for DerSimonian-Laird Random-Effects Model
# =============================================================================


def calculate_cochrans_q(effects: list[float], variances: list[float]) -> float:
    """Calculate Cochran's Q statistic for heterogeneity.

    Q = Σ w_i * (θ_i - θ̄)²

    where w_i = 1/v_i (inverse variance weight)
    and θ̄ = weighted mean effect

    Args:
        effects: List of effect sizes (e.g., log odds ratios).
        variances: List of within-study variances.

    Returns:
        Cochran's Q statistic.
    """
    if len(effects) < 2:
        return 0.0

    weights = [1.0 / v for v in variances]
    sum_weights = sum(weights)
    weighted_mean = sum(e * w for e, w in zip(effects, weights)) / sum_weights

    q = sum(w * (e - weighted_mean) ** 2 for e, w in zip(effects, weights))
    return q


def calculate_tau_squared(effects: list[float], variances: list[float]) -> float:
    """Calculate between-study variance (τ²) using DerSimonian-Laird method.

    τ² = max(0, (Q - df) / C)

    where:
    - Q = Cochran's Q statistic
    - df = k - 1 (degrees of freedom)
    - C = Σw_i - Σw_i² / Σw_i (scaling factor)

    Args:
        effects: List of effect sizes.
        variances: List of within-study variances.

    Returns:
        Between-study variance τ².
    """
    if len(effects) < 2:
        return 0.0

    weights = [1.0 / v for v in variances]
    sum_w = sum(weights)
    sum_w_sq = sum(w ** 2 for w in weights)

    # Scaling factor C
    c = sum_w - sum_w_sq / sum_w

    # Degrees of freedom
    df = len(effects) - 1

    # Cochran's Q
    q = calculate_cochrans_q(effects, variances)

    # τ² = max(0, (Q - df) / C)
    tau_sq = max(0.0, (q - df) / c) if c > 0 else 0.0

    return tau_sq


def calculate_i_squared(effects: list[float], variances: list[float]) -> float:
    """Calculate I² heterogeneity statistic.

    I² = max(0, (Q - df) / Q) × 100

    Interpretation (per Cochrane Handbook):
    - 0-40%: might not be important
    - 30-60%: moderate heterogeneity
    - 50-90%: substantial heterogeneity
    - 75-100%: considerable heterogeneity

    Args:
        effects: List of effect sizes.
        variances: List of within-study variances.

    Returns:
        I² as percentage (0-100).
    """
    if len(effects) < 2:
        return 0.0

    q = calculate_cochrans_q(effects, variances)
    df = len(effects) - 1

    if q <= 0:
        return 0.0

    i_sq = max(0.0, (q - df) / q) * 100
    return i_sq


def interpret_heterogeneity(i_squared: float) -> str:
    """Interpret I² heterogeneity per Cochrane guidelines.

    Args:
        i_squared: I² percentage (0-100).

    Returns:
        Interpretation string: "low", "moderate", or "substantial".
    """
    if i_squared < 40:
        return "low"
    elif i_squared < 75:
        return "moderate"
    else:
        return "substantial"


class PooledEstimate(BaseModel):
    """Random-effects pooled estimate with confidence interval."""
    pooled_effect: float
    ci_lower: float
    ci_upper: float
    effect_size_type: Literal["OR", "RR", "SMD"]
    p_value: float
    se: float = 0.0


def calculate_random_effects_pooled(
    effects: list[float], variances: list[float]
) -> PooledEstimate:
    """Calculate random-effects pooled estimate using DerSimonian-Laird.

    Uses random-effects weights: w*_i = 1 / (v_i + τ²)

    Args:
        effects: List of effect sizes.
        variances: List of within-study variances.

    Returns:
        PooledEstimate with pooled effect and 95% CI.
    """
    if len(effects) == 0:
        return PooledEstimate(
            pooled_effect=0.0,
            ci_lower=0.0,
            ci_upper=0.0,
            effect_size_type="OR",
            p_value=1.0,
        )

    if len(effects) == 1:
        # Single study: fixed-effect estimate
        se = math.sqrt(variances[0])
        ci_lower = effects[0] - 1.96 * se
        ci_upper = effects[0] + 1.96 * se
        z = effects[0] / se if se > 0 else 0
        p_value = 2 * (1 - stats.norm.cdf(abs(z)))
        return PooledEstimate(
            pooled_effect=effects[0],
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            effect_size_type="OR",
            p_value=p_value,
            se=se,
        )

    # Calculate τ²
    tau_sq = calculate_tau_squared(effects, variances)

    # Random-effects weights: w*_i = 1 / (v_i + τ²)
    re_weights = [1.0 / (v + tau_sq) for v in variances]
    sum_re_weights = sum(re_weights)

    # Pooled effect
    pooled_effect = sum(e * w for e, w in zip(effects, re_weights)) / sum_re_weights

    # Variance of pooled effect
    pooled_variance = 1.0 / sum_re_weights
    pooled_se = math.sqrt(pooled_variance)

    # 95% CI (using z = 1.96)
    ci_lower = pooled_effect - 1.96 * pooled_se
    ci_upper = pooled_effect + 1.96 * pooled_se

    # P-value (two-tailed z-test)
    z = pooled_effect / pooled_se if pooled_se > 0 else 0
    p_value = 2 * (1 - stats.norm.cdf(abs(z)))

    return PooledEstimate(
        pooled_effect=pooled_effect,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        effect_size_type="OR",
        p_value=p_value,
        se=pooled_se,
    )


# =============================================================================
# Data Models
# =============================================================================


class HeterogeneityMetrics(BaseModel):
    """Heterogeneity statistics for meta-analysis."""
    cochrans_q: float
    i_squared: float = Field(..., ge=0, le=100)
    tau_squared: float = Field(..., ge=0)
    df: int = Field(..., ge=0)
    p_value: float = Field(..., ge=0, le=1)
    interpretation: str = ""


class ForestPlotEntry(BaseModel):
    """Data for a single study in forest plot."""
    study_id: str
    study_label: str
    effect_size: float
    ci_lower: float
    ci_upper: float
    weight: float
    sample_size: int


class SynthesisOutput(BaseModel):
    """Complete output from evidence synthesis."""
    pooled_estimate: PooledEstimate
    heterogeneity: HeterogeneityMetrics
    included_studies: int
    total_sample_size: int
    grade_summary: str
    certainty_level: Literal["High", "Moderate", "Low", "Very Low"] = "Moderate"
    forest_plot_data: list[ForestPlotEntry]


class SynthesisInput(BaseModel):
    """Input for evidence synthesis."""
    studies: list[StudyResult]
    outcome_of_interest: str


# =============================================================================
# Evidence Synthesizer Agent
# =============================================================================


class EvidenceSynthesizerAgent(BaseAgent[SynthesisInput, SynthesisOutput]):
    """Agent for quantitative evidence synthesis.

    Implements DerSimonian-Laird random-effects model for pooling effect
    estimates across studies. Generates GRADE-compliant summary.

    Statistical Methods:
    - Cochran's Q for heterogeneity testing
    - I² for heterogeneity quantification
    - τ² for between-study variance
    - Random-effects pooled estimate with 95% CI
    """

    def __init__(
        self,
        llm: LLMProvider,
        model: str | None = None,
    ) -> None:
        """Initialize synthesizer agent.

        Args:
            llm: LLM provider for GRADE summary generation.
            model: Model name override.
        """
        super().__init__(llm, model)

    @property
    def name(self) -> str:
        return "evidence_synthesizer"

    def execute(self, input_data: SynthesisInput) -> AgentResult[SynthesisOutput]:
        """Synthesize evidence from included studies.

        Args:
            input_data: Studies to synthesize.

        Returns:
            AgentResult containing SynthesisOutput with pooled estimate.
        """
        studies = input_data.studies

        if not studies:
            return AgentResult(
                output=SynthesisOutput(
                    pooled_estimate=PooledEstimate(
                        pooled_effect=0.0,
                        ci_lower=0.0,
                        ci_upper=0.0,
                        effect_size_type="OR",
                        p_value=1.0,
                    ),
                    heterogeneity=HeterogeneityMetrics(
                        cochrans_q=0.0,
                        i_squared=0.0,
                        tau_squared=0.0,
                        df=0,
                        p_value=1.0,
                        interpretation="low",
                    ),
                    included_studies=0,
                    total_sample_size=0,
                    grade_summary="No studies available for synthesis.",
                    forest_plot_data=[],
                ),
                stats=self._stats,
            )

        # Extract effect sizes and variances
        effects = [s.statistics.effect_size for s in studies]
        variances = [s.statistics.variance for s in studies]
        k = len(studies)

        # Calculate statistics with Hartung-Knapp adjustment for small k
        if k < 5:
            pooled = calculate_random_effects_pooled_hk(effects, variances)
        else:
            pooled = calculate_random_effects_pooled(effects, variances)
        pooled.effect_size_type = studies[0].statistics.effect_size_type

        q = calculate_cochrans_q(effects, variances)
        tau_sq = calculate_tau_squared(effects, variances)
        i_sq = calculate_i_squared(effects, variances)
        df = k - 1

        # Q test p-value (chi-squared with df degrees of freedom)
        q_p_value = 1 - stats.chi2.cdf(q, df) if df > 0 else 1.0

        heterogeneity = HeterogeneityMetrics(
            cochrans_q=q,
            i_squared=i_sq,
            tau_squared=tau_sq,
            df=df,
            p_value=q_p_value,
            interpretation=interpret_heterogeneity(i_sq),
        )

        # Calculate study weights for forest plot
        re_weights = [1.0 / (v + tau_sq) for v in variances]
        total_weight = sum(re_weights)
        normalized_weights = [w / total_weight for w in re_weights]

        forest_plot_data = [
            ForestPlotEntry(
                study_id=s.study_id,
                study_label=f"{s.authors[0] if s.authors else 'Unknown'} {s.year}",
                effect_size=s.statistics.effect_size,
                ci_lower=s.statistics.confidence_interval_lower,
                ci_upper=s.statistics.confidence_interval_upper,
                weight=w,
                sample_size=s.sample_size,
            )
            for s, w in zip(studies, normalized_weights)
        ]

        total_sample_size = sum(s.sample_size for s in studies)

        # Calculate Risk of Bias proportion for deterministic GRADE
        high_risk_count = sum(
            1 for s in studies if s.risk_of_bias.overall.value == "high"
        )
        high_risk_proportion = high_risk_count / k if k > 0 else 0.0

        # DETERMINISTIC GRADE: No LLM discretion
        grade_result = calculate_deterministic_grade(
            i_squared=i_sq,
            high_risk_proportion=high_risk_proportion,
            n_studies=k,
        )

        # Generate human-readable summary (still uses LLM for prose, but
        # certainty level is locked to deterministic calculation)
        grade_summary = self._generate_grade_summary(
            input_data.outcome_of_interest,
            pooled,
            heterogeneity,
            k,
            total_sample_size,
            studies,
            grade_result,  # Pass deterministic result
        )

        output = SynthesisOutput(
            pooled_estimate=pooled,
            heterogeneity=heterogeneity,
            included_studies=k,
            total_sample_size=total_sample_size,
            grade_summary=grade_summary,
            certainty_level=grade_result.certainty_level,
            forest_plot_data=forest_plot_data,
        )

        return AgentResult(
            output=output,
            stats=self._stats,
        )

    def _generate_grade_summary(
        self,
        outcome: str,
        pooled: PooledEstimate,
        heterogeneity: HeterogeneityMetrics,
        n_studies: int,
        total_n: int,
        studies: list[StudyResult],
        grade_result: GRADEResult | None = None,
    ) -> str:
        """Generate GRADE-compliant summary using deterministic logic.

        The certainty level is determined by calculate_deterministic_grade()
        with NO LLM discretion. The LLM is only used for prose generation.

        Args:
            outcome: Outcome of interest.
            pooled: Pooled estimate result.
            heterogeneity: Heterogeneity metrics.
            n_studies: Number of studies.
            total_n: Total sample size.
            studies: List of included studies.
            grade_result: Deterministic GRADE result (certainty locked).
        """
        # Count risk of bias levels
        high_risk = sum(
            1 for s in studies if s.risk_of_bias.overall.value == "high"
        )
        some_concerns = sum(
            1 for s in studies if s.risk_of_bias.overall.value == "some_concerns"
        )

        # Use deterministic certainty if provided
        certainty = grade_result.certainty_level if grade_result else "Moderate"
        downgrades = grade_result.downgrade_reasons if grade_result else {}

        # Format downgrade reasons for prompt
        downgrade_text = "\n".join(f"- {reason}" for reason in downgrades.values()) if downgrades else "None"

        prompt = f"""Generate a GRADE-compliant summary of findings for this meta-analysis.

OUTCOME: {outcome}

RESULTS:
- Pooled Effect ({pooled.effect_size_type}): {pooled.pooled_effect:.2f}
- 95% CI: [{pooled.ci_lower:.2f}, {pooled.ci_upper:.2f}]
- P-value: {pooled.p_value:.4f}

HETEROGENEITY:
- I²: {heterogeneity.i_squared:.1f}% ({heterogeneity.interpretation})
- Cochran's Q: {heterogeneity.cochrans_q:.2f}, p={heterogeneity.p_value:.3f}

EVIDENCE BASE:
- Number of studies: {n_studies}
- Total participants: {total_n}
- Risk of bias: {high_risk} high risk, {some_concerns} some concerns

CERTAINTY LEVEL (DETERMINISTIC - DO NOT CHANGE): {certainty}
DOWNGRADE REASONS:
{downgrade_text}

Write a 2-3 sentence summary that includes the certainty level "{certainty}" and explains the downgrades.
The certainty level is pre-determined and MUST NOT be changed."""

        messages = [
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "user", "content": prompt},
        ]

        response = self.llm_call(messages, temperature=0.2)

        try:
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            data = json.loads(content)
            return data.get("grade_summary", content)
        except json.JSONDecodeError:
            return response.content.strip()

    def _get_system_prompt(self) -> str:
        """System prompt for GRADE summary generation."""
        return """You are an expert systematic review methodologist specializing in GRADE assessments.

Generate GRADE-compliant summaries of findings for meta-analyses.

GRADE CERTAINTY LEVELS:
- HIGH: Further research very unlikely to change confidence in estimate
- MODERATE: Further research likely to have important impact
- LOW: Further research very likely to have important impact
- VERY LOW: Any estimate is very uncertain

DOWNGRADING REASONS:
1. Risk of bias (many studies with high risk)
2. Inconsistency (high heterogeneity, I² > 75%)
3. Indirectness (population/intervention differences)
4. Imprecision (wide CI, crosses clinical threshold)
5. Publication bias (funnel plot asymmetry, few studies)

OUTPUT FORMAT (JSON):
{
    "grade_summary": "2-3 sentence summary with certainty level",
    "certainty_level": "High" | "Moderate" | "Low" | "Very Low",
    "certainty_rationale": "Brief explanation of rating"
}

Respond ONLY with valid JSON."""
