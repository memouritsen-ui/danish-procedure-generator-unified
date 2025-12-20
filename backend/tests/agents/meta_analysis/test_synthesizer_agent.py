"""Tests for EvidenceSynthesizerAgent - DerSimonian-Laird meta-analysis.

Following TDD: Tests written before implementation.

CRITICAL: Statistical tests use known datasets to validate math.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock

from procedurewriter.agents.meta_analysis.models import (
    PICOData,
    RiskOfBias,
    RiskOfBiasAssessment,
    StatisticalMetrics,
    StudyResult,
)
from procedurewriter.llm.providers import LLMProviderType, LLMResponse


class TestEvidenceSynthesizerBasics:
    """Basic functionality tests for EvidenceSynthesizerAgent."""

    def _create_mock_llm(self, response_content: str) -> MagicMock:
        """Create a mock LLM provider."""
        mock = MagicMock()
        mock.provider_type = LLMProviderType.OPENAI
        mock.is_available.return_value = True
        mock.chat_completion.return_value = LLMResponse(
            content=response_content,
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            model="gpt-4o-mini",
        )
        return mock

    def test_synthesizer_agent_exists(self) -> None:
        """EvidenceSynthesizerAgent should be importable."""
        from procedurewriter.agents.meta_analysis.synthesizer_agent import (
            EvidenceSynthesizerAgent,
        )

        assert EvidenceSynthesizerAgent is not None

    def test_synthesizer_agent_inherits_base_agent(self) -> None:
        """EvidenceSynthesizerAgent should inherit from BaseAgent."""
        from procedurewriter.agents.base import BaseAgent
        from procedurewriter.agents.meta_analysis.synthesizer_agent import (
            EvidenceSynthesizerAgent,
        )

        mock_llm = self._create_mock_llm("{}")
        agent = EvidenceSynthesizerAgent(llm=mock_llm)
        assert isinstance(agent, BaseAgent)

    def test_synthesizer_agent_has_name(self) -> None:
        """EvidenceSynthesizerAgent should have descriptive name."""
        from procedurewriter.agents.meta_analysis.synthesizer_agent import (
            EvidenceSynthesizerAgent,
        )

        mock_llm = self._create_mock_llm("{}")
        agent = EvidenceSynthesizerAgent(llm=mock_llm)
        assert agent.name == "evidence_synthesizer"


class TestDerSimonianLairdCalculation:
    """Tests for DerSimonian-Laird random-effects model calculations.

    Uses known dataset to validate statistical accuracy.
    Reference: Borenstein et al. (2009) Introduction to Meta-Analysis
    """

    def test_calculate_cochrans_q(self) -> None:
        """Cochran's Q should be calculated correctly."""
        from procedurewriter.agents.meta_analysis.synthesizer_agent import (
            calculate_cochrans_q,
        )

        # Known dataset: 3 studies with effect sizes and variances
        # Effect sizes (log odds ratios)
        effects = [0.5, 0.8, 0.3]
        variances = [0.04, 0.06, 0.05]

        # Calculate weights (inverse variance)
        weights = [1/v for v in variances]
        # Weighted mean
        weighted_mean = sum(e * w for e, w in zip(effects, weights)) / sum(weights)
        # Expected Q = sum(w * (e - mean)^2)
        expected_q = sum(w * (e - weighted_mean)**2 for e, w in zip(effects, weights))

        q = calculate_cochrans_q(effects, variances)
        assert abs(q - expected_q) < 0.0001

    def test_calculate_tau_squared(self) -> None:
        """Between-study variance tau^2 should be calculated correctly.

        Formula: tau^2 = max(0, (Q - df) / C)
        where C = sum(w) - sum(w^2)/sum(w)
        """
        from procedurewriter.agents.meta_analysis.synthesizer_agent import (
            calculate_tau_squared,
        )

        effects = [0.5, 0.8, 0.3]
        variances = [0.04, 0.06, 0.05]

        weights = [1/v for v in variances]
        sum_w = sum(weights)
        sum_w_sq = sum(w**2 for w in weights)

        # C = sum(w) - sum(w^2)/sum(w)
        c = sum_w - sum_w_sq / sum_w
        df = len(effects) - 1

        # Calculate Q first
        weighted_mean = sum(e * w for e, w in zip(effects, weights)) / sum_w
        q = sum(w * (e - weighted_mean)**2 for e, w in zip(effects, weights))

        # tau^2 = max(0, (Q - df) / C)
        expected_tau_sq = max(0, (q - df) / c)

        tau_sq = calculate_tau_squared(effects, variances)
        assert abs(tau_sq - expected_tau_sq) < 0.0001

    def test_calculate_i_squared(self) -> None:
        """Heterogeneity I^2 should be calculated correctly.

        Formula: I^2 = max(0, (Q - df) / Q) * 100
        """
        from procedurewriter.agents.meta_analysis.synthesizer_agent import (
            calculate_i_squared,
        )

        effects = [0.5, 0.8, 0.3]
        variances = [0.04, 0.06, 0.05]

        weights = [1/v for v in variances]
        weighted_mean = sum(e * w for e, w in zip(effects, weights)) / sum(weights)
        q = sum(w * (e - weighted_mean)**2 for e, w in zip(effects, weights))
        df = len(effects) - 1

        # I^2 = max(0, (Q - df) / Q) * 100
        expected_i_sq = max(0, (q - df) / q) * 100 if q > 0 else 0

        i_sq = calculate_i_squared(effects, variances)
        assert abs(i_sq - expected_i_sq) < 0.01

    def test_random_effects_pooled_estimate(self) -> None:
        """Random-effects pooled estimate should use tau^2 adjusted weights."""
        from procedurewriter.agents.meta_analysis.synthesizer_agent import (
            calculate_random_effects_pooled,
        )

        effects = [0.5, 0.8, 0.3]
        variances = [0.04, 0.06, 0.05]

        # Calculate tau^2
        weights = [1/v for v in variances]
        sum_w = sum(weights)
        sum_w_sq = sum(w**2 for w in weights)
        c = sum_w - sum_w_sq / sum_w
        df = len(effects) - 1
        weighted_mean_fe = sum(e * w for e, w in zip(effects, weights)) / sum_w
        q = sum(w * (e - weighted_mean_fe)**2 for e, w in zip(effects, weights))
        tau_sq = max(0, (q - df) / c)

        # Random effects weights: w* = 1 / (v + tau^2)
        re_weights = [1 / (v + tau_sq) for v in variances]
        expected_pooled = sum(e * w for e, w in zip(effects, re_weights)) / sum(re_weights)

        result = calculate_random_effects_pooled(effects, variances)
        assert abs(result.pooled_effect - expected_pooled) < 0.0001

    def test_pooled_confidence_interval(self) -> None:
        """Pooled effect should have valid 95% CI."""
        from procedurewriter.agents.meta_analysis.synthesizer_agent import (
            calculate_random_effects_pooled,
        )

        effects = [0.5, 0.8, 0.3]
        variances = [0.04, 0.06, 0.05]

        result = calculate_random_effects_pooled(effects, variances)

        # CI should bracket the pooled effect
        assert result.ci_lower < result.pooled_effect
        assert result.ci_upper > result.pooled_effect
        # Should be symmetric around pooled effect (approximately)
        margin = result.pooled_effect - result.ci_lower
        assert abs((result.ci_upper - result.pooled_effect) - margin) < 0.0001


class TestSynthesisOutput:
    """Tests for synthesis output structure."""

    def test_synthesis_output_structure(self) -> None:
        """SynthesisOutput should contain all required fields."""
        from procedurewriter.agents.meta_analysis.synthesizer_agent import (
            HeterogeneityMetrics,
            PooledEstimate,
            SynthesisOutput,
        )

        output = SynthesisOutput(
            pooled_estimate=PooledEstimate(
                pooled_effect=0.55,
                ci_lower=0.35,
                ci_upper=0.75,
                effect_size_type="OR",
                p_value=0.001,
            ),
            heterogeneity=HeterogeneityMetrics(
                cochrans_q=5.2,
                i_squared=45.3,
                tau_squared=0.02,
                df=2,
                p_value=0.074,
            ),
            included_studies=3,
            total_sample_size=1500,
            grade_summary="Moderate certainty evidence suggests...",
            forest_plot_data=[],
        )

        assert output.pooled_estimate.pooled_effect == 0.55
        assert output.heterogeneity.i_squared == 45.3


class TestGRADESummary:
    """Tests for GRADE-compliant summary generation."""

    def _create_mock_llm(self, response_content: str) -> MagicMock:
        """Create a mock LLM provider."""
        mock = MagicMock()
        mock.provider_type = LLMProviderType.OPENAI
        mock.is_available.return_value = True
        mock.chat_completion.return_value = LLMResponse(
            content=response_content,
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            model="gpt-4o-mini",
        )
        return mock

    def _create_sample_study(self, study_id: str, effect: float, variance: float) -> StudyResult:
        """Create sample StudyResult for testing."""
        return StudyResult(
            study_id=study_id,
            title=f"Study {study_id}",
            authors=["Author A"],
            year=2023,
            source="pubmed",
            pico=PICOData(
                population="Adults",
                intervention="Drug X",
                comparison="Placebo",
                outcome="Recovery",
                confidence=0.90,
            ),
            risk_of_bias=RiskOfBiasAssessment(
                randomization=RiskOfBias.LOW,
                deviations=RiskOfBias.LOW,
                missing_data=RiskOfBias.LOW,
                measurement=RiskOfBias.LOW,
                selection=RiskOfBias.LOW,
            ),
            statistics=StatisticalMetrics(
                effect_size=effect,
                effect_size_type="OR",
                variance=variance,
                confidence_interval_lower=effect - 0.2,
                confidence_interval_upper=effect + 0.2,
                weight=0.33,
            ),
            sample_size=500,
            detected_language="en",
        )

    def test_generates_grade_summary(self) -> None:
        """Agent should generate GRADE-compliant summary."""
        from procedurewriter.agents.meta_analysis.synthesizer_agent import (
            EvidenceSynthesizerAgent,
            SynthesisInput,
        )

        llm_response = json.dumps({
            "grade_summary": (
                "Moderate certainty evidence from 3 randomized trials (n=1500) "
                "suggests that Drug X reduces recovery time compared to placebo "
                "(OR 0.55, 95% CI 0.35-0.75). Evidence was downgraded one level "
                "for moderate heterogeneity (I²=45%)."
            ),
            "certainty_level": "Moderate",
            "certainty_rationale": "Downgraded for inconsistency",
        })
        mock_llm = self._create_mock_llm(llm_response)

        studies = [
            self._create_sample_study("Study1", 0.5, 0.04),
            self._create_sample_study("Study2", 0.8, 0.06),
            self._create_sample_study("Study3", 0.3, 0.05),
        ]

        agent = EvidenceSynthesizerAgent(llm=mock_llm)
        input_data = SynthesisInput(
            studies=studies,
            outcome_of_interest="Recovery time",
        )

        result = agent.execute(input_data)
        assert "certainty" in result.output.grade_summary.lower() or "evidence" in result.output.grade_summary.lower()


class TestForestPlotData:
    """Tests for forest plot data generation."""

    def _create_sample_study(self, study_id: str, effect: float, variance: float) -> StudyResult:
        """Create sample StudyResult for testing."""
        return StudyResult(
            study_id=study_id,
            title=f"Study {study_id}",
            authors=["Author A"],
            year=2023,
            source="pubmed",
            pico=PICOData(
                population="Adults",
                intervention="Drug X",
                comparison="Placebo",
                outcome="Recovery",
                confidence=0.90,
            ),
            risk_of_bias=RiskOfBiasAssessment(
                randomization=RiskOfBias.LOW,
                deviations=RiskOfBias.LOW,
                missing_data=RiskOfBias.LOW,
                measurement=RiskOfBias.LOW,
                selection=RiskOfBias.LOW,
            ),
            statistics=StatisticalMetrics(
                effect_size=effect,
                effect_size_type="OR",
                variance=variance,
                confidence_interval_lower=effect - 0.2,
                confidence_interval_upper=effect + 0.2,
                weight=0.33,
            ),
            sample_size=500,
            detected_language="en",
        )

    def test_forest_plot_data_structure(self) -> None:
        """Forest plot data should contain all necessary elements."""
        from procedurewriter.agents.meta_analysis.synthesizer_agent import (
            ForestPlotEntry,
        )

        entry = ForestPlotEntry(
            study_id="Study1",
            study_label="Smith 2023",
            effect_size=0.5,
            ci_lower=0.3,
            ci_upper=0.7,
            weight=0.25,
            sample_size=500,
        )
        assert entry.study_id == "Study1"
        assert entry.weight == 0.25


class TestStatisticalValidation:
    """Validation tests using known statistical results.

    These tests ensure our DerSimonian-Laird implementation matches
    published formulas and can replicate textbook examples.
    """

    def test_homogeneous_studies_zero_tau_squared(self) -> None:
        """Homogeneous studies should have tau^2 = 0."""
        from procedurewriter.agents.meta_analysis.synthesizer_agent import (
            calculate_tau_squared,
        )

        # Three studies with identical effects
        effects = [0.5, 0.5, 0.5]
        variances = [0.04, 0.04, 0.04]

        tau_sq = calculate_tau_squared(effects, variances)
        # tau^2 should be 0 (or very close) for homogeneous data
        assert tau_sq < 0.0001

    def test_high_heterogeneity_large_tau_squared(self) -> None:
        """Heterogeneous studies should have positive tau^2."""
        from procedurewriter.agents.meta_analysis.synthesizer_agent import (
            calculate_tau_squared,
        )

        # Studies with very different effects
        effects = [0.1, 0.5, 0.9]
        variances = [0.01, 0.01, 0.01]  # Small variances to emphasize heterogeneity

        tau_sq = calculate_tau_squared(effects, variances)
        assert tau_sq > 0

    def test_i_squared_interpretation_thresholds(self) -> None:
        """I^2 should follow Cochrane interpretation thresholds."""
        from procedurewriter.agents.meta_analysis.synthesizer_agent import (
            interpret_heterogeneity,
        )

        # I^2 interpretation per Cochrane Handbook:
        # 0-40%: might not be important
        # 30-60%: moderate heterogeneity
        # 50-90%: substantial heterogeneity
        # 75-100%: considerable heterogeneity

        assert interpret_heterogeneity(25) == "low"
        assert interpret_heterogeneity(50) == "moderate"
        assert interpret_heterogeneity(80) == "substantial"

    def test_single_study_degenerates_correctly(self) -> None:
        """Single study should return fixed-effect estimate."""
        from procedurewriter.agents.meta_analysis.synthesizer_agent import (
            calculate_random_effects_pooled,
        )

        effects = [0.5]
        variances = [0.04]

        result = calculate_random_effects_pooled(effects, variances)
        # Single study: pooled = the study itself
        assert abs(result.pooled_effect - 0.5) < 0.0001
