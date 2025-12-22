"""Tests for Stage 03: Chunk.

The Chunk stage splits source content into evidence chunks:
1. Reads raw content from sources
2. Splits into semantically meaningful chunks
3. Creates EvidenceChunk objects with metadata
4. Outputs chunks for evidence notes extraction
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    pass


class TestChunkStage:
    """Tests for Stage 03: Chunk."""

    def test_chunk_stage_name_is_chunk(self) -> None:
        """Chunk stage should identify itself as 'chunk'."""
        from procedurewriter.pipeline.stages.s03_chunk import ChunkStage

        stage = ChunkStage()
        assert stage.name == "chunk"

    def test_chunk_input_requires_sources(self) -> None:
        """Chunk input must have sources field."""
        from procedurewriter.pipeline.stages.s03_chunk import ChunkInput

        input_data = ChunkInput(
            run_id="test-run",
            run_dir=Path("/tmp/test"),
            procedure_title="Test",
            sources=[],
            raw_content_dir=Path("/tmp/test/raw"),
        )
        assert input_data.sources == []

    def test_chunk_output_has_chunks_list(self, tmp_path: Path) -> None:
        """Chunk output should contain a list of chunks."""
        from procedurewriter.pipeline.stages.s03_chunk import (
            ChunkInput,
            ChunkStage,
            SourceInfo,
        )

        stage = ChunkStage()
        run_dir = tmp_path / "runs" / "test-run"
        raw_dir = run_dir / "raw"
        raw_dir.mkdir(parents=True)

        # Create a source with content
        source = SourceInfo(
            source_id="src_001",
            title="Test Source",
            source_type="guideline",
        )
        source_file = raw_dir / "src_001.json"
        source_file.write_text(json.dumps({
            "source_id": "src_001",
            "title": "Test Source",
            "abstract": "This is a test abstract with some content.",
        }))

        input_data = ChunkInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            sources=[source],
            raw_content_dir=raw_dir,
        )

        result = stage.execute(input_data)

        assert hasattr(result, "chunks")
        assert isinstance(result.chunks, list)

    def test_chunk_output_has_all_required_fields(self, tmp_path: Path) -> None:
        """Chunk output should contain all fields needed by EvidenceNotes stage."""
        from procedurewriter.pipeline.stages.s03_chunk import (
            ChunkInput,
            ChunkStage,
        )

        stage = ChunkStage()
        run_dir = tmp_path / "runs" / "test-run"
        raw_dir = run_dir / "raw"
        raw_dir.mkdir(parents=True)

        input_data = ChunkInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            sources=[],
            raw_content_dir=raw_dir,
        )

        result = stage.execute(input_data)

        assert hasattr(result, "run_id")
        assert hasattr(result, "run_dir")
        assert hasattr(result, "procedure_title")
        assert hasattr(result, "chunks")
        assert hasattr(result, "total_chunks")
        assert result.run_id == "test-run"

    def test_chunk_creates_evidence_chunks_from_source(self, tmp_path: Path) -> None:
        """Chunk should create EvidenceChunk objects from source content."""
        from procedurewriter.pipeline.stages.s03_chunk import (
            ChunkInput,
            ChunkStage,
            SourceInfo,
        )

        stage = ChunkStage()
        run_dir = tmp_path / "runs" / "test-run"
        raw_dir = run_dir / "raw"
        raw_dir.mkdir(parents=True)

        # Create a source with substantial content
        source = SourceInfo(
            source_id="src_001",
            title="Test Source",
            source_type="guideline",
        )
        content = "This is the first paragraph of content. " * 10
        content += "\n\nThis is the second paragraph with different information. " * 10

        source_file = raw_dir / "src_001.json"
        source_file.write_text(json.dumps({
            "source_id": "src_001",
            "title": "Test Source",
            "abstract": content,
        }))

        input_data = ChunkInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            sources=[source],
            raw_content_dir=raw_dir,
        )

        result = stage.execute(input_data)

        assert len(result.chunks) >= 1
        # Each chunk should have required fields
        for chunk in result.chunks:
            assert chunk.source_id == "src_001"
            assert chunk.run_id == "test-run"
            assert len(chunk.text) > 0

    def test_chunk_assigns_sequential_indices(self, tmp_path: Path) -> None:
        """Chunks from same source should have sequential indices."""
        from procedurewriter.pipeline.stages.s03_chunk import (
            ChunkInput,
            ChunkStage,
            SourceInfo,
        )

        stage = ChunkStage()
        run_dir = tmp_path / "runs" / "test-run"
        raw_dir = run_dir / "raw"
        raw_dir.mkdir(parents=True)

        # Create content that will produce multiple chunks
        source = SourceInfo(
            source_id="src_001",
            title="Test Source",
            source_type="guideline",
        )
        # Long content to force multiple chunks
        paragraphs = [f"Paragraph {i}. " * 50 for i in range(5)]
        content = "\n\n".join(paragraphs)

        source_file = raw_dir / "src_001.json"
        source_file.write_text(json.dumps({
            "source_id": "src_001",
            "title": "Test Source",
            "abstract": content,
        }))

        input_data = ChunkInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            sources=[source],
            raw_content_dir=raw_dir,
            chunk_size=200,  # Small chunks
        )

        result = stage.execute(input_data)

        # Get chunks for this source
        source_chunks = [c for c in result.chunks if c.source_id == "src_001"]

        if len(source_chunks) > 1:
            indices = [c.chunk_index for c in source_chunks]
            assert indices == list(range(len(source_chunks)))

    def test_chunk_emits_progress_event(self, tmp_path: Path) -> None:
        """Chunk should emit a progress event when starting."""
        from procedurewriter.pipeline.stages.s03_chunk import (
            ChunkInput,
            ChunkStage,
        )

        mock_emitter = MagicMock()
        stage = ChunkStage()
        run_dir = tmp_path / "runs" / "test-run"
        raw_dir = run_dir / "raw"
        raw_dir.mkdir(parents=True)

        input_data = ChunkInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            sources=[],
            raw_content_dir=raw_dir,
            emitter=mock_emitter,
        )

        stage.execute(input_data)

        mock_emitter.emit.assert_called()

    def test_chunk_handles_empty_sources(self, tmp_path: Path) -> None:
        """Chunk should handle case where no sources are provided."""
        from procedurewriter.pipeline.stages.s03_chunk import (
            ChunkInput,
            ChunkStage,
        )

        stage = ChunkStage()
        run_dir = tmp_path / "runs" / "test-run"
        raw_dir = run_dir / "raw"
        raw_dir.mkdir(parents=True)

        input_data = ChunkInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            sources=[],
            raw_content_dir=raw_dir,
        )

        result = stage.execute(input_data)

        assert result.chunks == []
        assert result.total_chunks == 0

    def test_chunk_handles_missing_source_file(self, tmp_path: Path) -> None:
        """Chunk should handle case where source file doesn't exist."""
        from procedurewriter.pipeline.stages.s03_chunk import (
            ChunkInput,
            ChunkStage,
            SourceInfo,
        )

        stage = ChunkStage()
        run_dir = tmp_path / "runs" / "test-run"
        raw_dir = run_dir / "raw"
        raw_dir.mkdir(parents=True)

        # Source without corresponding file
        source = SourceInfo(
            source_id="missing_001",
            title="Missing Source",
            source_type="guideline",
        )

        input_data = ChunkInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            sources=[source],
            raw_content_dir=raw_dir,
        )

        # Should not crash
        result = stage.execute(input_data)
        assert isinstance(result.chunks, list)

    def test_chunk_respects_chunk_size_config(self, tmp_path: Path) -> None:
        """Chunk should respect chunk_size configuration."""
        from procedurewriter.pipeline.stages.s03_chunk import (
            ChunkInput,
            ChunkStage,
            SourceInfo,
        )

        stage = ChunkStage()
        run_dir = tmp_path / "runs" / "test-run"
        raw_dir = run_dir / "raw"
        raw_dir.mkdir(parents=True)

        source = SourceInfo(
            source_id="src_001",
            title="Test Source",
            source_type="guideline",
        )
        # Create content longer than chunk size
        content = "Word " * 500  # 2500 chars

        source_file = raw_dir / "src_001.json"
        source_file.write_text(json.dumps({
            "source_id": "src_001",
            "abstract": content,
        }))

        input_data = ChunkInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            sources=[source],
            raw_content_dir=raw_dir,
            chunk_size=500,  # 500 char chunks
        )

        result = stage.execute(input_data)

        # Should have multiple chunks
        assert len(result.chunks) > 1
        # Each chunk should be around chunk_size (with overlap buffer)
        for chunk in result.chunks:
            assert len(chunk.text) <= 600  # chunk_size + overlap

    def test_chunk_tracks_total_chunks_count(self, tmp_path: Path) -> None:
        """Chunk output should track total number of chunks created."""
        from procedurewriter.pipeline.stages.s03_chunk import (
            ChunkInput,
            ChunkStage,
            SourceInfo,
        )

        stage = ChunkStage()
        run_dir = tmp_path / "runs" / "test-run"
        raw_dir = run_dir / "raw"
        raw_dir.mkdir(parents=True)

        # Create two sources
        for i in range(2):
            source_file = raw_dir / f"src_00{i}.json"
            source_file.write_text(json.dumps({
                "source_id": f"src_00{i}",
                "abstract": f"Content for source {i}. " * 20,
            }))

        sources = [
            SourceInfo(source_id="src_000", title="Source 0", source_type="guideline"),
            SourceInfo(source_id="src_001", title="Source 1", source_type="review"),
        ]

        input_data = ChunkInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            sources=sources,
            raw_content_dir=raw_dir,
        )

        result = stage.execute(input_data)

        assert result.total_chunks == len(result.chunks)

    def test_chunk_passes_through_run_dir(self, tmp_path: Path) -> None:
        """Chunk should pass through run_dir for subsequent stages."""
        from procedurewriter.pipeline.stages.s03_chunk import (
            ChunkInput,
            ChunkStage,
        )

        stage = ChunkStage()
        run_dir = tmp_path / "runs" / "test-run"
        raw_dir = run_dir / "raw"
        raw_dir.mkdir(parents=True)

        input_data = ChunkInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            sources=[],
            raw_content_dir=raw_dir,
        )

        result = stage.execute(input_data)

        assert result.run_dir == run_dir

    def test_chunk_includes_source_metadata(self, tmp_path: Path) -> None:
        """Chunk metadata should include source information."""
        from procedurewriter.pipeline.stages.s03_chunk import (
            ChunkInput,
            ChunkStage,
            SourceInfo,
        )

        stage = ChunkStage()
        run_dir = tmp_path / "runs" / "test-run"
        raw_dir = run_dir / "raw"
        raw_dir.mkdir(parents=True)

        source = SourceInfo(
            source_id="src_001",
            title="Important Guideline",
            source_type="danish_guideline",
        )
        source_file = raw_dir / "src_001.json"
        source_file.write_text(json.dumps({
            "source_id": "src_001",
            "title": "Important Guideline",
            "abstract": "This is important content for the guideline.",
        }))

        input_data = ChunkInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            sources=[source],
            raw_content_dir=raw_dir,
        )

        result = stage.execute(input_data)

        assert len(result.chunks) >= 1
        chunk = result.chunks[0]
        assert chunk.metadata.get("source_title") == "Important Guideline"
        assert chunk.metadata.get("source_type") == "danish_guideline"
