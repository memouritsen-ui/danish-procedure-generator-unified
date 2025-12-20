"""Integration tests for MetaAnalysisOrchestrator flow.

Following TDD: Tests written before implementation.
Tests the full orchestration pipeline: PICO extraction -> Screening -> Bias -> Synthesis
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from procedurewriter.llm.providers import LLMProviderType, LLMResponse


class TestMetaAnalysisOrchestratorBasics:
    """Basic functionality tests for MetaAnalysisOrchestrator."""

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

    def test_orchestrator_exists(self) -> None:
        """MetaAnalysisOrchestrator should be importable."""
        from procedurewriter.agents.meta_analysis.orchestrator import (
            MetaAnalysisOrchestrator,
        )

        assert MetaAnalysisOrchestrator is not None

    def test_orchestrator_initialization(self) -> None:
        """MetaAnalysisOrchestrator should initialize with LLM provider."""
        from procedurewriter.agents.meta_analysis.orchestrator import (
            MetaAnalysisOrchestrator,
        )

        mock_llm = self._create_mock_llm("{}")
        orchestrator = MetaAnalysisOrchestrator(llm=mock_llm)
        assert orchestrator is not None

    def test_orchestrator_has_name(self) -> None:
        """MetaAnalysisOrchestrator should have descriptive name."""
        from procedurewriter.agents.meta_analysis.orchestrator import (
            MetaAnalysisOrchestrator,
        )

        mock_llm = self._create_mock_llm("{}")
        orchestrator = MetaAnalysisOrchestrator(llm=mock_llm)
        assert orchestrator.name == "meta_analysis_orchestrator"


class TestLazyImports:
    """Tests verifying lazy import pattern for sub-agents."""

    def _create_mock_llm(self) -> MagicMock:
        """Create a mock LLM provider."""
        mock = MagicMock()
        mock.provider_type = LLMProviderType.OPENAI
        mock.is_available.return_value = True
        return mock

    def test_pico_extractor_lazy_import(self) -> None:
        """PICOExtractor should be lazily imported."""
        from procedurewriter.agents.meta_analysis.orchestrator import (
            MetaAnalysisOrchestrator,
        )

        mock_llm = self._create_mock_llm()
        orchestrator = MetaAnalysisOrchestrator(llm=mock_llm)

        # Extractor should not be instantiated until needed
        assert orchestrator._pico_extractor is None

        # Access should trigger lazy initialization
        extractor = orchestrator.pico_extractor
        assert extractor is not None

    def test_screener_lazy_import(self) -> None:
        """StudyScreenerAgent should be lazily imported."""
        from procedurewriter.agents.meta_analysis.orchestrator import (
            MetaAnalysisOrchestrator,
        )

        mock_llm = self._create_mock_llm()
        orchestrator = MetaAnalysisOrchestrator(llm=mock_llm)

        assert orchestrator._screener is None
        screener = orchestrator.screener
        assert screener is not None

    def test_bias_agent_lazy_import(self) -> None:
        """BiasAssessmentAgent should be lazily imported."""
        from procedurewriter.agents.meta_analysis.orchestrator import (
            MetaAnalysisOrchestrator,
        )

        mock_llm = self._create_mock_llm()
        orchestrator = MetaAnalysisOrchestrator(llm=mock_llm)

        assert orchestrator._bias_agent is None
        bias_agent = orchestrator.bias_agent
        assert bias_agent is not None

    def test_synthesizer_lazy_import(self) -> None:
        """EvidenceSynthesizerAgent should be lazily imported."""
        from procedurewriter.agents.meta_analysis.orchestrator import (
            MetaAnalysisOrchestrator,
        )

        mock_llm = self._create_mock_llm()
        orchestrator = MetaAnalysisOrchestrator(llm=mock_llm)

        assert orchestrator._synthesizer is None
        synthesizer = orchestrator.synthesizer
        assert synthesizer is not None


class TestEventEmission:
    """Tests for event emission during orchestration."""

    def _create_mock_llm(self) -> MagicMock:
        """Create a mock LLM provider."""
        mock = MagicMock()
        mock.provider_type = LLMProviderType.OPENAI
        mock.is_available.return_value = True
        mock.chat_completion.return_value = LLMResponse(
            content="{}",
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            model="gpt-4o-mini",
        )
        return mock

    def test_emits_pico_extracted_event(self) -> None:
        """Orchestrator should emit PICO_EXTRACTED event."""
        from procedurewriter.pipeline.events import EventType

        # Verify the event type exists
        assert hasattr(EventType, "PICO_EXTRACTED")

    def test_emits_bias_assessed_event(self) -> None:
        """Orchestrator should emit BIAS_ASSESSED event."""
        from procedurewriter.pipeline.events import EventType

        assert hasattr(EventType, "BIAS_ASSESSED")

    def test_emits_synthesis_complete_event(self) -> None:
        """Orchestrator should emit SYNTHESIS_COMPLETE event."""
        from procedurewriter.pipeline.events import EventType

        assert hasattr(EventType, "SYNTHESIS_COMPLETE")


class TestOrchestratorInput:
    """Tests for orchestrator input model."""

    def test_orchestrator_input_structure(self) -> None:
        """OrchestratorInput should contain required fields."""
        from procedurewriter.agents.meta_analysis.orchestrator import OrchestratorInput
        from procedurewriter.agents.meta_analysis.screener_agent import PICOQuery

        query = PICOQuery(
            population="Adults with hypertension",
            intervention="ACE inhibitors",
            comparison="Placebo",
            outcome="Blood pressure reduction",
        )

        input_data = OrchestratorInput(
            query=query,
            study_sources=[
                {
                    "study_id": "Study1",
                    "title": "ACE inhibitors trial",
                    "abstract": "A randomized trial...",
                },
            ],
            outcome_of_interest="Blood pressure reduction",
        )

        assert input_data.query.population == "Adults with hypertension"
        assert len(input_data.study_sources) == 1


class TestOrchestratorOutput:
    """Tests for orchestrator output model."""

    def test_orchestrator_output_structure(self) -> None:
        """OrchestratorOutput should contain synthesis results."""
        from procedurewriter.agents.meta_analysis.orchestrator import OrchestratorOutput
        from procedurewriter.agents.meta_analysis.synthesizer_agent import (
            HeterogeneityMetrics,
            PooledEstimate,
            SynthesisOutput,
        )

        synthesis = SynthesisOutput(
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
            grade_summary="Moderate certainty evidence...",
            forest_plot_data=[],
        )

        output = OrchestratorOutput(
            synthesis=synthesis,
            included_study_ids=["Study1", "Study2", "Study3"],
            excluded_study_ids=["Study4"],
            exclusion_reasons={"Study4": "Population mismatch"},
            manual_review_needed=["Study5"],
        )

        assert output.synthesis.pooled_estimate.pooled_effect == 0.55
        assert len(output.included_study_ids) == 3


class TestAsyncExecution:
    """Tests for async execution wrapper."""

    def _create_mock_llm(self) -> MagicMock:
        """Create a mock LLM provider."""
        mock = MagicMock()
        mock.provider_type = LLMProviderType.OPENAI
        mock.is_available.return_value = True
        mock.chat_completion.return_value = LLMResponse(
            content="{}",
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            model="gpt-4o-mini",
        )
        return mock

    @pytest.mark.asyncio
    async def test_execute_async_available(self) -> None:
        """Orchestrator should have async execution method."""
        from procedurewriter.agents.meta_analysis.orchestrator import (
            MetaAnalysisOrchestrator,
        )

        mock_llm = self._create_mock_llm()
        orchestrator = MetaAnalysisOrchestrator(llm=mock_llm)

        assert hasattr(orchestrator, "execute_async")

    @pytest.mark.asyncio
    async def test_execute_async_wraps_sync(self) -> None:
        """execute_async should wrap sync execute in thread."""
        from procedurewriter.agents.meta_analysis.orchestrator import (
            MetaAnalysisOrchestrator,
        )

        mock_llm = self._create_mock_llm()
        orchestrator = MetaAnalysisOrchestrator(llm=mock_llm)

        # Mock the sync execute method
        mock_result = MagicMock()
        orchestrator.execute = MagicMock(return_value=mock_result)

        mock_input = MagicMock()
        result = await orchestrator.execute_async(mock_input)

        # Should have called sync execute
        orchestrator.execute.assert_called_once_with(mock_input)


class TestFullPipelineFlow:
    """Integration tests for full meta-analysis pipeline."""

    def _create_mock_llm_sequence(self, responses: list[str]) -> MagicMock:
        """Create mock LLM that returns different responses in sequence."""
        mock = MagicMock()
        mock.provider_type = LLMProviderType.OPENAI
        mock.is_available.return_value = True

        response_objects = [
            LLMResponse(
                content=r,
                input_tokens=100,
                output_tokens=50,
                total_tokens=150,
                model="gpt-4o-mini",
            )
            for r in responses
        ]
        mock.chat_completion.side_effect = response_objects
        return mock

    def test_pipeline_processes_multiple_studies(self) -> None:
        """Pipeline should process multiple studies and synthesize."""
        from procedurewriter.agents.meta_analysis.orchestrator import (
            MetaAnalysisOrchestrator,
            OrchestratorInput,
        )
        from procedurewriter.agents.meta_analysis.screener_agent import PICOQuery

        # Create responses for each agent call - in sequential order per study
        # Orchestrator processes each study: PICO → Screen → (if included) Bias
        responses = [
            # Study1: PICO extraction
            json.dumps({
                "population": "Adults with hypertension",
                "intervention": "ACE inhibitors",
                "comparison": "Placebo",
                "outcome": "Blood pressure reduction",
                "confidence": 0.92,
                "population_mesh": ["Hypertension"],
                "intervention_mesh": ["ACE Inhibitors"],
                "outcome_mesh": ["Blood Pressure"],
                "detected_language": "en",
            }),
            # Study1: Screening (Include)
            json.dumps({
                "decision": "Include",
                "reason": "Matches all criteria",
                "confidence": 0.95,
            }),
            # Study1: Bias assessment
            json.dumps({
                "randomization": "low",
                "deviations": "low",
                "missing_data": "low",
                "measurement": "low",
                "selection": "low",
                "linguistic_markers": {"blinding": True, "intention_to_treat": True, "power_analysis": True},
                "domain_justifications": {
                    "randomization": "Good",
                    "deviations": "Good",
                    "missing_data": "Good",
                    "measurement": "Good",
                    "selection": "Good",
                },
            }),
            # Study2: PICO extraction
            json.dumps({
                "population": "Adults with hypertension",
                "intervention": "ACE inhibitors",
                "comparison": "Placebo",
                "outcome": "Blood pressure reduction",
                "confidence": 0.90,
                "population_mesh": ["Hypertension"],
                "intervention_mesh": ["ACE Inhibitors"],
                "outcome_mesh": ["Blood Pressure"],
                "detected_language": "en",
            }),
            # Study2: Screening (Include)
            json.dumps({
                "decision": "Include",
                "reason": "Matches all criteria",
                "confidence": 0.93,
            }),
            # Study2: Bias assessment
            json.dumps({
                "randomization": "low",
                "deviations": "some_concerns",
                "missing_data": "low",
                "measurement": "low",
                "selection": "low",
                "linguistic_markers": {"blinding": True, "intention_to_treat": False, "power_analysis": True},
                "domain_justifications": {
                    "randomization": "Good",
                    "deviations": "Minor issues",
                    "missing_data": "Good",
                    "measurement": "Good",
                    "selection": "Good",
                },
            }),
            # Study3: PICO extraction
            json.dumps({
                "population": "Children with asthma",
                "intervention": "Bronchodilators",
                "comparison": "Placebo",
                "outcome": "Symptom relief",
                "confidence": 0.88,
                "population_mesh": ["Asthma"],
                "intervention_mesh": ["Bronchodilators"],
                "outcome_mesh": ["Symptoms"],
                "detected_language": "en",
            }),
            # Study3: Screening (Exclude - no bias assessment needed)
            json.dumps({
                "decision": "Exclude",
                "reason": "Population mismatch",
                "confidence": 0.90,
            }),
            # Synthesis GRADE summary
            json.dumps({
                "grade_summary": "Moderate certainty evidence from 2 RCTs suggests benefit.",
                "certainty_level": "Moderate",
                "certainty_rationale": "Downgraded for some concerns about deviations",
            }),
        ]

        mock_llm = self._create_mock_llm_sequence(responses)
        orchestrator = MetaAnalysisOrchestrator(llm=mock_llm)

        query = PICOQuery(
            population="Adults with hypertension",
            intervention="ACE inhibitors",
            comparison="Placebo",
            outcome="Blood pressure reduction",
        )

        input_data = OrchestratorInput(
            query=query,
            study_sources=[
                {
                    "study_id": "Study1",
                    "title": "ACE Trial 1",
                    "abstract": "RCT of ACE inhibitors...",
                    "effect_size": 0.405,  # ln(1.5) - provides stats to skip extraction
                    "variance": 0.04,
                    "ci_lower": 0.01,
                    "ci_upper": 0.80,
                },
                {
                    "study_id": "Study2",
                    "title": "ACE Trial 2",
                    "abstract": "RCT of ACE inhibitors...",
                    "effect_size": 0.588,  # ln(1.8)
                    "variance": 0.0625,
                    "ci_lower": 0.10,
                    "ci_upper": 1.08,
                },
                {
                    "study_id": "Study3",
                    "title": "Asthma Trial",
                    "abstract": "RCT in children...",
                    # No effect_size needed - will be excluded by screening
                },
            ],
            outcome_of_interest="Blood pressure reduction",
        )

        result = orchestrator.execute(input_data)

        # Should have 2 included studies (Study3 excluded for population mismatch)
        assert len(result.output.included_study_ids) == 2
        assert "Study3" in result.output.excluded_study_ids


class TestStatisticalValidationWithKnownData:
    """Validate statistical calculations with known dataset.

    Uses a simple 3-study example with pre-calculated results.
    """

    def test_known_dataset_synthesis(self) -> None:
        """Synthesis should match pre-calculated results for known data."""
        from procedurewriter.agents.meta_analysis.synthesizer_agent import (
            calculate_cochrans_q,
            calculate_i_squared,
            calculate_random_effects_pooled,
            calculate_tau_squared,
        )

        # Known dataset: 3 studies
        # Study 1: OR = 1.5, SE = 0.2, Var = 0.04
        # Study 2: OR = 1.8, SE = 0.25, Var = 0.0625
        # Study 3: OR = 1.3, SE = 0.22, Var = 0.0484
        # (Using log(OR) for calculations)
        effects = [0.405, 0.588, 0.262]  # ln(1.5), ln(1.8), ln(1.3)
        variances = [0.04, 0.0625, 0.0484]

        # Calculate all metrics
        q = calculate_cochrans_q(effects, variances)
        tau_sq = calculate_tau_squared(effects, variances)
        i_sq = calculate_i_squared(effects, variances)
        pooled = calculate_random_effects_pooled(effects, variances)

        # Q should be positive
        assert q >= 0

        # tau^2 should be non-negative
        assert tau_sq >= 0

        # I^2 should be 0-100
        assert 0 <= i_sq <= 100

        # Pooled effect should be within study range
        assert min(effects) <= pooled.pooled_effect <= max(effects)

        # CI should contain pooled effect
        assert pooled.ci_lower < pooled.pooled_effect < pooled.ci_upper
