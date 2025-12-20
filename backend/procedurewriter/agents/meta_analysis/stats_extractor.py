"""Statistics extraction agent.

Extracts quantitative effect estimates (OR, RR, SMD) from study text
for use in meta-analysis.
"""
from __future__ import annotations

import json
import logging
import math
from typing import Literal

from pydantic import BaseModel, Field

from procedurewriter.agents.base import AgentResult, BaseAgent
from procedurewriter.agents.meta_analysis.models import StatisticalMetrics

logger = logging.getLogger(__name__)


class StatsExtractionInput(BaseModel):
    """Input for statistics extraction."""
    study_id: str
    title: str
    abstract: str
    outcome_of_interest: str


class RawStatsExtraction(BaseModel):
    """Raw extraction from LLM before calculation/validation."""
    outcome_found: bool = Field(..., description="Was the specific outcome found?")
    effect_size: float | None = None
    effect_type: Literal["OR", "RR", "HR", "MD", "SMD"] | None = None
    ci_lower: float | None = None
    ci_upper: float | None = None
    sample_size: int | None = None
    p_value: float | None = None
    reported_as_text: str | None = Field(None, description="Exact quote of the stats")


class StatisticsExtractorAgent(BaseAgent[StatsExtractionInput, StatisticalMetrics]):
    """Agent for extracting statistical results from text.

    Focuses on extracting the PRIMARY result for the requested outcome.
    Calculates variance from Confidence Intervals if not explicitly reported.
    """

    @property
    def name(self) -> str:
        return "stats_extractor"

    def execute(self, input_data: StatsExtractionInput) -> AgentResult[StatisticalMetrics]:
        """Extract statistics for the specific outcome."""
        
        # 1. LLM Extraction
        prompt = self._build_prompt(input_data)
        messages = [
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "user", "content": prompt},
        ]
        
        response = self.llm_call(messages, temperature=0.0)  # Zero temp for numbers
        raw = self._parse_response(response.content)

        # 2. Logic / Fallback / Calculation
        if not raw.outcome_found or raw.effect_size is None:
            logger.warning(f"No stats found for {input_data.study_id} outcome '{input_data.outcome_of_interest}'")
            # Return a "null" result that won't weight the analysis (variance=infinity effectively)
            # But models.py requires non-negative variance. 
            # We return a placeholder with extremely high variance (low weight).
            return AgentResult(
                output=StatisticalMetrics(
                    effect_size=1.0, # Null effect for OR/RR
                    effect_size_type="OR",
                    variance=100.0, # High variance = Low weight
                    confidence_interval_lower=0.1,
                    confidence_interval_upper=10.0,
                    weight=0.0
                ),
                stats=self._stats
            )

        # 3. Calculate Variance from CI
        # For ratio metrics (OR/RR/HR): use log scale
        # For difference metrics (MD/SMD): use linear scale
        # Formula: SE = (CI_upper - CI_lower) / 3.92, Variance = SE^2

        ci_lower = raw.ci_lower if raw.ci_lower is not None else raw.effect_size * 0.5
        ci_upper = raw.ci_upper if raw.ci_upper is not None else raw.effect_size * 2.0

        # Swap if flipped
        if ci_upper < ci_lower:
            ci_lower, ci_upper = ci_upper, ci_lower

        # Determine if ratio metric (requires log-scale calculation)
        is_ratio_metric = raw.effect_type in ("OR", "RR", "HR")

        if raw.ci_lower is not None and raw.ci_upper is not None:
            if is_ratio_metric:
                # Log-scale calculation for OR/RR/HR
                # CI is symmetric on log scale: log(OR) ± 1.96 * SE[log(OR)]
                # Therefore: SE[log(OR)] = (log(CI_upper) - log(CI_lower)) / 3.92
                if ci_lower > 0 and ci_upper > 0:
                    log_ci_lower = math.log(ci_lower)
                    log_ci_upper = math.log(ci_upper)
                    se_log = (log_ci_upper - log_ci_lower) / 3.92
                    variance = se_log ** 2
                else:
                    # CI contains zero or negative (invalid for ratio metrics)
                    logger.warning(f"Invalid CI for ratio metric: [{ci_lower}, {ci_upper}]")
                    variance = 1.0
            else:
                # Linear scale for MD/SMD
                se = (ci_upper - ci_lower) / 3.92
                variance = se ** 2
        else:
            # Fallback variance if no CI reported
            variance = 1.0 

        return AgentResult(
            output=StatisticalMetrics(
                effect_size=raw.effect_size,
                effect_size_type=raw.effect_type if raw.effect_type in ["OR", "RR", "SMD"] else "OR", # Default map
                variance=variance,
                confidence_interval_lower=ci_lower,
                confidence_interval_upper=ci_upper,
                weight=0.0 # To be calculated by synthesizer
            ),
            stats=self._stats
        )

    def _build_prompt(self, input_data: StatsExtractionInput) -> str:
        return f"""Study ID: {input_data.study_id}
Title: {input_data.title}
Abstract: {input_data.abstract}

---
TASK: Extract statistical results for the outcome: "{input_data.outcome_of_interest}"
If multiple timepoints exist, prefer the primary endpoint.
If multiple analysis types exist (Intention-to-treat vs Per-protocol), prefer ITT.
"""

    def _get_system_prompt(self) -> str:
        return """You are a statistical extraction engine for systematic reviews.
Your goal is to extract structured numerical data from clinical text.

Supported Metrics:
- OR (Odds Ratio)
- RR (Risk Ratio / Relative Risk)
- HR (Hazard Ratio) -> Map to RR if needed
- MD (Mean Difference) -> Map to SMD
- SMD (Standardized Mean Difference)

OUTPUT FORMAT (JSON):
{
    "outcome_found": true/false,
    "effect_size": 1.5,
    "effect_type": "OR",
    "ci_lower": 1.1,
    "ci_upper": 2.2,
    "sample_size": 150,
    "p_value": 0.04,
    "reported_as_text": "OR 1.5 (95% CI 1.1-2.2), p=0.04"
}

If the specific outcome is not found, set "outcome_found": false.
Do not hallucinate numbers. If CI is missing, return null.
Reply ONLY with valid JSON."""

    def _parse_response(self, content: str) -> RawStatsExtraction:
        try:
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()
            
            data = json.loads(content)
            return RawStatsExtraction(**data)
        except Exception as e:
            logger.error(f"Failed to parse stats extraction: {e}")
            return RawStatsExtraction(outcome_found=False)
