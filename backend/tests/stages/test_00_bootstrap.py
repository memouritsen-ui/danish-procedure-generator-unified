"""Tests for Stage 00: Bootstrap.

The Bootstrap stage initializes a pipeline run by:
1. Creating the run directory structure (raw, normalized, index subdirs)
2. Emitting a pipeline start event
3. Resetting the session cost tracker
4. Loading required config files (author_guide, allowlist, evidence_hierarchy)
"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    pass


class TestPipelineStageBase:
    """Tests for the PipelineStage abstract base class."""

    def test_stage_has_name_property(self) -> None:
        """Every stage must have a name for logging and events."""
        from procedurewriter.pipeline.stages.base import PipelineStage

        # PipelineStage is abstract, so we need to check the interface
        assert hasattr(PipelineStage, "name")

    def test_stage_has_execute_method(self) -> None:
        """Every stage must have an execute method."""
        from procedurewriter.pipeline.stages.base import PipelineStage

        assert hasattr(PipelineStage, "execute")

    def test_cannot_instantiate_abstract_stage(self) -> None:
        """PipelineStage is abstract and cannot be instantiated directly."""
        from procedurewriter.pipeline.stages.base import PipelineStage

        with pytest.raises(TypeError, match="abstract"):
            PipelineStage()  # type: ignore[abstract]


class TestBootstrapStage:
    """Tests for Stage 00: Bootstrap."""

    def test_bootstrap_stage_name_is_bootstrap(self) -> None:
        """Bootstrap stage should identify itself as 'bootstrap'."""
        from procedurewriter.pipeline.stages.s00_bootstrap import BootstrapStage

        stage = BootstrapStage()
        assert stage.name == "bootstrap"

    def test_bootstrap_creates_run_directory(self, tmp_path: Path) -> None:
        """Bootstrap should create the run directory."""
        from procedurewriter.pipeline.stages.s00_bootstrap import (
            BootstrapInput,
            BootstrapStage,
        )

        run_id = str(uuid.uuid4())
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()

        stage = BootstrapStage()
        input_data = BootstrapInput(
            run_id=run_id,
            runs_dir=runs_dir,
            author_guide_path=None,
            allowlist_path=None,
            evidence_hierarchy_path=None,
        )

        result = stage.execute(input_data)

        expected_run_dir = runs_dir / run_id
        assert expected_run_dir.exists()
        assert result.run_dir == expected_run_dir

    def test_bootstrap_creates_subdirectories(self, tmp_path: Path) -> None:
        """Bootstrap should create raw, normalized, and index subdirectories."""
        from procedurewriter.pipeline.stages.s00_bootstrap import (
            BootstrapInput,
            BootstrapStage,
        )

        run_id = str(uuid.uuid4())
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()

        stage = BootstrapStage()
        input_data = BootstrapInput(
            run_id=run_id,
            runs_dir=runs_dir,
            author_guide_path=None,
            allowlist_path=None,
            evidence_hierarchy_path=None,
        )

        result = stage.execute(input_data)

        run_dir = result.run_dir
        assert (run_dir / "raw").exists()
        assert (run_dir / "normalized").exists()
        assert (run_dir / "index").exists()

    def test_bootstrap_emits_progress_event(self, tmp_path: Path) -> None:
        """Bootstrap should emit a progress event when starting."""
        from procedurewriter.pipeline.stages.s00_bootstrap import (
            BootstrapInput,
            BootstrapStage,
        )

        run_id = str(uuid.uuid4())
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()

        mock_emitter = MagicMock()

        stage = BootstrapStage()
        input_data = BootstrapInput(
            run_id=run_id,
            runs_dir=runs_dir,
            author_guide_path=None,
            allowlist_path=None,
            evidence_hierarchy_path=None,
            emitter=mock_emitter,
        )

        stage.execute(input_data)

        # Verify emitter was called with progress event
        mock_emitter.emit.assert_called()
        call_args = mock_emitter.emit.call_args_list[0]
        # First positional arg should be event type
        assert call_args[0][0].value == "progress" or "PROGRESS" in str(call_args[0][0])

    def test_bootstrap_resets_session_tracker(self, tmp_path: Path) -> None:
        """Bootstrap should reset the session cost tracker."""
        from procedurewriter.pipeline.stages.s00_bootstrap import (
            BootstrapInput,
            BootstrapStage,
        )

        run_id = str(uuid.uuid4())
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()

        stage = BootstrapStage()
        input_data = BootstrapInput(
            run_id=run_id,
            runs_dir=runs_dir,
            author_guide_path=None,
            allowlist_path=None,
            evidence_hierarchy_path=None,
        )

        with patch(
            "procedurewriter.pipeline.stages.s00_bootstrap.reset_session_tracker"
        ) as mock_reset:
            stage.execute(input_data)
            mock_reset.assert_called_once()

    def test_bootstrap_loads_author_guide_when_path_provided(
        self, tmp_path: Path
    ) -> None:
        """Bootstrap should load author guide config when path is provided."""
        from procedurewriter.pipeline.stages.s00_bootstrap import (
            BootstrapInput,
            BootstrapStage,
        )

        run_id = str(uuid.uuid4())
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()

        # Create a mock author guide file
        author_guide_path = tmp_path / "author_guide.yaml"
        author_guide_path.write_text("style:\n  tone: formal\n")

        stage = BootstrapStage()
        input_data = BootstrapInput(
            run_id=run_id,
            runs_dir=runs_dir,
            author_guide_path=author_guide_path,
            allowlist_path=None,
            evidence_hierarchy_path=None,
        )

        result = stage.execute(input_data)

        assert result.author_guide is not None
        assert result.author_guide["style"]["tone"] == "formal"

    def test_bootstrap_output_contains_all_required_fields(
        self, tmp_path: Path
    ) -> None:
        """Bootstrap output should contain all fields needed by subsequent stages."""
        from procedurewriter.pipeline.stages.s00_bootstrap import (
            BootstrapInput,
            BootstrapStage,
        )

        run_id = str(uuid.uuid4())
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()

        stage = BootstrapStage()
        input_data = BootstrapInput(
            run_id=run_id,
            runs_dir=runs_dir,
            author_guide_path=None,
            allowlist_path=None,
            evidence_hierarchy_path=None,
        )

        result = stage.execute(input_data)

        # Check all required output fields exist
        assert hasattr(result, "run_id")
        assert hasattr(result, "run_dir")
        assert hasattr(result, "author_guide")
        assert hasattr(result, "allowlist")
        assert hasattr(result, "evidence_hierarchy")
        assert result.run_id == run_id

    def test_bootstrap_loads_allowlist_when_path_provided(
        self, tmp_path: Path
    ) -> None:
        """Bootstrap should load allowlist config when path is provided."""
        from procedurewriter.pipeline.stages.s00_bootstrap import (
            BootstrapInput,
            BootstrapStage,
        )

        run_id = str(uuid.uuid4())
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()

        # Create a mock allowlist file
        allowlist_path = tmp_path / "allowlist.yaml"
        allowlist_path.write_text("version: '1.0'\nallowed:\n  - example.com\n")

        stage = BootstrapStage()
        input_data = BootstrapInput(
            run_id=run_id,
            runs_dir=runs_dir,
            author_guide_path=None,
            allowlist_path=allowlist_path,
            evidence_hierarchy_path=None,
        )

        result = stage.execute(input_data)

        assert result.allowlist is not None
        assert result.allowlist["version"] == "1.0"

    def test_bootstrap_with_missing_config_path_returns_none(
        self, tmp_path: Path
    ) -> None:
        """Bootstrap with None config paths should set output to None."""
        from procedurewriter.pipeline.stages.s00_bootstrap import (
            BootstrapInput,
            BootstrapStage,
        )

        run_id = str(uuid.uuid4())
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()

        stage = BootstrapStage()
        input_data = BootstrapInput(
            run_id=run_id,
            runs_dir=runs_dir,
            author_guide_path=None,
            allowlist_path=None,
            evidence_hierarchy_path=None,
        )

        result = stage.execute(input_data)

        assert result.author_guide is None
        assert result.allowlist is None
