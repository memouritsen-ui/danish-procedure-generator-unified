"""Stage 09: ReviseLoop - Handle iterative revision.

The ReviseLoop stage decides whether to revise or proceed:
1. Receives issues and gates from Stage 08 (Evals)
2. Decides whether to revise based on gate status
3. Tracks iteration count (max 3)
4. Either signals need for revision or proceeds to Package
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from procedurewriter.models.gates import Gate, GateStatus
from procedurewriter.models.issues import Issue, IssueSeverity
from procedurewriter.pipeline.events import EventType
from procedurewriter.pipeline.stages.base import PipelineStage

if TYPE_CHECKING:
    from procedurewriter.pipeline.events import EventEmitter

logger = logging.getLogger(__name__)

# Maximum number of revision iterations
MAX_ITERATIONS = 3


@dataclass
class ReviseLoopInput:
    """Input for the ReviseLoop stage."""

    run_id: str
    run_dir: Path
    procedure_title: str
    issues: list[Issue]
    gates: list[Gate]
    iteration: int = 1
    emitter: "EventEmitter | None" = None
    score_history: list[int] = field(default_factory=list)  # R4-017: Track issue count history


@dataclass
class ReviseLoopOutput:
    """Output from the ReviseLoop stage."""

    run_id: str
    run_dir: Path
    procedure_title: str
    issues: list[Issue]
    gates: list[Gate]
    iteration: int
    needs_revision: bool
    max_iterations_reached: bool
    can_proceed: bool
    revision_guidance: list[str] = field(default_factory=list)
    score_history: list[int] = field(default_factory=list)  # R4-017: Issue count history
    improvement_stalled: bool = False  # R4-017: True if no improvement detected


class ReviseLoopStage(PipelineStage[ReviseLoopInput, ReviseLoopOutput]):
    """Stage 09: ReviseLoop - Handle iterative revision."""

    @property
    def name(self) -> str:
        """Return the stage name."""
        return "reviseloop"

    def execute(self, input_data: ReviseLoopInput) -> ReviseLoopOutput:
        """Execute the revise loop stage.

        Decides whether to revise based on gate status and iteration count.

        Args:
            input_data: ReviseLoop input containing issues and gates

        Returns:
            ReviseLoop output with revision decision
        """
        # Emit progress event if emitter provided
        if input_data.emitter is not None:
            input_data.emitter.emit(
                EventType.PROGRESS,
                {
                    "message": f"Evaluating revision for {input_data.procedure_title} (iteration {input_data.iteration})",
                    "stage": "reviseloop",
                },
            )

        # Check if all gates pass
        all_gates_pass = all(g.status == GateStatus.PASS for g in input_data.gates)

        # Check if we've reached max iterations
        max_iterations_reached = input_data.iteration >= MAX_ITERATIONS

        # R4-017: Track score history (total blocking issues)
        current_score = sum(
            1 for i in input_data.issues
            if i.severity in (IssueSeverity.S0, IssueSeverity.S1)
        )
        score_history = list(input_data.score_history) + [current_score]

        # R4-017: Detect improvement stalling
        improvement_stalled = False
        if len(score_history) >= 2:
            # Stalled if score is same or worse than previous iteration
            if score_history[-1] >= score_history[-2]:
                improvement_stalled = True
                logger.warning(
                    f"R4-017: No improvement detected (scores: {score_history})"
                )

        # Determine if we need revision
        if all_gates_pass:
            # Gates pass - proceed to Package
            needs_revision = False
            can_proceed = True
            revision_guidance = []
            logger.info(
                f"All gates passed at iteration {input_data.iteration}, proceeding to Package"
            )
        elif max_iterations_reached or improvement_stalled:
            # R4-017: Stop if stalled OR max iterations reached
            needs_revision = False
            can_proceed = True  # Proceed anyway with warnings
            revision_guidance = self._generate_guidance(input_data.issues)
            if improvement_stalled:
                logger.warning(
                    f"R4-017: Improvement stalled at iteration {input_data.iteration}, proceeding anyway"
                )
            else:
                logger.warning(
                    f"Max iterations ({MAX_ITERATIONS}) reached with issues, proceeding anyway"
                )
        else:
            # Gates fail and iterations remain - request revision
            needs_revision = True
            can_proceed = False
            revision_guidance = self._generate_guidance(input_data.issues)
            logger.info(
                f"Gates failed at iteration {input_data.iteration}, requesting revision"
            )

        return ReviseLoopOutput(
            run_id=input_data.run_id,
            run_dir=input_data.run_dir,
            procedure_title=input_data.procedure_title,
            issues=input_data.issues,
            gates=input_data.gates,
            iteration=input_data.iteration,
            needs_revision=needs_revision,
            max_iterations_reached=max_iterations_reached,
            can_proceed=can_proceed,
            revision_guidance=revision_guidance,
            score_history=score_history,  # R4-017
            improvement_stalled=improvement_stalled,  # R4-017
        )

    def _generate_guidance(self, issues: list[Issue]) -> list[str]:
        """Generate revision guidance based on issues.

        Args:
            issues: List of issues to generate guidance for

        Returns:
            List of guidance strings
        """
        guidance: list[str] = []

        # Group issues by severity
        s0_issues = [i for i in issues if i.severity == IssueSeverity.S0]
        s1_issues = [i for i in issues if i.severity == IssueSeverity.S1]

        if s0_issues:
            guidance.append(
                f"CRITICAL: {len(s0_issues)} safety issues require immediate attention"
            )
            for issue in s0_issues[:3]:  # Top 3
                guidance.append(f"  - {issue.code.value}: {issue.message[:80]}")

        if s1_issues:
            guidance.append(
                f"QUALITY: {len(s1_issues)} quality issues need resolution"
            )
            for issue in s1_issues[:3]:  # Top 3
                guidance.append(f"  - {issue.code.value}: {issue.message[:80]}")

        if not guidance:
            guidance.append("No specific issues found, but gates did not pass")

        return guidance
