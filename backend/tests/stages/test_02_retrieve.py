"""Tests for Stage 02: Retrieve.

The Retrieve stage fetches sources using expanded search terms:
1. Searches multiple tiers (Danish library, NICE, PubMed, Cochrane)
2. Downloads raw source content to run_dir/raw/
3. Returns source references with metadata
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

if TYPE_CHECKING:
    pass


class TestRetrieveStage:
    """Tests for Stage 02: Retrieve."""

    def test_retrieve_stage_name_is_retrieve(self) -> None:
        """Retrieve stage should identify itself as 'retrieve'."""
        from procedurewriter.pipeline.stages.s02_retrieve import RetrieveStage

        stage = RetrieveStage()
        assert stage.name == "retrieve"

    def test_retrieve_input_requires_search_terms(self) -> None:
        """Retrieve input must have search_terms field."""
        from procedurewriter.pipeline.stages.s02_retrieve import RetrieveInput

        input_data = RetrieveInput(
            run_id="test-run",
            run_dir=Path("/tmp/test"),
            procedure_title="Anafylaksi behandling",
            search_terms=["anaphylaxis", "anafylaksi"],
        )
        assert input_data.search_terms == ["anaphylaxis", "anafylaksi"]

    def test_retrieve_output_has_sources_list(self, tmp_path: Path) -> None:
        """Retrieve output should contain a list of sources."""
        from procedurewriter.pipeline.stages.s02_retrieve import (
            RetrieveInput,
            RetrieveOutput,
            RetrieveStage,
        )

        stage = RetrieveStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)
        (run_dir / "raw").mkdir()

        input_data = RetrieveInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            search_terms=["test"],
        )

        with patch.object(stage, "_fetch_sources") as mock_fetch:
            mock_fetch.return_value = []
            result = stage.execute(input_data)

        assert hasattr(result, "sources")
        assert isinstance(result.sources, list)

    def test_retrieve_output_has_all_required_fields(self, tmp_path: Path) -> None:
        """Retrieve output should contain all fields needed by Chunk stage."""
        from procedurewriter.pipeline.stages.s02_retrieve import (
            RetrieveInput,
            RetrieveStage,
        )

        stage = RetrieveStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)
        (run_dir / "raw").mkdir()

        input_data = RetrieveInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            search_terms=["test"],
        )

        with patch.object(stage, "_fetch_sources") as mock_fetch:
            mock_fetch.return_value = []
            result = stage.execute(input_data)

        assert hasattr(result, "run_id")
        assert hasattr(result, "run_dir")
        assert hasattr(result, "procedure_title")
        assert hasattr(result, "sources")
        assert hasattr(result, "raw_content_dir")
        assert result.run_id == "test-run"

    def test_retrieve_creates_raw_content_directory(self, tmp_path: Path) -> None:
        """Retrieve should ensure raw content directory exists."""
        from procedurewriter.pipeline.stages.s02_retrieve import (
            RetrieveInput,
            RetrieveStage,
        )

        stage = RetrieveStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = RetrieveInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            search_terms=["test"],
        )

        with patch.object(stage, "_fetch_sources") as mock_fetch:
            mock_fetch.return_value = []
            result = stage.execute(input_data)

        assert (run_dir / "raw").exists()
        assert result.raw_content_dir == run_dir / "raw"

    def test_retrieve_emits_progress_event(self, tmp_path: Path) -> None:
        """Retrieve should emit a progress event when starting."""
        from procedurewriter.pipeline.stages.s02_retrieve import (
            RetrieveInput,
            RetrieveStage,
        )

        mock_emitter = MagicMock()
        stage = RetrieveStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)
        (run_dir / "raw").mkdir()

        input_data = RetrieveInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            search_terms=["test"],
            emitter=mock_emitter,
        )

        with patch.object(stage, "_fetch_sources") as mock_fetch:
            mock_fetch.return_value = []
            stage.execute(input_data)

        mock_emitter.emit.assert_called()

    def test_retrieve_passes_search_terms_to_fetcher(self, tmp_path: Path) -> None:
        """Retrieve should pass search terms to the fetch function."""
        from procedurewriter.pipeline.stages.s02_retrieve import (
            RetrieveInput,
            RetrieveStage,
        )

        stage = RetrieveStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)
        (run_dir / "raw").mkdir()

        search_terms = ["anaphylaxis treatment", "anafylaksi"]
        input_data = RetrieveInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Anafylaksi behandling",
            search_terms=search_terms,
        )

        with patch.object(stage, "_fetch_sources") as mock_fetch:
            mock_fetch.return_value = []
            stage.execute(input_data)

        mock_fetch.assert_called_once()
        call_args = mock_fetch.call_args
        assert call_args[0][0] == search_terms  # First positional arg

    def test_retrieve_returns_source_references(self, tmp_path: Path) -> None:
        """Retrieve should return SourceReference objects."""
        from procedurewriter.pipeline.stages.s02_retrieve import (
            RetrieveInput,
            RetrieveStage,
            SourceInfo,
        )

        stage = RetrieveStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)
        (run_dir / "raw").mkdir()

        input_data = RetrieveInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            search_terms=["test"],
        )

        mock_source = SourceInfo(
            source_id="src_001",
            title="Test Source",
            url="https://example.com/source",
            source_type="danish_guideline",
        )

        with patch.object(stage, "_fetch_sources") as mock_fetch:
            mock_fetch.return_value = [mock_source]
            result = stage.execute(input_data)

        assert len(result.sources) == 1
        assert result.sources[0].source_id == "src_001"
        assert result.sources[0].title == "Test Source"

    def test_retrieve_handles_empty_search_results(self, tmp_path: Path) -> None:
        """Retrieve should handle case where no sources are found."""
        from procedurewriter.pipeline.stages.s02_retrieve import (
            RetrieveInput,
            RetrieveStage,
        )

        stage = RetrieveStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)
        (run_dir / "raw").mkdir()

        input_data = RetrieveInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Unknown rare condition",
            search_terms=["unknown"],
        )

        with patch.object(stage, "_fetch_sources") as mock_fetch:
            mock_fetch.return_value = []
            result = stage.execute(input_data)

        assert result.sources == []
        assert result.total_sources == 0

    def test_retrieve_tracks_total_sources_count(self, tmp_path: Path) -> None:
        """Retrieve output should track total number of sources found."""
        from procedurewriter.pipeline.stages.s02_retrieve import (
            RetrieveInput,
            RetrieveStage,
            SourceInfo,
        )

        stage = RetrieveStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)
        (run_dir / "raw").mkdir()

        input_data = RetrieveInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            search_terms=["test"],
        )

        mock_sources = [
            SourceInfo(source_id="src_001", title="Source 1", source_type="guideline"),
            SourceInfo(source_id="src_002", title="Source 2", source_type="review"),
            SourceInfo(source_id="src_003", title="Source 3", source_type="rct"),
        ]

        with patch.object(stage, "_fetch_sources") as mock_fetch:
            mock_fetch.return_value = mock_sources
            result = stage.execute(input_data)

        assert result.total_sources == 3

    def test_retrieve_respects_max_sources_limit(self, tmp_path: Path) -> None:
        """Retrieve should respect max_sources configuration."""
        from procedurewriter.pipeline.stages.s02_retrieve import (
            RetrieveInput,
            RetrieveStage,
        )

        stage = RetrieveStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)
        (run_dir / "raw").mkdir()

        input_data = RetrieveInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            search_terms=["test"],
            max_sources=5,
        )

        with patch.object(stage, "_fetch_sources") as mock_fetch:
            mock_fetch.return_value = []
            stage.execute(input_data)

        call_args = mock_fetch.call_args
        # max_sources should be passed to fetcher
        assert call_args[1].get("max_sources") == 5 or call_args[0][1] == 5

    def test_retrieve_passes_through_run_dir(self, tmp_path: Path) -> None:
        """Retrieve should pass through run_dir for subsequent stages."""
        from procedurewriter.pipeline.stages.s02_retrieve import (
            RetrieveInput,
            RetrieveStage,
        )

        stage = RetrieveStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)
        (run_dir / "raw").mkdir()

        input_data = RetrieveInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            search_terms=["test"],
        )

        with patch.object(stage, "_fetch_sources") as mock_fetch:
            mock_fetch.return_value = []
            result = stage.execute(input_data)

        assert result.run_dir == run_dir
