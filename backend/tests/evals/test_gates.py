"""Tests for the GateEvaluator class.

The GateEvaluator aggregates issues from linters and evaluates pipeline gates:
- S0 gate: Must have 0 S0 (safety-critical) issues to pass
- S1 gate: Must have 0 S1 (quality-critical) issues to pass
- Final gate: Both S0 and S1 gates must pass

Gates are ship-blocking checkpoints that ensure procedure quality and safety.

TDD: Write tests first, then implement the evaluator.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from procedurewriter.models.gates import Gate, GateStatus, GateType
from procedurewriter.models.issues import Issue, IssueCode, IssueSeverity


# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_run_id() -> str:
    """Generate a sample run ID."""
    return "gate_test_run_001"


@pytest.fixture
def no_issues() -> list[Issue]:
    """Empty issues list (all gates should pass)."""
    return []


@pytest.fixture
def s2_issues_only(sample_run_id: str) -> list[Issue]:
    """Only S2 (warning) issues - all gates should pass."""
    return [
        Issue(
            run_id=sample_run_id,
            code=IssueCode.OVERCONFIDENT_LANGUAGE,
            severity=IssueSeverity.S2,
            message="Overconfident language detected",
        ),
        Issue(
            run_id=sample_run_id,
            code=IssueCode.INFORMAL_LANGUAGE,
            severity=IssueSeverity.S2,
            message="Informal language detected",
        ),
    ]


@pytest.fixture
def s0_issues(sample_run_id: str) -> list[Issue]:
    """S0 (safety-critical) issues - S0 and Final gates should fail."""
    return [
        Issue(
            run_id=sample_run_id,
            code=IssueCode.DOSE_WITHOUT_EVIDENCE,
            severity=IssueSeverity.S0,
            message="Dose claim without evidence",
        ),
        Issue(
            run_id=sample_run_id,
            code=IssueCode.CONFLICTING_DOSES,
            severity=IssueSeverity.S0,
            message="Conflicting doses detected",
        ),
    ]


@pytest.fixture
def s1_issues(sample_run_id: str) -> list[Issue]:
    """S1 (quality-critical) issues - S1 and Final gates should fail."""
    return [
        Issue(
            run_id=sample_run_id,
            code=IssueCode.OUTDATED_GUIDELINE,
            severity=IssueSeverity.S1,
            message="Source is outdated",
        ),
        Issue(
            run_id=sample_run_id,
            code=IssueCode.UNIT_MISMATCH,
            severity=IssueSeverity.S1,
            message="Inconsistent units",
        ),
    ]


@pytest.fixture
def mixed_issues(sample_run_id: str) -> list[Issue]:
    """Mix of S0, S1, and S2 issues."""
    return [
        # S0
        Issue(
            run_id=sample_run_id,
            code=IssueCode.DOSE_WITHOUT_EVIDENCE,
            severity=IssueSeverity.S0,
            message="Safety issue",
        ),
        # S1
        Issue(
            run_id=sample_run_id,
            code=IssueCode.OUTDATED_GUIDELINE,
            severity=IssueSeverity.S1,
            message="Quality issue",
        ),
        # S2
        Issue(
            run_id=sample_run_id,
            code=IssueCode.OVERCONFIDENT_LANGUAGE,
            severity=IssueSeverity.S2,
            message="Warning",
        ),
    ]


# ---------------------------------------------------------------------------
# ALL GATES PASS TESTS
# ---------------------------------------------------------------------------


class TestAllGatesPass:
    """Tests for scenarios where all gates should pass."""

    def test_no_issues_all_gates_pass(
        self, sample_run_id: str, no_issues: list[Issue]
    ) -> None:
        """With no issues, all gates pass."""
        from procedurewriter.evals.gates import GateEvaluator

        evaluator = GateEvaluator()
        gates = evaluator.evaluate(sample_run_id, no_issues)

        assert len(gates) == 3  # S0, S1, Final

        s0_gate = next(g for g in gates if g.gate_type == GateType.S0_SAFETY)
        s1_gate = next(g for g in gates if g.gate_type == GateType.S1_QUALITY)
        final_gate = next(g for g in gates if g.gate_type == GateType.FINAL)

        assert s0_gate.status == GateStatus.PASS
        assert s1_gate.status == GateStatus.PASS
        assert final_gate.status == GateStatus.PASS

    def test_s2_warnings_all_gates_pass(
        self, sample_run_id: str, s2_issues_only: list[Issue]
    ) -> None:
        """S2 warnings don't block any gates."""
        from procedurewriter.evals.gates import GateEvaluator

        evaluator = GateEvaluator()
        gates = evaluator.evaluate(sample_run_id, s2_issues_only)

        s0_gate = next(g for g in gates if g.gate_type == GateType.S0_SAFETY)
        s1_gate = next(g for g in gates if g.gate_type == GateType.S1_QUALITY)
        final_gate = next(g for g in gates if g.gate_type == GateType.FINAL)

        assert s0_gate.status == GateStatus.PASS
        assert s1_gate.status == GateStatus.PASS
        assert final_gate.status == GateStatus.PASS


# ---------------------------------------------------------------------------
# S0 GATE TESTS
# ---------------------------------------------------------------------------


class TestS0Gate:
    """Tests for S0 (safety) gate evaluation."""

    def test_s0_issues_fail_s0_gate(
        self, sample_run_id: str, s0_issues: list[Issue]
    ) -> None:
        """S0 issues cause S0 gate to fail."""
        from procedurewriter.evals.gates import GateEvaluator

        evaluator = GateEvaluator()
        gates = evaluator.evaluate(sample_run_id, s0_issues)

        s0_gate = next(g for g in gates if g.gate_type == GateType.S0_SAFETY)

        assert s0_gate.status == GateStatus.FAIL
        assert s0_gate.issues_failed == 2

    def test_s0_gate_tracks_issue_count(
        self, sample_run_id: str, s0_issues: list[Issue]
    ) -> None:
        """S0 gate tracks total issues checked and failed."""
        from procedurewriter.evals.gates import GateEvaluator

        evaluator = GateEvaluator()
        gates = evaluator.evaluate(sample_run_id, s0_issues)

        s0_gate = next(g for g in gates if g.gate_type == GateType.S0_SAFETY)

        assert s0_gate.issues_checked == 2
        assert s0_gate.issues_failed == 2

    def test_s1_issues_dont_affect_s0_gate(
        self, sample_run_id: str, s1_issues: list[Issue]
    ) -> None:
        """S1 issues don't affect S0 gate (only S0 issues do)."""
        from procedurewriter.evals.gates import GateEvaluator

        evaluator = GateEvaluator()
        gates = evaluator.evaluate(sample_run_id, s1_issues)

        s0_gate = next(g for g in gates if g.gate_type == GateType.S0_SAFETY)

        assert s0_gate.status == GateStatus.PASS
        assert s0_gate.issues_failed == 0


# ---------------------------------------------------------------------------
# S1 GATE TESTS
# ---------------------------------------------------------------------------


class TestS1Gate:
    """Tests for S1 (quality) gate evaluation."""

    def test_s1_issues_fail_s1_gate(
        self, sample_run_id: str, s1_issues: list[Issue]
    ) -> None:
        """S1 issues cause S1 gate to fail."""
        from procedurewriter.evals.gates import GateEvaluator

        evaluator = GateEvaluator()
        gates = evaluator.evaluate(sample_run_id, s1_issues)

        s1_gate = next(g for g in gates if g.gate_type == GateType.S1_QUALITY)

        assert s1_gate.status == GateStatus.FAIL
        assert s1_gate.issues_failed == 2

    def test_s0_issues_dont_affect_s1_gate(
        self, sample_run_id: str, s0_issues: list[Issue]
    ) -> None:
        """S0 issues don't affect S1 gate (only S1 issues do)."""
        from procedurewriter.evals.gates import GateEvaluator

        evaluator = GateEvaluator()
        gates = evaluator.evaluate(sample_run_id, s0_issues)

        s1_gate = next(g for g in gates if g.gate_type == GateType.S1_QUALITY)

        assert s1_gate.status == GateStatus.PASS
        assert s1_gate.issues_failed == 0


# ---------------------------------------------------------------------------
# FINAL GATE TESTS
# ---------------------------------------------------------------------------


class TestFinalGate:
    """Tests for Final gate evaluation."""

    def test_final_gate_fails_with_s0_issues(
        self, sample_run_id: str, s0_issues: list[Issue]
    ) -> None:
        """Final gate fails if S0 gate fails."""
        from procedurewriter.evals.gates import GateEvaluator

        evaluator = GateEvaluator()
        gates = evaluator.evaluate(sample_run_id, s0_issues)

        final_gate = next(g for g in gates if g.gate_type == GateType.FINAL)

        assert final_gate.status == GateStatus.FAIL

    def test_final_gate_fails_with_s1_issues(
        self, sample_run_id: str, s1_issues: list[Issue]
    ) -> None:
        """Final gate fails if S1 gate fails."""
        from procedurewriter.evals.gates import GateEvaluator

        evaluator = GateEvaluator()
        gates = evaluator.evaluate(sample_run_id, s1_issues)

        final_gate = next(g for g in gates if g.gate_type == GateType.FINAL)

        assert final_gate.status == GateStatus.FAIL

    def test_final_gate_fails_with_mixed_issues(
        self, sample_run_id: str, mixed_issues: list[Issue]
    ) -> None:
        """Final gate fails if any blocking issues exist."""
        from procedurewriter.evals.gates import GateEvaluator

        evaluator = GateEvaluator()
        gates = evaluator.evaluate(sample_run_id, mixed_issues)

        final_gate = next(g for g in gates if g.gate_type == GateType.FINAL)

        assert final_gate.status == GateStatus.FAIL


# ---------------------------------------------------------------------------
# GATE METADATA TESTS
# ---------------------------------------------------------------------------


class TestGateMetadata:
    """Tests for gate metadata (timestamps, messages, run_id)."""

    def test_gates_have_run_id(
        self, sample_run_id: str, no_issues: list[Issue]
    ) -> None:
        """All gates have the correct run_id."""
        from procedurewriter.evals.gates import GateEvaluator

        evaluator = GateEvaluator()
        gates = evaluator.evaluate(sample_run_id, no_issues)

        for gate in gates:
            assert gate.run_id == sample_run_id

    def test_gates_have_evaluated_at(
        self, sample_run_id: str, no_issues: list[Issue]
    ) -> None:
        """All gates have evaluated_at timestamp set."""
        from procedurewriter.evals.gates import GateEvaluator

        evaluator = GateEvaluator()
        gates = evaluator.evaluate(sample_run_id, no_issues)

        for gate in gates:
            assert gate.evaluated_at is not None
            assert isinstance(gate.evaluated_at, datetime)

    def test_failed_gate_has_message(
        self, sample_run_id: str, s0_issues: list[Issue]
    ) -> None:
        """Failed gates have a message explaining why."""
        from procedurewriter.evals.gates import GateEvaluator

        evaluator = GateEvaluator()
        gates = evaluator.evaluate(sample_run_id, s0_issues)

        s0_gate = next(g for g in gates if g.gate_type == GateType.S0_SAFETY)

        assert s0_gate.message is not None
        assert len(s0_gate.message) > 0

    def test_passed_gate_has_message(
        self, sample_run_id: str, no_issues: list[Issue]
    ) -> None:
        """Passed gates have a success message."""
        from procedurewriter.evals.gates import GateEvaluator

        evaluator = GateEvaluator()
        gates = evaluator.evaluate(sample_run_id, no_issues)

        s0_gate = next(g for g in gates if g.gate_type == GateType.S0_SAFETY)

        assert s0_gate.message is not None


# ---------------------------------------------------------------------------
# EDGE CASES
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and utility methods."""

    def test_can_release_with_no_issues(
        self, sample_run_id: str, no_issues: list[Issue]
    ) -> None:
        """can_release returns True when all gates pass."""
        from procedurewriter.evals.gates import GateEvaluator

        evaluator = GateEvaluator()
        gates = evaluator.evaluate(sample_run_id, no_issues)

        assert evaluator.can_release(gates) is True

    def test_cannot_release_with_s0_issues(
        self, sample_run_id: str, s0_issues: list[Issue]
    ) -> None:
        """can_release returns False when S0 gate fails."""
        from procedurewriter.evals.gates import GateEvaluator

        evaluator = GateEvaluator()
        gates = evaluator.evaluate(sample_run_id, s0_issues)

        assert evaluator.can_release(gates) is False

    def test_cannot_release_with_s1_issues(
        self, sample_run_id: str, s1_issues: list[Issue]
    ) -> None:
        """can_release returns False when S1 gate fails."""
        from procedurewriter.evals.gates import GateEvaluator

        evaluator = GateEvaluator()
        gates = evaluator.evaluate(sample_run_id, s1_issues)

        assert evaluator.can_release(gates) is False

    def test_count_by_severity(
        self, sample_run_id: str, mixed_issues: list[Issue]
    ) -> None:
        """count_by_severity returns correct counts."""
        from procedurewriter.evals.gates import GateEvaluator

        evaluator = GateEvaluator()
        counts = evaluator.count_by_severity(mixed_issues)

        assert counts[IssueSeverity.S0] == 1
        assert counts[IssueSeverity.S1] == 1
        assert counts[IssueSeverity.S2] == 1

    def test_empty_issues_count_by_severity(
        self, no_issues: list[Issue]
    ) -> None:
        """count_by_severity returns zeros for empty list."""
        from procedurewriter.evals.gates import GateEvaluator

        evaluator = GateEvaluator()
        counts = evaluator.count_by_severity(no_issues)

        assert counts[IssueSeverity.S0] == 0
        assert counts[IssueSeverity.S1] == 0
        assert counts[IssueSeverity.S2] == 0
