"""Pipeline Orchestrator - Wires all 11 stages together.

The orchestrator manages the execution of the full pipeline:
00: Bootstrap → 01: TermExpand → 02: Retrieve → 03: Chunk →
04: EvidenceNotes → 05: Draft → 06: ClaimExtract → 07: Bind →
08: Evals → 09: ReviseLoop → 10: PackageRelease
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from procedurewriter.pipeline.events import EventType
from procedurewriter.pipeline.stages import (
    BindStage,
    BootstrapInput,
    BootstrapStage,
    ChunkStage,
    ClaimExtractStage,
    DraftStage,
    EvalsStage,
    EvidenceNotesStage,
    PackageReleaseStage,
    PipelineStage,
    RetrieveStage,
    ReviseLoopStage,
    TermExpandStage,
)

if TYPE_CHECKING:
    from procedurewriter.pipeline.events import EventEmitter
    from procedurewriter.pipeline.stages.s10_package import PackageReleaseOutput

logger = logging.getLogger(__name__)


class PipelineError(Exception):
    """Exception raised when a pipeline stage fails."""

    def __init__(
        self,
        message: str,
        stage: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        """Initialize PipelineError.

        Args:
            message: Error message
            stage: Name of the failing stage
            cause: Original exception
        """
        self.stage = stage
        self.cause = cause
        full_message = f"Pipeline error in stage '{stage}': {message}" if stage else message
        super().__init__(full_message)


@dataclass
class PipelineResult:
    """Result from a complete pipeline run."""

    run_id: str
    run_dir: Path
    procedure_title: str
    success: bool
    bundle_path: Path | None = None
    error_message: str | None = None
    iterations: int = 1


class PipelineOrchestrator:
    """Orchestrates the 11-stage medical procedure pipeline.

    The orchestrator:
    1. Creates and manages all stages
    2. Passes data between stages
    3. Handles revision loops
    4. Manages event emission
    """

    def __init__(
        self,
        base_dir: Path | None = None,
        emitter: "EventEmitter | None" = None,
    ) -> None:
        """Initialize the orchestrator.

        Args:
            base_dir: Base directory for run outputs
            emitter: Event emitter for progress updates
        """
        self.base_dir = base_dir or Path("data")
        self.emitter = emitter

        # Initialize all 11 stages in order
        self.stages: list[PipelineStage[Any, Any]] = [
            BootstrapStage(),
            TermExpandStage(),
            RetrieveStage(),
            ChunkStage(),
            EvidenceNotesStage(),
            DraftStage(),
            ClaimExtractStage(),
            BindStage(),
            EvalsStage(),
            ReviseLoopStage(),
            PackageReleaseStage(),
        ]

    def run(self, procedure_title: str) -> "PackageReleaseOutput":
        """Run the full pipeline.

        Args:
            procedure_title: The title of the procedure to generate

        Returns:
            The final PackageReleaseOutput

        Raises:
            ValueError: If procedure_title is empty
            PipelineError: If any stage fails
        """
        if not procedure_title:
            raise ValueError("procedure_title is required")

        # Emit start event
        if self.emitter:
            self.emitter.emit(
                EventType.PROGRESS,
                {"message": "Pipeline starting", "procedure_title": procedure_title},
            )

        logger.info(f"Starting pipeline for: {procedure_title}")

        return self._execute_stages(procedure_title)

    def _execute_stages(self, procedure_title: str) -> "PackageReleaseOutput":
        """Execute all stages in sequence.

        Args:
            procedure_title: The procedure title

        Returns:
            The final output from PackageRelease stage

        Raises:
            PipelineError: If any stage fails
        """
        # Generate run ID
        run_id = uuid.uuid4().hex

        # Track procedure_title across stages (not part of all outputs)
        self._current_procedure_title = procedure_title

        # Start with Bootstrap input
        runs_dir = self.base_dir / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)

        current_input: Any = BootstrapInput(
            run_id=run_id,
            runs_dir=runs_dir,
            author_guide_path=None,
            allowlist_path=None,
            evidence_hierarchy_path=None,
            emitter=self.emitter,
        )

        current_output: Any = None

        for stage in self.stages:
            try:
                logger.info(f"Executing stage: {stage.name}")

                # Add emitter to input if it has that field
                if hasattr(current_input, "emitter"):
                    object.__setattr__(current_input, "emitter", self.emitter)

                current_output = stage.execute(current_input)

                # Transform output to next input
                current_input = self._transform_output_to_input(
                    stage.name,
                    current_output,
                )

            except Exception as e:
                logger.error(f"Stage {stage.name} failed: {e}")
                raise PipelineError(
                    message=str(e),
                    stage=stage.name,
                    cause=e if isinstance(e, Exception) else None,
                ) from e

        # Return the final PackageRelease output
        return current_output

    def _transform_output_to_input(
        self,
        stage_name: str,
        output: Any,
    ) -> Any:
        """Transform a stage output into the next stage's input.

        This handles the data flow between stages, mapping output fields
        to the corresponding input fields of the next stage.

        Args:
            stage_name: Name of the completed stage
            output: Output from the completed stage

        Returns:
            Input for the next stage
        """
        from procedurewriter.pipeline.stages import (
            BindInput,
            ChunkInput,
            ClaimExtractInput,
            DraftInput,
            EvalsInput,
            EvidenceNotesInput,
            PackageReleaseInput,
            RetrieveInput,
            ReviseLoopInput,
            TermExpandInput,
        )

        # Get procedure_title from orchestrator state (Bootstrap doesn't output it)
        procedure_title = getattr(self, "_current_procedure_title", "Unknown")

        # Map stage outputs to next stage inputs
        if stage_name == "bootstrap":
            return TermExpandInput(
                run_id=output.run_id,
                run_dir=output.run_dir,
                procedure_title=procedure_title,
                emitter=self.emitter,
            )
        elif stage_name == "termexpand":
            return RetrieveInput(
                run_id=output.run_id,
                run_dir=output.run_dir,
                procedure_title=procedure_title,
                search_terms=output.search_terms,
                emitter=self.emitter,
            )
        elif stage_name == "retrieve":
            return ChunkInput(
                run_id=output.run_id,
                run_dir=output.run_dir,
                procedure_title=procedure_title,
                sources=output.sources,
                emitter=self.emitter,
            )
        elif stage_name == "chunk":
            return EvidenceNotesInput(
                run_id=output.run_id,
                run_dir=output.run_dir,
                procedure_title=procedure_title,
                chunks=output.chunks,
                emitter=self.emitter,
            )
        elif stage_name == "evidencenotes":
            return DraftInput(
                run_id=output.run_id,
                run_dir=output.run_dir,
                procedure_title=procedure_title,
                evidence_notes=output.evidence_notes,
                emitter=self.emitter,
            )
        elif stage_name == "draft":
            return ClaimExtractInput(
                run_id=output.run_id,
                run_dir=output.run_dir,
                procedure_title=procedure_title,
                draft_content=output.draft_content,
                emitter=self.emitter,
            )
        elif stage_name == "claimextract":
            return BindInput(
                run_id=output.run_id,
                run_dir=output.run_dir,
                procedure_title=procedure_title,
                claims=output.claims,
                chunks=output.chunks,
                emitter=self.emitter,
            )
        elif stage_name == "bind":
            return EvalsInput(
                run_id=output.run_id,
                run_dir=output.run_dir,
                procedure_title=procedure_title,
                claims=output.claims,
                links=output.links,
                draft_content=output.draft_content,
                emitter=self.emitter,
            )
        elif stage_name == "evals":
            return ReviseLoopInput(
                run_id=output.run_id,
                run_dir=output.run_dir,
                procedure_title=procedure_title,
                issues=output.issues,
                gates=output.gates,
                iteration=1,
                emitter=self.emitter,
            )
        elif stage_name == "reviseloop":
            return PackageReleaseInput(
                run_id=output.run_id,
                run_dir=output.run_dir,
                procedure_title=procedure_title,
                issues=output.issues,
                gates=output.gates,
                iteration=output.iteration,
                emitter=self.emitter,
            )
        else:
            # PackageRelease is the final stage
            return output
