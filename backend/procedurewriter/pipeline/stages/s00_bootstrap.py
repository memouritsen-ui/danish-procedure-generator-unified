"""Stage 00: Bootstrap - Initialize pipeline run.

The Bootstrap stage prepares the run environment by:
1. Creating the run directory structure (raw, normalized, index subdirs)
2. Emitting a pipeline start event
3. Resetting the session cost tracker
4. Loading required config files (author_guide, allowlist, evidence_hierarchy)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from procedurewriter.llm.cost_tracker import reset_session_tracker
from procedurewriter.pipeline.events import EventType
from procedurewriter.pipeline.stages.base import PipelineStage

if TYPE_CHECKING:
    from procedurewriter.pipeline.events import EventEmitter


def load_yaml(path: Path | None) -> dict[str, Any] | None:
    """Load a YAML file and return its contents as a dict.

    Args:
        path: Path to the YAML file, or None

    Returns:
        The parsed YAML as a dict, or None if path is None
    """
    if path is None:
        return None

    import yaml

    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass
class BootstrapInput:
    """Input for the Bootstrap stage."""

    run_id: str
    runs_dir: Path
    author_guide_path: Path | None
    allowlist_path: Path | None
    evidence_hierarchy_path: Path | None
    emitter: EventEmitter | None = None


@dataclass
class BootstrapOutput:
    """Output from the Bootstrap stage."""

    run_id: str
    run_dir: Path
    author_guide: dict[str, Any] | None
    allowlist: dict[str, Any] | None
    evidence_hierarchy: Any  # EvidenceHierarchy or None


class BootstrapStage(PipelineStage[BootstrapInput, BootstrapOutput]):
    """Stage 00: Bootstrap - Initialize the pipeline run."""

    @property
    def name(self) -> str:
        """Return the stage name."""
        return "bootstrap"

    def execute(self, input_data: BootstrapInput) -> BootstrapOutput:
        """Execute the bootstrap stage.

        Creates run directories, emits events, resets cost tracker,
        and loads configuration files.

        Args:
            input_data: Bootstrap input containing run_id, paths, etc.

        Returns:
            Bootstrap output with loaded configs and run_dir

        Raises:
            ValueError: If required input fields are missing or invalid (R4-003)
        """
        # R4-003: Input validation
        if not input_data:
            raise ValueError("BootstrapInput is required")

        if not input_data.run_id:
            raise ValueError("run_id is required and cannot be empty")

        if not input_data.run_id.replace("-", "").replace("_", "").isalnum():
            raise ValueError(
                f"run_id must be alphanumeric (with optional - or _): {input_data.run_id}"
            )

        if not input_data.runs_dir:
            raise ValueError("runs_dir is required")

        # Create run directory and subdirectories
        run_dir = input_data.runs_dir / input_data.run_id
        (run_dir / "raw").mkdir(parents=True, exist_ok=True)
        (run_dir / "normalized").mkdir(parents=True, exist_ok=True)
        (run_dir / "index").mkdir(parents=True, exist_ok=True)

        # Emit progress event if emitter provided
        if input_data.emitter is not None:
            input_data.emitter.emit(
                EventType.PROGRESS,
                {"message": "Pipeline starting", "stage": "init"},
            )

        # Reset session cost tracker
        reset_session_tracker()

        # Load configuration files
        author_guide = load_yaml(input_data.author_guide_path)
        allowlist = load_yaml(input_data.allowlist_path)

        # Evidence hierarchy is loaded differently (from its own class)
        evidence_hierarchy = None
        if input_data.evidence_hierarchy_path is not None:
            from procedurewriter.pipeline.evidence_hierarchy import EvidenceHierarchy

            evidence_hierarchy = EvidenceHierarchy.from_config(
                input_data.evidence_hierarchy_path
            )

        return BootstrapOutput(
            run_id=input_data.run_id,
            run_dir=run_dir,
            author_guide=author_guide,
            allowlist=allowlist,
            evidence_hierarchy=evidence_hierarchy,
        )
