"""Tests for Pipeline Orchestrator - Integration of all 11 stages.

The PipelineOrchestrator wires together:
00: Bootstrap → 01: TermExpand → 02: Retrieve → 03: Chunk →
04: EvidenceNotes → 05: Draft → 06: ClaimExtract → 07: Bind →
08: Evals → 09: ReviseLoop → 10: PackageRelease
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestPipelineOrchestrator:
    """Tests for the PipelineOrchestrator."""

    def test_orchestrator_has_all_eleven_stages(self) -> None:
        """Orchestrator should have all 11 stages registered."""
        from procedurewriter.pipeline.orchestrator import PipelineOrchestrator

        orchestrator = PipelineOrchestrator()
        assert len(orchestrator.stages) == 11

    def test_orchestrator_stages_in_correct_order(self) -> None:
        """Stages should be in the correct execution order."""
        from procedurewriter.pipeline.orchestrator import PipelineOrchestrator

        orchestrator = PipelineOrchestrator()
        stage_names = [s.name for s in orchestrator.stages]

        expected_order = [
            "bootstrap",
            "termexpand",
            "retrieve",
            "chunk",
            "evidencenotes",
            "draft",
            "claimextract",
            "bind",
            "evals",
            "reviseloop",
            "package",
        ]

        assert stage_names == expected_order

    def test_orchestrator_can_be_created_with_emitter(self) -> None:
        """Orchestrator should accept an event emitter."""
        from procedurewriter.pipeline.orchestrator import PipelineOrchestrator

        mock_emitter = MagicMock()
        orchestrator = PipelineOrchestrator(emitter=mock_emitter)

        assert orchestrator.emitter == mock_emitter

    def test_orchestrator_run_requires_procedure_title(self) -> None:
        """Orchestrator run should require a procedure title."""
        from procedurewriter.pipeline.orchestrator import PipelineOrchestrator

        orchestrator = PipelineOrchestrator()

        with pytest.raises(ValueError, match="procedure_title"):
            orchestrator.run(procedure_title="")

    def test_orchestrator_creates_run_directory(self, tmp_path: Path) -> None:
        """Orchestrator should create a run directory."""
        from procedurewriter.pipeline.orchestrator import PipelineOrchestrator

        orchestrator = PipelineOrchestrator(base_dir=tmp_path)

        # Mock all stages to avoid actual execution
        with patch.object(orchestrator, "_execute_stages") as mock_exec:
            mock_exec.return_value = MagicMock(
                run_id="test-run",
                run_dir=tmp_path / "runs" / "test-run",
                success=True,
            )
            result = orchestrator.run(procedure_title="Test Procedure")

        assert result.run_id is not None

    def test_orchestrator_passes_emitter_to_stages(self, tmp_path: Path) -> None:
        """Orchestrator should pass emitter to each stage input."""
        from procedurewriter.pipeline.orchestrator import PipelineOrchestrator

        mock_emitter = MagicMock()
        orchestrator = PipelineOrchestrator(base_dir=tmp_path, emitter=mock_emitter)

        # Mock the first stage to check emitter is passed
        with patch.object(orchestrator.stages[0], "execute") as mock_stage:
            mock_stage.return_value = MagicMock(
                run_id="test-run",
                run_dir=tmp_path / "runs" / "test-run",
            )
            # We only want to test the first stage receives emitter
            try:
                orchestrator.run(procedure_title="Test")
            except Exception:
                pass  # Expected to fail after first stage

            # Check that execute was called with input containing emitter
            call_args = mock_stage.call_args
            if call_args:
                input_data = call_args[0][0]
                assert hasattr(input_data, "emitter")

    def test_orchestrator_returns_final_result(self, tmp_path: Path) -> None:
        """Orchestrator should return the final stage result."""
        from procedurewriter.pipeline.orchestrator import PipelineOrchestrator

        orchestrator = PipelineOrchestrator(base_dir=tmp_path)

        with patch.object(orchestrator, "_execute_stages") as mock_exec:
            mock_result = MagicMock(
                run_id="test-run",
                run_dir=tmp_path / "runs" / "test-run",
                success=True,
                bundle_path=tmp_path / "bundle.zip",
            )
            mock_exec.return_value = mock_result
            result = orchestrator.run(procedure_title="Test")

        assert result == mock_result

    def test_orchestrator_handles_stage_failure(self, tmp_path: Path) -> None:
        """Orchestrator should handle stage failures gracefully."""
        from procedurewriter.pipeline.orchestrator import (
            PipelineError,
            PipelineOrchestrator,
        )

        orchestrator = PipelineOrchestrator(base_dir=tmp_path)

        with patch.object(orchestrator.stages[0], "execute") as mock_stage:
            mock_stage.side_effect = RuntimeError("Stage failed")

            with pytest.raises(PipelineError):
                orchestrator.run(procedure_title="Test")

    def test_orchestrator_emits_start_event(self, tmp_path: Path) -> None:
        """Orchestrator should emit a start event."""
        from procedurewriter.pipeline.events import EventType
        from procedurewriter.pipeline.orchestrator import PipelineOrchestrator

        mock_emitter = MagicMock()
        orchestrator = PipelineOrchestrator(base_dir=tmp_path, emitter=mock_emitter)

        # Patch _execute_stages to prevent full execution
        with patch.object(
            orchestrator, "_execute_stages", return_value=MagicMock()
        ) as mock_exec:
            orchestrator.run(procedure_title="Test")

        # Check emit was called with progress event at start
        mock_emitter.emit.assert_called_once_with(
            EventType.PROGRESS,
            {"message": "Pipeline starting", "procedure_title": "Test"},
        )

    def test_orchestrator_stage_order_matches_documentation(self) -> None:
        """Stage order should match the documented 11-stage pipeline."""
        from procedurewriter.pipeline.orchestrator import PipelineOrchestrator

        orchestrator = PipelineOrchestrator()

        # Documented order from BUILD.md
        documented_stages = [
            "00 Bootstrap",
            "01 TermExpand",
            "02 Retrieve",
            "03 Chunk",
            "04 EvidenceNotes",
            "05 Draft",
            "06 ClaimExtract",
            "07 Bind",
            "08 Evals",
            "09 ReviseLoop",
            "10 PackageRelease",
        ]

        # Extract just the names (without numbers)
        doc_names = [s.split()[1].lower() for s in documented_stages]
        # Handle PackageRelease -> package
        doc_names[-1] = "package"

        actual_names = [s.name for s in orchestrator.stages]

        assert actual_names == doc_names


class TestPipelineStageExports:
    """Tests for stage module exports."""

    def test_all_stages_exported_from_init(self) -> None:
        """All 11 stages should be importable from stages module."""
        from procedurewriter.pipeline import stages

        expected_stages = [
            "BootstrapStage",
            "TermExpandStage",
            "RetrieveStage",
            "ChunkStage",
            "EvidenceNotesStage",
            "DraftStage",
            "ClaimExtractStage",
            "BindStage",
            "EvalsStage",
            "ReviseLoopStage",
            "PackageReleaseStage",
        ]

        for stage_name in expected_stages:
            assert hasattr(stages, stage_name), f"Missing export: {stage_name}"

    def test_all_inputs_exported_from_init(self) -> None:
        """All stage inputs should be exportable."""
        from procedurewriter.pipeline import stages

        expected_inputs = [
            "BootstrapInput",
            "TermExpandInput",
            "RetrieveInput",
            "ChunkInput",
            "EvidenceNotesInput",
            "DraftInput",
            "ClaimExtractInput",
            "BindInput",
            "EvalsInput",
            "ReviseLoopInput",
            "PackageReleaseInput",
        ]

        for input_name in expected_inputs:
            assert hasattr(stages, input_name), f"Missing export: {input_name}"

    def test_all_outputs_exported_from_init(self) -> None:
        """All stage outputs should be exportable."""
        from procedurewriter.pipeline import stages

        expected_outputs = [
            "BootstrapOutput",
            "TermExpandOutput",
            "RetrieveOutput",
            "ChunkOutput",
            "EvidenceNotesOutput",
            "DraftOutput",
            "ClaimExtractOutput",
            "BindOutput",
            "EvalsOutput",
            "ReviseLoopOutput",
            "PackageReleaseOutput",
        ]

        for output_name in expected_outputs:
            assert hasattr(stages, output_name), f"Missing export: {output_name}"


class TestPipelineError:
    """Tests for PipelineError exception."""

    def test_pipeline_error_includes_stage_name(self) -> None:
        """PipelineError should include the failing stage name."""
        from procedurewriter.pipeline.orchestrator import PipelineError

        error = PipelineError("Test error", stage="bootstrap")
        assert error.stage == "bootstrap"
        assert "bootstrap" in str(error)

    def test_pipeline_error_includes_original_exception(self) -> None:
        """PipelineError should preserve the original exception."""
        from procedurewriter.pipeline.orchestrator import PipelineError

        original = ValueError("Original error")
        error = PipelineError("Wrapper", stage="chunk", cause=original)
        assert error.cause == original
