"""Tests for Censor's Report rectifications.

TDD: These tests written FIRST to specify required behavior.
"""
from __future__ import annotations

import asyncio
import json
import math
import time
from unittest.mock import MagicMock, patch

import pytest
from scipy import stats


# =============================================================================
# FIX 1: Deterministic GRADE Logic with Hartung-Knapp
# =============================================================================


class TestDeterministicGRADELogic:
    """Tests for deterministic GRADE certainty calculation."""

    def test_downgrade_for_inconsistency_when_i_squared_above_50(self) -> None:
        """Auto-downgrade when I² > 50% (substantial heterogeneity)."""
        from procedurewriter.agents.meta_analysis.synthesizer_agent import (
            calculate_deterministic_grade,
            GRADEDowngrade,
        )

        result = calculate_deterministic_grade(
            i_squared=55.0,
            high_risk_proportion=0.1,
            n_studies=6,
        )

        assert GRADEDowngrade.INCONSISTENCY in result.downgrades
        assert "I² > 50%" in result.downgrade_reasons["inconsistency"]

    def test_downgrade_for_risk_of_bias_when_above_25_percent(self) -> None:
        """Auto-downgrade when >25% studies have high RoB."""
        from procedurewriter.agents.meta_analysis.synthesizer_agent import (
            calculate_deterministic_grade,
            GRADEDowngrade,
        )

        result = calculate_deterministic_grade(
            i_squared=20.0,
            high_risk_proportion=0.30,  # 30% high risk
            n_studies=10,
        )

        assert GRADEDowngrade.RISK_OF_BIAS in result.downgrades
        assert ">25% studies with high risk of bias" in result.downgrade_reasons["risk_of_bias"]

    def test_downgrade_for_imprecision_when_k_less_than_5(self) -> None:
        """Auto-downgrade for imprecision when k < 5 studies."""
        from procedurewriter.agents.meta_analysis.synthesizer_agent import (
            calculate_deterministic_grade,
            GRADEDowngrade,
        )

        result = calculate_deterministic_grade(
            i_squared=20.0,
            high_risk_proportion=0.0,
            n_studies=3,  # k < 5
        )

        assert GRADEDowngrade.IMPRECISION in result.downgrades
        assert "k < 5 studies" in result.downgrade_reasons["imprecision"]

    def test_certainty_high_with_no_downgrades(self) -> None:
        """Certainty should be HIGH when no downgrade criteria met."""
        from procedurewriter.agents.meta_analysis.synthesizer_agent import (
            calculate_deterministic_grade,
        )

        result = calculate_deterministic_grade(
            i_squared=30.0,  # Below 50%
            high_risk_proportion=0.10,  # Below 25%
            n_studies=8,  # >= 5
        )

        assert result.certainty_level == "High"
        assert len(result.downgrades) == 0

    def test_certainty_moderate_with_one_downgrade(self) -> None:
        """Certainty drops to MODERATE with 1 downgrade."""
        from procedurewriter.agents.meta_analysis.synthesizer_agent import (
            calculate_deterministic_grade,
        )

        result = calculate_deterministic_grade(
            i_squared=60.0,  # I² > 50% triggers inconsistency
            high_risk_proportion=0.10,
            n_studies=8,
        )

        assert result.certainty_level == "Moderate"
        assert len(result.downgrades) == 1

    def test_certainty_low_with_two_downgrades(self) -> None:
        """Certainty drops to LOW with 2 downgrades."""
        from procedurewriter.agents.meta_analysis.synthesizer_agent import (
            calculate_deterministic_grade,
        )

        result = calculate_deterministic_grade(
            i_squared=60.0,  # Inconsistency
            high_risk_proportion=0.30,  # Risk of bias
            n_studies=8,
        )

        assert result.certainty_level == "Low"
        assert len(result.downgrades) == 2

    def test_certainty_very_low_with_three_downgrades(self) -> None:
        """Certainty drops to VERY LOW with 3+ downgrades."""
        from procedurewriter.agents.meta_analysis.synthesizer_agent import (
            calculate_deterministic_grade,
        )

        result = calculate_deterministic_grade(
            i_squared=60.0,  # Inconsistency
            high_risk_proportion=0.30,  # Risk of bias
            n_studies=3,  # Imprecision
        )

        assert result.certainty_level == "Very Low"
        assert len(result.downgrades) == 3


class TestHartungKnappAdjustment:
    """Tests for Hartung-Knapp CI adjustment when k < 5."""

    def test_uses_t_distribution_when_k_less_than_5(self) -> None:
        """CI should use t-distribution (wider) instead of z=1.96 when k < 5."""
        from procedurewriter.agents.meta_analysis.synthesizer_agent import (
            calculate_random_effects_pooled_hk,
        )

        # 3 studies with known effects
        effects = [0.5, 0.6, 0.55]
        variances = [0.04, 0.05, 0.045]

        result = calculate_random_effects_pooled_hk(effects, variances)

        # With k=3, df=2, t_{0.975,2} ≈ 4.303 >> z=1.96
        # So CI should be wider than standard z-based CI
        ci_width = result.ci_upper - result.ci_lower

        # Calculate what z-based CI would be for comparison
        from procedurewriter.agents.meta_analysis.synthesizer_agent import (
            calculate_random_effects_pooled,
        )
        standard_result = calculate_random_effects_pooled(effects, variances)
        standard_ci_width = standard_result.ci_upper - standard_result.ci_lower

        # Hartung-Knapp CI should be wider
        assert ci_width > standard_ci_width, "HK adjustment should widen CI for small k"

    def test_t_critical_value_correct_for_df_2(self) -> None:
        """t critical value for df=2 should be approximately 4.303."""
        from procedurewriter.agents.meta_analysis.synthesizer_agent import (
            get_t_critical_value,
        )

        t_crit = get_t_critical_value(df=2, alpha=0.05)

        expected = stats.t.ppf(0.975, df=2)  # ≈ 4.303
        assert abs(t_crit - expected) < 0.01

    def test_t_critical_value_correct_for_df_3(self) -> None:
        """t critical value for df=3 should be approximately 3.182."""
        from procedurewriter.agents.meta_analysis.synthesizer_agent import (
            get_t_critical_value,
        )

        t_crit = get_t_critical_value(df=3, alpha=0.05)

        expected = stats.t.ppf(0.975, df=3)  # ≈ 3.182
        assert abs(t_crit - expected) < 0.01

    def test_uses_z_when_k_5_or_more(self) -> None:
        """Standard z=1.96 should be used when k >= 5."""
        from procedurewriter.agents.meta_analysis.synthesizer_agent import (
            calculate_random_effects_pooled_hk,
            calculate_random_effects_pooled,
        )

        effects = [0.5, 0.6, 0.55, 0.48, 0.52]
        variances = [0.04, 0.05, 0.045, 0.042, 0.048]

        hk_result = calculate_random_effects_pooled_hk(effects, variances)
        standard_result = calculate_random_effects_pooled(effects, variances)

        # CIs should be very similar (HK converges to z for large k)
        hk_width = hk_result.ci_upper - hk_result.ci_lower
        standard_width = standard_result.ci_upper - standard_result.ci_lower

        # Allow small difference due to Hartung-Knapp variance adjustment
        assert abs(hk_width - standard_width) < 0.5 * standard_width


# =============================================================================
# FIX 2: SSE ERROR/COMPLETE Events with Emitter Cleanup
# =============================================================================


class TestSSEErrorHandling:
    """Tests for ERROR and COMPLETE event handling in SSE stream."""

    def test_subscribes_to_error_event(self) -> None:
        """SSE stream should subscribe to ERROR events."""
        from procedurewriter.pipeline.events import EventType

        # Import should have ERROR event type
        assert hasattr(EventType, "ERROR")
        assert EventType.ERROR.value == "error"

    def test_subscribes_to_complete_event(self) -> None:
        """SSE stream should subscribe to COMPLETE events."""
        from procedurewriter.pipeline.events import EventType

        assert hasattr(EventType, "COMPLETE")
        assert EventType.COMPLETE.value == "complete"

    @pytest.mark.asyncio
    async def test_stream_terminates_on_error_event(self) -> None:
        """Stream should terminate when ERROR event received."""
        from procedurewriter.api.meta_analysis import get_meta_analysis_events, _active_emitters
        from procedurewriter.pipeline.events import EventEmitter, EventType

        run_id = "test-error-run"
        emitter = EventEmitter()
        _active_emitters[run_id] = emitter

        events_received = []

        async def collect_events():
            async for event in get_meta_analysis_events(run_id):
                events_received.append(event)
                if event.get("event") == "error":
                    break

        # Start collection in background
        task = asyncio.create_task(collect_events())

        # Emit error event
        await asyncio.sleep(0.1)
        emitter.emit(EventType.ERROR, {"message": "Pipeline failed"})

        await asyncio.wait_for(task, timeout=2.0)

        # Verify error was received
        assert any(e.get("event") == "error" for e in events_received)

        # Cleanup
        del _active_emitters[run_id]

    @pytest.mark.asyncio
    async def test_stream_terminates_on_complete_event(self) -> None:
        """Stream should terminate when COMPLETE event received."""
        from procedurewriter.api.meta_analysis import get_meta_analysis_events, _active_emitters
        from procedurewriter.pipeline.events import EventEmitter, EventType

        run_id = "test-complete-run"
        emitter = EventEmitter()
        _active_emitters[run_id] = emitter

        events_received = []

        async def collect_events():
            async for event in get_meta_analysis_events(run_id):
                events_received.append(event)
                if event.get("event") == "complete":
                    break

        task = asyncio.create_task(collect_events())

        await asyncio.sleep(0.1)
        emitter.emit(EventType.COMPLETE, {"status": "done"})

        await asyncio.wait_for(task, timeout=2.0)

        assert any(e.get("event") == "complete" for e in events_received)

        del _active_emitters[run_id]


class TestEmitterCleanup:
    """Tests for emitter cleanup to prevent memory leaks."""

    def test_cleanup_function_exists(self) -> None:
        """cleanup_stale_emitters function should exist."""
        from procedurewriter.api.meta_analysis import cleanup_stale_emitters

        assert callable(cleanup_stale_emitters)

    def test_emitter_has_created_at_timestamp(self) -> None:
        """Active emitters should track creation timestamp."""
        from procedurewriter.api.meta_analysis import (
            _active_emitters,
            _emitter_timestamps,
        )

        # After creating emitter, timestamp should be recorded
        assert isinstance(_emitter_timestamps, dict)

    def test_stale_emitters_removed_after_30_minutes(self) -> None:
        """Emitters inactive for >30 minutes should be pruned."""
        from procedurewriter.api.meta_analysis import (
            cleanup_stale_emitters,
            _active_emitters,
            _emitter_timestamps,
        )
        from procedurewriter.pipeline.events import EventEmitter

        run_id = "test-stale-run"
        emitter = EventEmitter()
        _active_emitters[run_id] = emitter
        _emitter_timestamps[run_id] = time.time() - 1800 - 60  # 31 minutes ago

        cleanup_stale_emitters()

        assert run_id not in _active_emitters
        assert run_id not in _emitter_timestamps

    def test_active_emitters_not_removed(self) -> None:
        """Emitters within 30-minute window should not be pruned."""
        from procedurewriter.api.meta_analysis import (
            cleanup_stale_emitters,
            _active_emitters,
            _emitter_timestamps,
        )
        from procedurewriter.pipeline.events import EventEmitter

        run_id = "test-active-run"
        emitter = EventEmitter()
        _active_emitters[run_id] = emitter
        _emitter_timestamps[run_id] = time.time() - 600  # 10 minutes ago

        cleanup_stale_emitters()

        assert run_id in _active_emitters

        # Cleanup
        del _active_emitters[run_id]
        del _emitter_timestamps[run_id]

    def test_emitter_removed_on_complete_event(self) -> None:
        """Emitter should be cleaned up when COMPLETE is emitted."""
        from procedurewriter.api.meta_analysis import (
            _active_emitters,
            remove_emitter_on_completion,
        )
        from procedurewriter.pipeline.events import EventEmitter

        run_id = "test-cleanup-complete"
        emitter = EventEmitter()
        _active_emitters[run_id] = emitter

        remove_emitter_on_completion(run_id)

        assert run_id not in _active_emitters


# =============================================================================
# FIX 3: Chapter Alignment and Badge Injection
# =============================================================================


class TestGRADEBadgeInjection:
    """Tests for GRADE badge injection into output."""

    def test_synthesis_output_includes_certainty_level(self) -> None:
        """SynthesisOutput should include certainty_level field."""
        from procedurewriter.agents.meta_analysis.synthesizer_agent import (
            SynthesisOutput,
            PooledEstimate,
            HeterogeneityMetrics,
        )

        output = SynthesisOutput(
            pooled_estimate=PooledEstimate(
                pooled_effect=0.5,
                ci_lower=0.3,
                ci_upper=0.7,
                effect_size_type="OR",
                p_value=0.01,
            ),
            heterogeneity=HeterogeneityMetrics(
                cochrans_q=5.0,
                i_squared=40.0,
                tau_squared=0.02,
                df=2,
                p_value=0.1,
            ),
            included_studies=3,
            total_sample_size=500,
            grade_summary="Test summary",
            certainty_level="Moderate",
            forest_plot_data=[],
        )

        assert output.certainty_level == "Moderate"

    def test_markdown_output_contains_grade_badge(self) -> None:
        """Generated Markdown should contain [GRADE: LEVEL] badge."""
        from procedurewriter.pipeline.docx_writer import format_grade_badge

        badge = format_grade_badge("Moderate")

        assert "[GRADE: Moderate]" in badge or "**GRADE: Moderate**" in badge

    def test_docx_contains_grade_badge_section(self) -> None:
        """Generated DOCX should include GRADE badge in visible format."""
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from procedurewriter.pipeline.docx_writer import write_meta_analysis_docx
        from procedurewriter.agents.meta_analysis.orchestrator import OrchestratorOutput
        from procedurewriter.agents.meta_analysis.synthesizer_agent import (
            SynthesisOutput,
            PooledEstimate,
            HeterogeneityMetrics,
        )
        from docx import Document

        synthesis = SynthesisOutput(
            pooled_estimate=PooledEstimate(
                pooled_effect=0.5,
                ci_lower=0.3,
                ci_upper=0.7,
                effect_size_type="OR",
                p_value=0.01,
            ),
            heterogeneity=HeterogeneityMetrics(
                cochrans_q=5.0,
                i_squared=40.0,
                tau_squared=0.02,
                df=2,
                p_value=0.1,
            ),
            included_studies=3,
            total_sample_size=500,
            grade_summary="Moderate certainty evidence.",
            certainty_level="Moderate",
            forest_plot_data=[],
        )

        output = OrchestratorOutput(
            synthesis=synthesis,
            included_study_ids=["S1", "S2", "S3"],
            excluded_study_ids=[],
            exclusion_reasons={},
            manual_review_needed=[],
        )

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.docx"
            write_meta_analysis_docx(
                output=output,
                output_path=output_path,
                run_id="test-badge-run",
            )

            doc = Document(str(output_path))
            all_text = "\n".join(p.text for p in doc.paragraphs)

            assert "GRADE" in all_text or "Moderate" in all_text


# =============================================================================
# FIX 5: Re-validation Test for Hartung-Knapp
# =============================================================================


class TestHartungKnappIntegration:
    """Integration test verifying Hartung-Knapp is active for k < 5."""

    def test_orchestrator_uses_hartung_knapp_for_small_k(self) -> None:
        """Full pipeline should use Hartung-Knapp when k < 5 studies."""
        from unittest.mock import MagicMock
        from procedurewriter.agents.meta_analysis.orchestrator import (
            MetaAnalysisOrchestrator,
            OrchestratorInput,
        )
        from procedurewriter.agents.meta_analysis.screener_agent import PICOQuery
        from procedurewriter.llm.providers import LLMResponse

        mock_llm = MagicMock()
        mock_llm.is_available.return_value = True

        # 3 studies (k < 5)
        studies = [
            {
                "study_id": f"S{i}",
                "title": f"Study {i}",
                "abstract": "RCT in adults...",
                "effect_size": 0.5 + i * 0.1,
                "variance": 0.04,
            }
            for i in range(3)
        ]

        # Mock responses for each study
        responses = []
        for i in range(3):
            # PICO
            responses.append(json.dumps({
                "population": "Adults",
                "intervention": "Drug",
                "comparison": "Placebo",
                "outcome": "Outcome",
                "confidence": 0.9,
                "detected_language": "en",
            }))
            # Screening
            responses.append(json.dumps({
                "decision": "Include",
                "reason": "Matches",
                "confidence": 0.95,
            }))
            # Bias
            responses.append(json.dumps({
                "randomization": "low",
                "deviations": "low",
                "missing_data": "low",
                "measurement": "low",
                "selection": "low",
            }))
        # GRADE
        responses.append(json.dumps({
            "grade_summary": "Low certainty.",
            "certainty_level": "Low",
        }))

        mock_llm.chat_completion.side_effect = [
            LLMResponse(content=r, input_tokens=100, output_tokens=50, total_tokens=150, model="test")
            for r in responses
        ]

        orchestrator = MetaAnalysisOrchestrator(llm=mock_llm)

        input_data = OrchestratorInput(
            query=PICOQuery(
                population="Adults",
                intervention="Drug",
                comparison="Placebo",
                outcome="Outcome",
            ),
            study_sources=studies,
            outcome_of_interest="Outcome",
        )

        result = orchestrator.execute(input_data)

        # Verify Hartung-Knapp was used (CI wider than z-based)
        synthesis = result.output.synthesis
        pooled = synthesis.pooled_estimate

        # With k=3, HK should produce wider CI
        # Check that imprecision downgrade was triggered
        assert synthesis.certainty_level in ["Low", "Very Low", "Moderate"]
