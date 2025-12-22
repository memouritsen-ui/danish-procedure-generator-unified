"""Tests for Stage 05: Draft.

The Draft stage uses WriterAgent to generate procedure content:
1. Receives notes from Stage 04 (EvidenceNotes)
2. Converts notes to source references for Writer
3. Calls WriterAgent to generate structured procedure draft
4. Outputs draft markdown for ClaimExtract stage
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

if TYPE_CHECKING:
    pass


class TestDraftStage:
    """Tests for Stage 05: Draft."""

    def test_draft_stage_name_is_draft(self) -> None:
        """Draft stage should identify itself as 'draft'."""
        from procedurewriter.pipeline.stages.s05_draft import DraftStage

        stage = DraftStage()
        assert stage.name == "draft"

    def test_draft_input_requires_procedure_title(self) -> None:
        """Draft input must have procedure_title field."""
        from procedurewriter.pipeline.stages.s05_draft import DraftInput

        input_data = DraftInput(
            run_id="test-run",
            run_dir=Path("/tmp/test"),
            procedure_title="Test Procedure",
            notes=[],
        )
        assert input_data.procedure_title == "Test Procedure"

    def test_draft_output_has_content_markdown(self, tmp_path: Path) -> None:
        """Draft output should contain markdown content."""
        from procedurewriter.pipeline.stages.s05_draft import (
            DraftInput,
            DraftStage,
            EvidenceNoteRef,
        )

        # Mock WriterAgent
        mock_writer = MagicMock()
        mock_writer.execute.return_value = MagicMock(
            output=MagicMock(
                success=True,
                content_markdown="# Test Procedure\n\n## Indikationer\n- Test content",
                sections=["Test Procedure", "Indikationer"],
                citations_used=["SRC001"],
                word_count=10,
            ),
            stats=MagicMock(),
        )

        stage = DraftStage(writer_agent=mock_writer)
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = DraftInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            notes=[],
        )

        result = stage.execute(input_data)

        assert hasattr(result, "content_markdown")
        assert isinstance(result.content_markdown, str)

    def test_draft_output_has_all_required_fields(self, tmp_path: Path) -> None:
        """Draft output should contain all fields needed by ClaimExtract stage."""
        from procedurewriter.pipeline.stages.s05_draft import (
            DraftInput,
            DraftStage,
        )

        mock_writer = MagicMock()
        mock_writer.execute.return_value = MagicMock(
            output=MagicMock(
                success=True,
                content_markdown="# Draft",
                sections=["Draft"],
                citations_used=[],
                word_count=1,
            ),
            stats=MagicMock(),
        )

        stage = DraftStage(writer_agent=mock_writer)
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = DraftInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            notes=[],
        )

        result = stage.execute(input_data)

        assert hasattr(result, "run_id")
        assert hasattr(result, "run_dir")
        assert hasattr(result, "procedure_title")
        assert hasattr(result, "content_markdown")
        assert hasattr(result, "sections")
        assert hasattr(result, "citations_used")
        assert result.run_id == "test-run"

    def test_draft_calls_writer_agent(self, tmp_path: Path) -> None:
        """Draft should call WriterAgent to generate content."""
        from procedurewriter.pipeline.stages.s05_draft import (
            DraftInput,
            DraftStage,
            EvidenceNoteRef,
        )

        mock_writer = MagicMock()
        mock_writer.execute.return_value = MagicMock(
            output=MagicMock(
                success=True,
                content_markdown="# Content",
                sections=["Content"],
                citations_used=["SRC001"],
                word_count=1,
            ),
            stats=MagicMock(),
        )

        stage = DraftStage(writer_agent=mock_writer)
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        note = EvidenceNoteRef(
            chunk_id=uuid4(),
            source_id="SRC001",
            summary="Key clinical finding",
            source_title="Test Source",
        )

        input_data = DraftInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            notes=[note],
        )

        stage.execute(input_data)

        mock_writer.execute.assert_called_once()

    def test_draft_passes_notes_as_sources(self, tmp_path: Path) -> None:
        """Draft should convert notes to source references for Writer."""
        from procedurewriter.pipeline.stages.s05_draft import (
            DraftInput,
            DraftStage,
            EvidenceNoteRef,
        )

        mock_writer = MagicMock()
        mock_writer.execute.return_value = MagicMock(
            output=MagicMock(
                success=True,
                content_markdown="# Content",
                sections=["Content"],
                citations_used=["SRC001", "SRC002"],
                word_count=10,
            ),
            stats=MagicMock(),
        )

        stage = DraftStage(writer_agent=mock_writer)
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        notes = [
            EvidenceNoteRef(
                chunk_id=uuid4(),
                source_id="SRC001",
                summary="Finding 1",
                source_title="Source One",
            ),
            EvidenceNoteRef(
                chunk_id=uuid4(),
                source_id="SRC002",
                summary="Finding 2",
                source_title="Source Two",
            ),
        ]

        input_data = DraftInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            notes=notes,
        )

        stage.execute(input_data)

        # Check that sources were passed to writer
        call_args = mock_writer.execute.call_args
        writer_input = call_args[0][0]
        assert len(writer_input.sources) == 2

    def test_draft_emits_progress_event(self, tmp_path: Path) -> None:
        """Draft should emit a progress event when starting."""
        from procedurewriter.pipeline.stages.s05_draft import (
            DraftInput,
            DraftStage,
        )

        mock_writer = MagicMock()
        mock_writer.execute.return_value = MagicMock(
            output=MagicMock(
                success=True,
                content_markdown="# Content",
                sections=[],
                citations_used=[],
                word_count=1,
            ),
            stats=MagicMock(),
        )

        mock_emitter = MagicMock()
        stage = DraftStage(writer_agent=mock_writer)
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = DraftInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            notes=[],
            emitter=mock_emitter,
        )

        stage.execute(input_data)

        mock_emitter.emit.assert_called()

    def test_draft_handles_empty_notes(self, tmp_path: Path) -> None:
        """Draft should handle case where no notes are provided."""
        from procedurewriter.pipeline.stages.s05_draft import (
            DraftInput,
            DraftStage,
        )

        mock_writer = MagicMock()
        mock_writer.execute.return_value = MagicMock(
            output=MagicMock(
                success=True,
                content_markdown="# Minimal draft",
                sections=["Minimal draft"],
                citations_used=[],
                word_count=2,
            ),
            stats=MagicMock(),
        )

        stage = DraftStage(writer_agent=mock_writer)
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = DraftInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            notes=[],
        )

        result = stage.execute(input_data)

        # Should still produce output
        assert result.content_markdown != ""

    def test_draft_handles_writer_error(self, tmp_path: Path) -> None:
        """Draft should handle WriterAgent errors gracefully."""
        from procedurewriter.pipeline.stages.s05_draft import (
            DraftInput,
            DraftStage,
        )

        mock_writer = MagicMock()
        mock_writer.execute.return_value = MagicMock(
            output=MagicMock(
                success=False,
                error="LLM error",
                content_markdown="",
                sections=[],
                citations_used=[],
                word_count=0,
            ),
            stats=MagicMock(),
        )

        stage = DraftStage(writer_agent=mock_writer)
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = DraftInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            notes=[],
        )

        # Should not raise
        result = stage.execute(input_data)
        assert hasattr(result, "error")

    def test_draft_passes_through_run_dir(self, tmp_path: Path) -> None:
        """Draft should pass through run_dir for subsequent stages."""
        from procedurewriter.pipeline.stages.s05_draft import (
            DraftInput,
            DraftStage,
        )

        mock_writer = MagicMock()
        mock_writer.execute.return_value = MagicMock(
            output=MagicMock(
                success=True,
                content_markdown="# Content",
                sections=[],
                citations_used=[],
                word_count=1,
            ),
            stats=MagicMock(),
        )

        stage = DraftStage(writer_agent=mock_writer)
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = DraftInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            notes=[],
        )

        result = stage.execute(input_data)

        assert result.run_dir == run_dir

    def test_draft_uses_outline_config(self, tmp_path: Path) -> None:
        """Draft should use outline configuration when provided."""
        from procedurewriter.pipeline.stages.s05_draft import (
            DraftInput,
            DraftStage,
        )

        mock_writer = MagicMock()
        mock_writer.execute.return_value = MagicMock(
            output=MagicMock(
                success=True,
                content_markdown="# Content",
                sections=["Indikationer", "Kontraindikationer"],
                citations_used=[],
                word_count=1,
            ),
            stats=MagicMock(),
        )

        stage = DraftStage(writer_agent=mock_writer)
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        outline = ["Indikationer", "Kontraindikationer", "Udstyr"]

        input_data = DraftInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            notes=[],
            outline=outline,
        )

        stage.execute(input_data)

        call_args = mock_writer.execute.call_args
        writer_input = call_args[0][0]
        assert writer_input.outline == outline

    def test_draft_tracks_word_count(self, tmp_path: Path) -> None:
        """Draft output should track word count from writer."""
        from procedurewriter.pipeline.stages.s05_draft import (
            DraftInput,
            DraftStage,
        )

        mock_writer = MagicMock()
        mock_writer.execute.return_value = MagicMock(
            output=MagicMock(
                success=True,
                content_markdown="# Content with many words here",
                sections=["Content"],
                citations_used=[],
                word_count=5,
            ),
            stats=MagicMock(),
        )

        stage = DraftStage(writer_agent=mock_writer)
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = DraftInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            notes=[],
        )

        result = stage.execute(input_data)

        assert result.word_count == 5

    def test_draft_saves_content_to_run_dir(self, tmp_path: Path) -> None:
        """Draft should save generated content to run directory."""
        from procedurewriter.pipeline.stages.s05_draft import (
            DraftInput,
            DraftStage,
        )

        mock_writer = MagicMock()
        mock_writer.execute.return_value = MagicMock(
            output=MagicMock(
                success=True,
                content_markdown="# Saved Content\n\nThis is the draft.",
                sections=["Saved Content"],
                citations_used=[],
                word_count=5,
            ),
            stats=MagicMock(),
        )

        stage = DraftStage(writer_agent=mock_writer)
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = DraftInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            notes=[],
        )

        stage.execute(input_data)

        # Check that draft was saved
        draft_file = run_dir / "draft.md"
        assert draft_file.exists()
        assert "Saved Content" in draft_file.read_text()
