"""Stage 08: Evals - Run lints and evaluate gates.

The Evals stage detects issues and evaluates quality gates:
1. Receives bound claims and links from Stage 07 (Bind)
2. Runs lint checks to detect issues (S0/S1/S2)
3. Creates Issue objects for detected problems
4. Evaluates gates (S0_SAFETY, S1_QUALITY, FINAL)
5. Outputs issues and gate statuses for ReviseLoop
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from procedurewriter.models.claims import Claim, ClaimType
from procedurewriter.models.evidence import ClaimEvidenceLink
from procedurewriter.models.gates import Gate, GateStatus, GateType
from procedurewriter.models.issues import Issue, IssueCode, IssueSeverity
from procedurewriter.pipeline.events import EventType
from procedurewriter.pipeline.stages.base import PipelineStage

if TYPE_CHECKING:
    from procedurewriter.pipeline.events import EventEmitter

logger = logging.getLogger(__name__)

# Claim types that are safety-critical (S0) when unbound
S0_CLAIM_TYPES = {
    ClaimType.DOSE,
    ClaimType.THRESHOLD,
    ClaimType.CONTRAINDICATION,
}


class S0SafetyError(Exception):
    """R4-015: Raised when S0 safety issues are found and fail_on_s0 is True."""

    pass


@dataclass
class EvalsInput:
    """Input for the Evals stage."""

    run_id: str
    run_dir: Path
    procedure_title: str
    claims: list[Claim]
    links: list[ClaimEvidenceLink]
    unbound_claims: list[Claim]
    emitter: "EventEmitter | None" = None
    fail_on_s0: bool = False  # R4-015: Option to fail pipeline on S0 issues


@dataclass
class EvalsOutput:
    """Output from the Evals stage."""

    run_id: str
    run_dir: Path
    procedure_title: str
    issues: list[Issue]
    gates: list[Gate]
    s0_count: int = 0
    s1_count: int = 0
    s2_count: int = 0
    all_gates_passed: bool = False


class EvalsStage(PipelineStage[EvalsInput, EvalsOutput]):
    """Stage 08: Evals - Run lints and evaluate gates."""

    @property
    def name(self) -> str:
        """Return the stage name."""
        return "evals"

    def execute(self, input_data: EvalsInput) -> EvalsOutput:
        """Execute the evals stage.

        Runs lint checks and evaluates quality gates.

        Args:
            input_data: Evals input containing claims, links, and unbound claims

        Returns:
            Evals output with issues and gate evaluations
        """
        # Emit progress event if emitter provided
        if input_data.emitter is not None:
            input_data.emitter.emit(
                EventType.PROGRESS,
                {
                    "message": f"Evaluating {input_data.procedure_title}",
                    "stage": "evals",
                },
            )

        # Run lint checks
        issues = self._run_lints(input_data)

        # Count issues by severity
        s0_count = sum(1 for i in issues if i.severity == IssueSeverity.S0)
        s1_count = sum(1 for i in issues if i.severity == IssueSeverity.S1)
        s2_count = sum(1 for i in issues if i.severity == IssueSeverity.S2)

        logger.info(
            f"Found {len(issues)} issues: {s0_count} S0, {s1_count} S1, {s2_count} S2"
        )

        # R4-015: Fail immediately if S0 issues found and fail_on_s0 is True
        if input_data.fail_on_s0 and s0_count > 0:
            s0_issues = [i for i in issues if i.severity == IssueSeverity.S0]
            raise S0SafetyError(
                f"R4-015: Pipeline stopped due to {s0_count} S0 safety issues: "
                f"{[i.message[:50] for i in s0_issues[:3]]}"
            )

        # Evaluate gates
        gates = self._evaluate_gates(
            run_id=input_data.run_id,
            s0_count=s0_count,
            s1_count=s1_count,
        )

        # Determine if all gates passed
        all_gates_passed = all(g.status == GateStatus.PASS for g in gates)

        return EvalsOutput(
            run_id=input_data.run_id,
            run_dir=input_data.run_dir,
            procedure_title=input_data.procedure_title,
            issues=issues,
            gates=gates,
            s0_count=s0_count,
            s1_count=s1_count,
            s2_count=s2_count,
            all_gates_passed=all_gates_passed,
        )

    def _run_lints(self, input_data: EvalsInput) -> list[Issue]:
        """Run all lint checks and collect issues.

        Args:
            input_data: Input with claims and binding info

        Returns:
            List of detected issues
        """
        issues: list[Issue] = []

        # Check unbound claims
        issues.extend(self._check_unbound_claims(input_data))

        return issues

    def _check_unbound_claims(self, input_data: EvalsInput) -> list[Issue]:
        """Check for claims that couldn't be bound to evidence.

        Args:
            input_data: Input with unbound claims list

        Returns:
            List of issues for unbound claims
        """
        issues: list[Issue] = []

        for claim in input_data.unbound_claims:
            issue = self._create_unbound_claim_issue(claim, input_data.run_id)
            issues.append(issue)

        return issues

    def _create_unbound_claim_issue(self, claim: Claim, run_id: str) -> Issue:
        """Create an issue for an unbound claim.

        The severity depends on claim type:
        - DOSE, THRESHOLD, CONTRAINDICATION → S0 (safety-critical)
        - Other types → S1 (quality-critical)

        Args:
            claim: The unbound claim
            run_id: Pipeline run ID

        Returns:
            Issue object for this unbound claim
        """
        if claim.claim_type in S0_CLAIM_TYPES:
            # Safety-critical claim types
            code = self._get_s0_code_for_claim_type(claim.claim_type)
            severity = IssueSeverity.S0
            message = f"{claim.claim_type.value.upper()} claim has no evidence: '{claim.text[:50]}...'"
        else:
            # Quality-critical (S1) for other types
            code = IssueCode.CLAIM_BINDING_FAILED
            severity = IssueSeverity.S1
            message = f"Claim could not be bound to evidence: '{claim.text[:50]}...'"

        return Issue(
            run_id=run_id,
            code=code,
            severity=severity,
            message=message,
            line_number=claim.line_number,
            claim_id=claim.id,
        )

    def _get_s0_code_for_claim_type(self, claim_type: ClaimType) -> IssueCode:
        """Get the appropriate S0 issue code for a claim type.

        Args:
            claim_type: Type of the claim

        Returns:
            Appropriate IssueCode
        """
        mapping = {
            ClaimType.DOSE: IssueCode.DOSE_WITHOUT_EVIDENCE,
            ClaimType.THRESHOLD: IssueCode.THRESHOLD_WITHOUT_EVIDENCE,
            ClaimType.CONTRAINDICATION: IssueCode.CONTRAINDICATION_UNBOUND,
        }
        return mapping.get(claim_type, IssueCode.DOSE_WITHOUT_EVIDENCE)

    def _evaluate_gates(
        self,
        run_id: str,
        s0_count: int,
        s1_count: int,
    ) -> list[Gate]:
        """Evaluate all pipeline gates.

        Args:
            run_id: Pipeline run ID
            s0_count: Number of S0 issues
            s1_count: Number of S1 issues

        Returns:
            List of evaluated Gate objects
        """
        gates: list[Gate] = []
        now = datetime.now(timezone.utc)

        # S0 Safety Gate
        s0_status = GateStatus.PASS if s0_count == 0 else GateStatus.FAIL
        s0_gate = Gate(
            run_id=run_id,
            gate_type=GateType.S0_SAFETY,
            status=s0_status,
            issues_checked=s0_count,
            issues_failed=s0_count,
            message=f"{'No' if s0_count == 0 else s0_count} safety-critical issues",
            evaluated_at=now,
        )
        gates.append(s0_gate)

        # S1 Quality Gate
        s1_status = GateStatus.PASS if s1_count == 0 else GateStatus.FAIL
        s1_gate = Gate(
            run_id=run_id,
            gate_type=GateType.S1_QUALITY,
            status=s1_status,
            issues_checked=s1_count,
            issues_failed=s1_count,
            message=f"{'No' if s1_count == 0 else s1_count} quality-critical issues",
            evaluated_at=now,
        )
        gates.append(s1_gate)

        # Final Gate - passes only if both S0 and S1 pass
        final_status = (
            GateStatus.PASS
            if (s0_status == GateStatus.PASS and s1_status == GateStatus.PASS)
            else GateStatus.FAIL
        )
        total_blocking = s0_count + s1_count
        final_gate = Gate(
            run_id=run_id,
            gate_type=GateType.FINAL,
            status=final_status,
            issues_checked=total_blocking,
            issues_failed=total_blocking,
            message="All gates passed" if final_status == GateStatus.PASS else f"{total_blocking} blocking issues",
            evaluated_at=now,
        )
        gates.append(final_gate)

        return gates
