"""Pipeline Orchestrator - Wires all 11 stages together.

The orchestrator manages the execution of the full pipeline:
00: Bootstrap → 01: TermExpand → 02: Retrieve → 03: Chunk →
04: EvidenceNotes → 05: Draft → 06: ClaimExtract → 07: Bind →
08: Evals → 09: ReviseLoop → 10: PackageRelease

Supports checkpoint/resume for crash recovery (R4-002).
"""

from __future__ import annotations

import logging
import pickle
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
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
    5. Supports checkpoint/resume for crash recovery (R4-002)
    """

    def __init__(
        self,
        base_dir: Path | None = None,
        emitter: "EventEmitter | None" = None,
        run_dir: Path | None = None,
    ) -> None:
        """Initialize the orchestrator.

        Args:
            base_dir: Base directory for run outputs
            emitter: Event emitter for progress updates
            run_dir: Existing run directory for resume (optional)
        """
        self.base_dir = base_dir or Path("data")
        self.emitter = emitter
        self._run_dir = run_dir

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

    def _get_checkpoint_dir(self, run_dir: Path) -> Path:
        """Get or create checkpoint directory for a run."""
        checkpoint_dir = run_dir / "checkpoints"
        checkpoint_dir.mkdir(exist_ok=True)
        return checkpoint_dir

    def _checkpoint_path(self, run_dir: Path, stage_name: str) -> Path:
        """Get path to checkpoint file for a stage."""
        return self._get_checkpoint_dir(run_dir) / f"{stage_name}.pkl"

    def _save_checkpoint(self, run_dir: Path, stage_name: str, output: Any) -> None:
        """Save stage output to disk for crash recovery.

        Args:
            run_dir: The run directory
            stage_name: Name of the completed stage
            output: Output data to checkpoint
        """
        path = self._checkpoint_path(run_dir, stage_name)
        try:
            with open(path, "wb") as f:
                pickle.dump(
                    {
                        "output": output,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "stage": stage_name,
                    },
                    f,
                )
            logger.info(f"Checkpoint saved: {stage_name}")
        except (OSError, pickle.PicklingError) as e:
            logger.warning(f"Failed to save checkpoint for {stage_name}: {e}")
            # Non-fatal - continue without checkpoint

    def _load_checkpoint(self, run_dir: Path, stage_name: str) -> Any | None:
        """Load stage output from disk if exists.

        Args:
            run_dir: The run directory
            stage_name: Name of the stage to load

        Returns:
            The stage output, or None if no valid checkpoint exists
        """
        path = self._checkpoint_path(run_dir, stage_name)
        if not path.exists():
            return None

        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
                # Validate checkpoint data
                if data.get("stage") != stage_name:
                    logger.warning(
                        f"Checkpoint mismatch: expected {stage_name}, "
                        f"got {data.get('stage')}"
                    )
                    return None
                logger.info(f"Checkpoint loaded: {stage_name}")
                return data["output"]
        except (OSError, pickle.UnpicklingError, KeyError) as e:
            logger.warning(f"Corrupted checkpoint {stage_name}: {e}")
            # Delete corrupted file
            try:
                path.unlink()
            except OSError:
                pass
            return None

    def run(
        self,
        procedure_title: str,
        resume_from: str | None = None,
    ) -> "PackageReleaseOutput":
        """Run the full pipeline with optional checkpoint resume.

        Args:
            procedure_title: The title of the procedure to generate
            resume_from: Optional stage name to resume from (R4-002).
                        Requires run_dir to be set in constructor.

        Returns:
            The final PackageReleaseOutput

        Raises:
            ValueError: If procedure_title is empty or resume has no checkpoint
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

        if resume_from:
            logger.info(f"Resuming pipeline from stage '{resume_from}' for: {procedure_title}")
        else:
            logger.info(f"Starting pipeline for: {procedure_title}")

        return self._execute_stages(procedure_title, resume_from=resume_from)

    def _execute_stages(
        self,
        procedure_title: str,
        resume_from: str | None = None,
    ) -> "PackageReleaseOutput":
        """Execute all stages in sequence with checkpoint support.

        Args:
            procedure_title: The procedure title
            resume_from: Optional stage name to resume from (R4-002)

        Returns:
            The final output from PackageRelease stage

        Raises:
            PipelineError: If any stage fails
            ValueError: If resume_from stage has no checkpoint
        """
        # Generate run ID or use existing from resume
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
        run_dir: Path | None = None
        skip_until_found = resume_from is not None

        for stage in self.stages:
            # Resume logic (R4-002)
            if skip_until_found:
                if stage.name == resume_from:
                    skip_until_found = False
                    # We need run_dir to load checkpoint
                    if self._run_dir is None:
                        raise ValueError(
                            f"Cannot resume: run_dir not provided for checkpoint loading"
                        )
                    run_dir = self._run_dir
                    current_output = self._load_checkpoint(run_dir, stage.name)
                    if current_output is None:
                        raise ValueError(f"No valid checkpoint for stage '{stage.name}'")
                    # Transform to next stage input
                    current_input = self._transform_output_to_input(
                        stage.name,
                        current_output,
                    )
                    logger.info(f"Resumed from checkpoint: {stage.name}")
                continue

            try:
                logger.info(f"Executing stage: {stage.name}")

                # Add emitter to input if it has that field
                if hasattr(current_input, "emitter"):
                    object.__setattr__(current_input, "emitter", self.emitter)

                current_output = stage.execute(current_input)

                # Get run_dir from output if available
                if hasattr(current_output, "run_dir"):
                    run_dir = current_output.run_dir

                # Save checkpoint after successful stage execution (R4-002)
                if run_dir is not None:
                    self._save_checkpoint(run_dir, stage.name, current_output)

                # Transform output to next input
                current_input = self._transform_output_to_input(
                    stage.name,
                    current_output,
                )

            except Exception as e:
                logger.error(f"Stage {stage.name} failed: {e}")
                resume_hint = (
                    f"Resume with: resume_from='{stage.name}'" if run_dir else ""
                )
                raise PipelineError(
                    message=f"{e}. {resume_hint}",
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
