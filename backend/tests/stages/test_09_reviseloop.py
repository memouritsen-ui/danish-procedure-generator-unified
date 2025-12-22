"""Tests for Stage 09: ReviseLoop.

The ReviseLoop stage handles iterative revision:
1. Receives issues and gates from Stage 08 (Evals)
2. Decides whether to revise or proceed
3. Tracks iteration count (max 3)
4. Either signals need for revision or proceeds to Package
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from procedurewriter.models.gates import Gate, GateStatus, GateType
from procedurewriter.models.issues import Issue, IssueCode, IssueSeverity

if TYPE_CHECKING:
    pass


def make_issue(
    run_id: str = "test-run",
    code: IssueCode = IssueCode.DOSE_WITHOUT_EVIDENCE,
    severity: IssueSeverity = IssueSeverity.S0,
    message: str = "Test issue",
) -> Issue:
    """Factory function to create test Issue objects."""
    return Issue(
        run_id=run_id,
        code=code,
        severity=severity,
        message=message,
    )


def make_gate(
    run_id: str = "test-run",
    gate_type: GateType = GateType.S0_SAFETY,
    status: GateStatus = GateStatus.PASS,
) -> Gate:
    """Factory function to create test Gate objects."""
    return Gate(
        run_id=run_id,
        gate_type=gate_type,
        status=status,
    )


class TestReviseLoopStage:
    """Tests for Stage 09: ReviseLoop."""

    def test_reviseloop_stage_name_is_reviseloop(self) -> None:
        """ReviseLoop stage should identify itself as 'reviseloop'."""
        from procedurewriter.pipeline.stages.s09_reviseloop import ReviseLoopStage

        stage = ReviseLoopStage()
        assert stage.name == "reviseloop"

    def test_reviseloop_input_requires_issues_and_gates(self) -> None:
        """ReviseLoop input must have issues and gates fields."""
        from procedurewriter.pipeline.stages.s09_reviseloop import ReviseLoopInput

        issue = make_issue()
        gate = make_gate()

        input_data = ReviseLoopInput(
            run_id="test-run",
            run_dir=Path("/tmp/test"),
            procedure_title="Test Procedure",
            issues=[issue],
            gates=[gate],
            iteration=1,
        )
        assert len(input_data.issues) == 1
        assert len(input_data.gates) == 1
        assert input_data.iteration == 1

    def test_reviseloop_output_has_all_required_fields(self, tmp_path: Path) -> None:
        """ReviseLoop output should contain all fields needed by Package stage."""
        from procedurewriter.pipeline.stages.s09_reviseloop import (
            ReviseLoopInput,
            ReviseLoopStage,
        )

        stage = ReviseLoopStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = ReviseLoopInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            issues=[],
            gates=[make_gate(status=GateStatus.PASS)],
            iteration=1,
        )

        result = stage.execute(input_data)

        assert hasattr(result, "run_id")
        assert hasattr(result, "run_dir")
        assert hasattr(result, "procedure_title")
        assert hasattr(result, "needs_revision")
        assert hasattr(result, "iteration")
        assert hasattr(result, "max_iterations_reached")
        assert hasattr(result, "can_proceed")
        assert result.run_id == "test-run"

    def test_reviseloop_proceeds_when_gates_pass(self, tmp_path: Path) -> None:
        """ReviseLoop should proceed to Package when all gates pass."""
        from procedurewriter.pipeline.stages.s09_reviseloop import (
            ReviseLoopInput,
            ReviseLoopStage,
        )

        stage = ReviseLoopStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = ReviseLoopInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test",
            issues=[],
            gates=[
                make_gate(gate_type=GateType.S0_SAFETY, status=GateStatus.PASS),
                make_gate(gate_type=GateType.S1_QUALITY, status=GateStatus.PASS),
                make_gate(gate_type=GateType.FINAL, status=GateStatus.PASS),
            ],
            iteration=1,
        )

        result = stage.execute(input_data)

        assert result.needs_revision is False
        assert result.can_proceed is True

    def test_reviseloop_needs_revision_when_gates_fail(self, tmp_path: Path) -> None:
        """ReviseLoop should signal revision needed when gates fail."""
        from procedurewriter.pipeline.stages.s09_reviseloop import (
            ReviseLoopInput,
            ReviseLoopStage,
        )

        stage = ReviseLoopStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = ReviseLoopInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test",
            issues=[make_issue()],
            gates=[
                make_gate(gate_type=GateType.S0_SAFETY, status=GateStatus.FAIL),
                make_gate(gate_type=GateType.FINAL, status=GateStatus.FAIL),
            ],
            iteration=1,
        )

        result = stage.execute(input_data)

        assert result.needs_revision is True
        assert result.can_proceed is False

    def test_reviseloop_max_iterations_is_three(self, tmp_path: Path) -> None:
        """ReviseLoop should stop after 3 iterations."""
        from procedurewriter.pipeline.stages.s09_reviseloop import (
            ReviseLoopInput,
            ReviseLoopStage,
        )

        stage = ReviseLoopStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        # At iteration 3, even with failures, should stop
        input_data = ReviseLoopInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test",
            issues=[make_issue()],
            gates=[make_gate(status=GateStatus.FAIL)],
            iteration=3,
        )

        result = stage.execute(input_data)

        assert result.max_iterations_reached is True
        assert result.needs_revision is False  # Can't revise anymore

    def test_reviseloop_increments_iteration(self, tmp_path: Path) -> None:
        """ReviseLoop should track iteration count in output."""
        from procedurewriter.pipeline.stages.s09_reviseloop import (
            ReviseLoopInput,
            ReviseLoopStage,
        )

        stage = ReviseLoopStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = ReviseLoopInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test",
            issues=[],
            gates=[make_gate(status=GateStatus.PASS)],
            iteration=2,
        )

        result = stage.execute(input_data)

        assert result.iteration == 2

    def test_reviseloop_emits_progress_event(self, tmp_path: Path) -> None:
        """ReviseLoop should emit a progress event when starting."""
        from procedurewriter.pipeline.stages.s09_reviseloop import (
            ReviseLoopInput,
            ReviseLoopStage,
        )

        mock_emitter = MagicMock()
        stage = ReviseLoopStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = ReviseLoopInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            issues=[],
            gates=[make_gate(status=GateStatus.PASS)],
            iteration=1,
            emitter=mock_emitter,
        )

        stage.execute(input_data)

        mock_emitter.emit.assert_called()

    def test_reviseloop_passes_through_run_dir(self, tmp_path: Path) -> None:
        """ReviseLoop should pass through run_dir for subsequent stages."""
        from procedurewriter.pipeline.stages.s09_reviseloop import (
            ReviseLoopInput,
            ReviseLoopStage,
        )

        stage = ReviseLoopStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = ReviseLoopInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            issues=[],
            gates=[make_gate(status=GateStatus.PASS)],
            iteration=1,
        )

        result = stage.execute(input_data)

        assert result.run_dir == run_dir

    def test_reviseloop_passes_through_issues(self, tmp_path: Path) -> None:
        """ReviseLoop should pass through issues for reporting."""
        from procedurewriter.pipeline.stages.s09_reviseloop import (
            ReviseLoopInput,
            ReviseLoopStage,
        )

        issue = make_issue()
        stage = ReviseLoopStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = ReviseLoopInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test",
            issues=[issue],
            gates=[make_gate(status=GateStatus.FAIL)],
            iteration=1,
        )

        result = stage.execute(input_data)

        assert result.issues == [issue]

    def test_reviseloop_passes_through_gates(self, tmp_path: Path) -> None:
        """ReviseLoop should pass through gates for reporting."""
        from procedurewriter.pipeline.stages.s09_reviseloop import (
            ReviseLoopInput,
            ReviseLoopStage,
        )

        gate = make_gate(status=GateStatus.PASS)
        stage = ReviseLoopStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = ReviseLoopInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test",
            issues=[],
            gates=[gate],
            iteration=1,
        )

        result = stage.execute(input_data)

        assert result.gates == [gate]

    def test_reviseloop_at_iteration_two_can_still_revise(self, tmp_path: Path) -> None:
        """ReviseLoop at iteration 2 should still allow revision."""
        from procedurewriter.pipeline.stages.s09_reviseloop import (
            ReviseLoopInput,
            ReviseLoopStage,
        )

        stage = ReviseLoopStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = ReviseLoopInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test",
            issues=[make_issue()],
            gates=[make_gate(status=GateStatus.FAIL)],
            iteration=2,
        )

        result = stage.execute(input_data)

        assert result.needs_revision is True
        assert result.max_iterations_reached is False

    def test_reviseloop_provides_revision_guidance(self, tmp_path: Path) -> None:
        """ReviseLoop should provide guidance on what to revise."""
        from procedurewriter.pipeline.stages.s09_reviseloop import (
            ReviseLoopInput,
            ReviseLoopStage,
        )

        stage = ReviseLoopStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        issue = make_issue(code=IssueCode.DOSE_WITHOUT_EVIDENCE)

        input_data = ReviseLoopInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test",
            issues=[issue],
            gates=[make_gate(status=GateStatus.FAIL)],
            iteration=1,
        )

        result = stage.execute(input_data)

        assert hasattr(result, "revision_guidance")
        assert len(result.revision_guidance) > 0
