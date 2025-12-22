"""Tests for Stage 04: EvidenceNotes.

The EvidenceNotes stage uses LLM to summarize evidence chunks:
1. Receives chunks from Stage 03 (Chunk)
2. Calls LLM to generate clinical notes for each chunk
3. Creates EvidenceNote objects with structured summaries
4. Outputs notes for Draft stage to use
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from procedurewriter.models.evidence import EvidenceChunk

if TYPE_CHECKING:
    pass


class TestEvidenceNotesStage:
    """Tests for Stage 04: EvidenceNotes."""

    def test_evidencenotes_stage_name_is_evidencenotes(self) -> None:
        """EvidenceNotes stage should identify itself as 'evidencenotes'."""
        from procedurewriter.pipeline.stages.s04_evidencenotes import EvidenceNotesStage

        stage = EvidenceNotesStage()
        assert stage.name == "evidencenotes"

    def test_evidencenotes_input_requires_chunks(self) -> None:
        """EvidenceNotes input must have chunks field."""
        from procedurewriter.pipeline.stages.s04_evidencenotes import EvidenceNotesInput

        input_data = EvidenceNotesInput(
            run_id="test-run",
            run_dir=Path("/tmp/test"),
            procedure_title="Test Procedure",
            chunks=[],
        )
        assert input_data.chunks == []

    def test_evidencenotes_output_has_notes_list(self, tmp_path: Path) -> None:
        """EvidenceNotes output should contain a list of notes."""
        from procedurewriter.pipeline.stages.s04_evidencenotes import (
            EvidenceNotesInput,
            EvidenceNotesStage,
        )

        # Mock LLM client
        mock_llm = MagicMock()
        mock_llm.chat_completion.return_value = MagicMock(
            content="Clinical summary of evidence.",
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
        )

        stage = EvidenceNotesStage(llm_client=mock_llm)
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = EvidenceNotesInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            chunks=[],
        )

        result = stage.execute(input_data)

        assert hasattr(result, "notes")
        assert isinstance(result.notes, list)

    def test_evidencenotes_output_has_all_required_fields(self, tmp_path: Path) -> None:
        """EvidenceNotes output should contain all fields needed by Draft stage."""
        from procedurewriter.pipeline.stages.s04_evidencenotes import (
            EvidenceNotesInput,
            EvidenceNotesStage,
        )

        mock_llm = MagicMock()
        mock_llm.chat_completion.return_value = MagicMock(
            content="Summary",
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
        )

        stage = EvidenceNotesStage(llm_client=mock_llm)
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = EvidenceNotesInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            chunks=[],
        )

        result = stage.execute(input_data)

        assert hasattr(result, "run_id")
        assert hasattr(result, "run_dir")
        assert hasattr(result, "procedure_title")
        assert hasattr(result, "notes")
        assert hasattr(result, "total_notes")
        assert result.run_id == "test-run"

    def test_evidencenotes_creates_notes_from_chunks(self, tmp_path: Path) -> None:
        """EvidenceNotes should create note objects from evidence chunks."""
        from procedurewriter.pipeline.stages.s04_evidencenotes import (
            EvidenceNotesInput,
            EvidenceNotesStage,
        )

        mock_llm = MagicMock()
        mock_llm.chat_completion.return_value = MagicMock(
            content="Key finding: Antibiotic treatment recommended within 4 hours.",
            input_tokens=100,
            output_tokens=20,
            total_tokens=120,
        )

        stage = EvidenceNotesStage(llm_client=mock_llm)
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        # Create a chunk to process
        chunk = EvidenceChunk(
            run_id="test-run",
            source_id="src_001",
            text="Early antibiotic treatment within 4 hours improves outcomes in community-acquired pneumonia.",
            chunk_index=0,
            metadata={"source_title": "CAP Guidelines"},
        )

        input_data = EvidenceNotesInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Pneumonia Treatment",
            chunks=[chunk],
        )

        result = stage.execute(input_data)

        assert len(result.notes) == 1
        assert result.notes[0].chunk_id == chunk.id
        assert len(result.notes[0].summary) > 0

    def test_evidencenotes_calls_llm_for_each_chunk(self, tmp_path: Path) -> None:
        """EvidenceNotes should call LLM once per chunk."""
        from procedurewriter.pipeline.stages.s04_evidencenotes import (
            EvidenceNotesInput,
            EvidenceNotesStage,
        )

        mock_llm = MagicMock()
        mock_llm.chat_completion.return_value = MagicMock(
            content="Summary",
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
        )

        stage = EvidenceNotesStage(llm_client=mock_llm)
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        # Create 3 chunks
        chunks = [
            EvidenceChunk(
                run_id="test-run",
                source_id=f"src_{i:03d}",
                text=f"Evidence text {i}",
                chunk_index=0,
            )
            for i in range(3)
        ]

        input_data = EvidenceNotesInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test",
            chunks=chunks,
        )

        stage.execute(input_data)

        assert mock_llm.chat_completion.call_count == 3

    def test_evidencenotes_emits_progress_event(self, tmp_path: Path) -> None:
        """EvidenceNotes should emit a progress event when starting."""
        from procedurewriter.pipeline.stages.s04_evidencenotes import (
            EvidenceNotesInput,
            EvidenceNotesStage,
        )

        mock_llm = MagicMock()
        mock_llm.chat_completion.return_value = MagicMock(
            content="Summary",
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
        )

        mock_emitter = MagicMock()
        stage = EvidenceNotesStage(llm_client=mock_llm)
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = EvidenceNotesInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            chunks=[],
            emitter=mock_emitter,
        )

        stage.execute(input_data)

        mock_emitter.emit.assert_called()

    def test_evidencenotes_handles_empty_chunks(self, tmp_path: Path) -> None:
        """EvidenceNotes should handle case where no chunks are provided."""
        from procedurewriter.pipeline.stages.s04_evidencenotes import (
            EvidenceNotesInput,
            EvidenceNotesStage,
        )

        mock_llm = MagicMock()
        stage = EvidenceNotesStage(llm_client=mock_llm)
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = EvidenceNotesInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            chunks=[],
        )

        result = stage.execute(input_data)

        assert result.notes == []
        assert result.total_notes == 0
        # LLM should not be called with no chunks
        mock_llm.chat_completion.assert_not_called()

    def test_evidencenotes_handles_llm_error_gracefully(self, tmp_path: Path) -> None:
        """EvidenceNotes should handle LLM errors without crashing."""
        from procedurewriter.pipeline.stages.s04_evidencenotes import (
            EvidenceNotesInput,
            EvidenceNotesStage,
        )

        mock_llm = MagicMock()
        mock_llm.chat_completion.side_effect = Exception("API rate limit exceeded")

        stage = EvidenceNotesStage(llm_client=mock_llm)
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        chunk = EvidenceChunk(
            run_id="test-run",
            source_id="src_001",
            text="Test content",
            chunk_index=0,
        )

        input_data = EvidenceNotesInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            chunks=[chunk],
        )

        # Should not raise
        result = stage.execute(input_data)
        assert isinstance(result.notes, list)

    def test_evidencenotes_passes_through_run_dir(self, tmp_path: Path) -> None:
        """EvidenceNotes should pass through run_dir for subsequent stages."""
        from procedurewriter.pipeline.stages.s04_evidencenotes import (
            EvidenceNotesInput,
            EvidenceNotesStage,
        )

        mock_llm = MagicMock()
        mock_llm.chat_completion.return_value = MagicMock(
            content="Summary",
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
        )

        stage = EvidenceNotesStage(llm_client=mock_llm)
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = EvidenceNotesInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            chunks=[],
        )

        result = stage.execute(input_data)

        assert result.run_dir == run_dir

    def test_evidencenotes_includes_chunk_metadata_in_prompt(
        self, tmp_path: Path
    ) -> None:
        """EvidenceNotes should include chunk metadata when prompting LLM."""
        from procedurewriter.pipeline.stages.s04_evidencenotes import (
            EvidenceNotesInput,
            EvidenceNotesStage,
        )

        mock_llm = MagicMock()
        mock_llm.chat_completion.return_value = MagicMock(
            content="Summary",
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
        )

        stage = EvidenceNotesStage(llm_client=mock_llm)
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        chunk = EvidenceChunk(
            run_id="test-run",
            source_id="src_001",
            text="Clinical content here",
            chunk_index=0,
            metadata={"source_title": "Danish Guidelines 2024", "source_type": "danish_guideline"},
        )

        input_data = EvidenceNotesInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            chunks=[chunk],
        )

        stage.execute(input_data)

        # Check that the prompt includes source info
        call_args = mock_llm.chat_completion.call_args
        messages = call_args.kwargs.get("messages") or call_args[0][0]
        prompt_text = str(messages)
        assert "Danish Guidelines 2024" in prompt_text or "Clinical content" in prompt_text

    def test_evidencenotes_tracks_total_notes_count(self, tmp_path: Path) -> None:
        """EvidenceNotes output should track total number of notes created."""
        from procedurewriter.pipeline.stages.s04_evidencenotes import (
            EvidenceNotesInput,
            EvidenceNotesStage,
        )

        mock_llm = MagicMock()
        mock_llm.chat_completion.return_value = MagicMock(
            content="Summary",
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
        )

        stage = EvidenceNotesStage(llm_client=mock_llm)
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        chunks = [
            EvidenceChunk(
                run_id="test-run",
                source_id=f"src_{i:03d}",
                text=f"Evidence text {i}",
                chunk_index=0,
            )
            for i in range(5)
        ]

        input_data = EvidenceNotesInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            chunks=chunks,
        )

        result = stage.execute(input_data)

        assert result.total_notes == len(result.notes)

    def test_evidencenotes_uses_configurable_model(self, tmp_path: Path) -> None:
        """EvidenceNotes should use configurable LLM model."""
        from procedurewriter.pipeline.stages.s04_evidencenotes import (
            EvidenceNotesInput,
            EvidenceNotesStage,
        )

        mock_llm = MagicMock()
        mock_llm.chat_completion.return_value = MagicMock(
            content="Summary",
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
        )

        stage = EvidenceNotesStage(llm_client=mock_llm)
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        chunk = EvidenceChunk(
            run_id="test-run",
            source_id="src_001",
            text="Test content",
            chunk_index=0,
        )

        input_data = EvidenceNotesInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            chunks=[chunk],
            model="gpt-4o-mini",  # Use cheaper model
        )

        stage.execute(input_data)

        call_args = mock_llm.chat_completion.call_args
        assert call_args.kwargs.get("model") == "gpt-4o-mini"
