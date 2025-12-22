"""GateEvaluator - Evaluates pipeline gates based on issue severities.

Gates are checkpoints that determine if a procedure can be released:
- S0 gate: Must have 0 S0 (safety-critical) issues to pass
- S1 gate: Must have 0 S1 (quality-critical) issues to pass
- Final gate: Both S0 and S1 gates must pass for release

S2 warnings don't block gates but should still be reviewed.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from procedurewriter.models.gates import Gate, GateStatus, GateType
from procedurewriter.models.issues import Issue, IssueSeverity

if TYPE_CHECKING:
    pass


class GateEvaluator:
    """Evaluates pipeline gates based on issue counts by severity.

    This evaluator:
    1. Counts issues by severity (S0, S1, S2)
    2. Creates and evaluates S0_SAFETY gate (fails if any S0 issues)
    3. Creates and evaluates S1_QUALITY gate (fails if any S1 issues)
    4. Creates and evaluates FINAL gate (fails if S0 or S1 gate fails)

    Example:
        evaluator = GateEvaluator()
        gates = evaluator.evaluate(run_id, issues)

        if evaluator.can_release(gates):
            # Proceed with release
        else:
            # Fix issues first
    """

    def evaluate(self, run_id: str, issues: list[Issue]) -> list[Gate]:
        """Evaluate all gates based on the given issues.

        Args:
            run_id: The procedure run ID
            issues: List of issues to evaluate

        Returns:
            List of 3 Gate objects (S0, S1, Final) with evaluation results
        """
        now = datetime.now(timezone.utc)
        counts = self.count_by_severity(issues)

        # Evaluate S0 gate
        s0_count = counts[IssueSeverity.S0]
        s0_passed = s0_count == 0
        s0_gate = Gate(
            run_id=run_id,
            gate_type=GateType.S0_SAFETY,
            status=GateStatus.PASS if s0_passed else GateStatus.FAIL,
            issues_checked=s0_count,
            issues_failed=s0_count,
            message=self._gate_message(GateType.S0_SAFETY, s0_passed, s0_count),
            evaluated_at=now,
        )

        # Evaluate S1 gate
        s1_count = counts[IssueSeverity.S1]
        s1_passed = s1_count == 0
        s1_gate = Gate(
            run_id=run_id,
            gate_type=GateType.S1_QUALITY,
            status=GateStatus.PASS if s1_passed else GateStatus.FAIL,
            issues_checked=s1_count,
            issues_failed=s1_count,
            message=self._gate_message(GateType.S1_QUALITY, s1_passed, s1_count),
            evaluated_at=now,
        )

        # Evaluate Final gate (passes only if S0 and S1 both pass)
        final_passed = s0_passed and s1_passed
        total_blocking = s0_count + s1_count
        final_gate = Gate(
            run_id=run_id,
            gate_type=GateType.FINAL,
            status=GateStatus.PASS if final_passed else GateStatus.FAIL,
            issues_checked=total_blocking,
            issues_failed=total_blocking,
            message=self._final_gate_message(final_passed, s0_count, s1_count),
            evaluated_at=now,
        )

        return [s0_gate, s1_gate, final_gate]

    def can_release(self, gates: list[Gate]) -> bool:
        """Check if procedure can be released based on gate results.

        Args:
            gates: List of evaluated Gate objects

        Returns:
            True if all gates pass, False otherwise
        """
        return all(gate.is_passed for gate in gates)

    def count_by_severity(self, issues: list[Issue]) -> dict[IssueSeverity, int]:
        """Count issues by severity level.

        Args:
            issues: List of issues to count

        Returns:
            Dict mapping severity to count
        """
        counts: Counter[IssueSeverity] = Counter()

        for issue in issues:
            counts[issue.severity] += 1

        # Ensure all severity levels are present (default 0)
        for severity in IssueSeverity:
            if severity not in counts:
                counts[severity] = 0

        return dict(counts)

    def _gate_message(
        self, gate_type: GateType, passed: bool, issue_count: int
    ) -> str:
        """Generate message for S0 or S1 gate.

        Args:
            gate_type: Type of gate
            passed: Whether gate passed
            issue_count: Number of issues of this severity

        Returns:
            Human-readable gate status message
        """
        severity_name = "safety" if gate_type == GateType.S0_SAFETY else "quality"

        if passed:
            return f"All {severity_name} checks passed (0 {severity_name}-critical issues)"
        else:
            plural = "s" if issue_count != 1 else ""
            return (
                f"Gate failed: {issue_count} {severity_name}-critical issue{plural} "
                f"must be resolved before release"
            )

    def _final_gate_message(
        self, passed: bool, s0_count: int, s1_count: int
    ) -> str:
        """Generate message for Final gate.

        Args:
            passed: Whether final gate passed
            s0_count: Number of S0 issues
            s1_count: Number of S1 issues

        Returns:
            Human-readable final gate status message
        """
        if passed:
            return "Release approved: all gates passed"
        else:
            parts = []
            if s0_count > 0:
                parts.append(f"{s0_count} safety-critical (S0)")
            if s1_count > 0:
                parts.append(f"{s1_count} quality-critical (S1)")

            return f"Release blocked: {', '.join(parts)} issue(s) must be resolved"
