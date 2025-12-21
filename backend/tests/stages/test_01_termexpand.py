"""Tests for Stage 01: TermExpand.

The TermExpand stage expands Danish medical procedure titles into:
1. English translation/equivalents
2. MeSH (Medical Subject Headings) terms
3. Synonyms and related terms
4. Common abbreviations

This provides structured search terms for the Retrieve stage.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    pass


class TestTermExpandStage:
    """Tests for Stage 01: TermExpand."""

    def test_termexpand_stage_name_is_termexpand(self) -> None:
        """TermExpand stage should identify itself as 'termexpand'."""
        from procedurewriter.pipeline.stages.s01_termexpand import TermExpandStage

        stage = TermExpandStage()
        assert stage.name == "termexpand"

    def test_termexpand_requires_procedure_title_in_input(self) -> None:
        """TermExpand input must have procedure_title field."""
        from procedurewriter.pipeline.stages.s01_termexpand import TermExpandInput

        # Should be able to create with procedure_title
        input_data = TermExpandInput(
            run_id="test-run",
            run_dir=Path("/tmp/test"),
            procedure_title="Anafylaksi behandling",
        )
        assert input_data.procedure_title == "Anafylaksi behandling"

    def test_termexpand_output_contains_original_danish_term(
        self, tmp_path: Path
    ) -> None:
        """TermExpand output should always contain the original Danish term."""
        from procedurewriter.pipeline.stages.s01_termexpand import (
            TermExpandInput,
            TermExpandStage,
        )

        stage = TermExpandStage()
        input_data = TermExpandInput(
            run_id="test-run",
            run_dir=tmp_path,
            procedure_title="Pneumoni behandling",
        )

        result = stage.execute(input_data)

        # Original Danish term must be preserved
        assert result.danish_terms is not None
        assert "Pneumoni behandling" in result.danish_terms

    def test_termexpand_output_contains_english_translations(
        self, tmp_path: Path
    ) -> None:
        """TermExpand output should contain English translations."""
        from procedurewriter.pipeline.stages.s01_termexpand import (
            TermExpandInput,
            TermExpandStage,
        )

        stage = TermExpandStage()
        input_data = TermExpandInput(
            run_id="test-run",
            run_dir=tmp_path,
            procedure_title="Anafylaksi behandling",
        )

        result = stage.execute(input_data)

        # Should have English translations
        assert result.english_terms is not None
        assert len(result.english_terms) >= 1
        # "anaphylaxis" should be in at least one term
        english_lower = [t.lower() for t in result.english_terms]
        assert any("anaphylaxis" in t for t in english_lower)

    def test_termexpand_output_contains_mesh_terms(self, tmp_path: Path) -> None:
        """TermExpand output should contain MeSH terms when applicable."""
        from procedurewriter.pipeline.stages.s01_termexpand import (
            TermExpandInput,
            TermExpandStage,
        )

        stage = TermExpandStage()
        input_data = TermExpandInput(
            run_id="test-run",
            run_dir=tmp_path,
            procedure_title="Anafylaksi behandling",
        )

        result = stage.execute(input_data)

        # Should have MeSH terms list (may be empty for unknown procedures)
        assert hasattr(result, "mesh_terms")

    def test_termexpand_output_has_all_required_fields(self, tmp_path: Path) -> None:
        """TermExpand output should contain all fields needed by Retrieve stage."""
        from procedurewriter.pipeline.stages.s01_termexpand import (
            TermExpandInput,
            TermExpandStage,
        )

        stage = TermExpandStage()
        input_data = TermExpandInput(
            run_id="test-run",
            run_dir=tmp_path,
            procedure_title="Akut astma",
        )

        result = stage.execute(input_data)

        # Check all required output fields exist
        assert hasattr(result, "run_id")
        assert hasattr(result, "run_dir")
        assert hasattr(result, "procedure_title")
        assert hasattr(result, "danish_terms")
        assert hasattr(result, "english_terms")
        assert hasattr(result, "mesh_terms")
        assert hasattr(result, "all_search_terms")
        assert result.run_id == "test-run"
        assert result.procedure_title == "Akut astma"

    def test_termexpand_all_search_terms_combines_all_term_types(
        self, tmp_path: Path
    ) -> None:
        """all_search_terms should combine Danish, English, and MeSH terms."""
        from procedurewriter.pipeline.stages.s01_termexpand import (
            TermExpandInput,
            TermExpandStage,
        )

        stage = TermExpandStage()
        input_data = TermExpandInput(
            run_id="test-run",
            run_dir=tmp_path,
            procedure_title="Pneumoni behandling",
        )

        result = stage.execute(input_data)

        # all_search_terms should be non-empty
        assert result.all_search_terms is not None
        assert len(result.all_search_terms) >= 2

        # Should contain at least Danish original
        assert any("pneumoni" in t.lower() for t in result.all_search_terms)

    def test_termexpand_emits_progress_event(self, tmp_path: Path) -> None:
        """TermExpand should emit a progress event when starting."""
        from procedurewriter.pipeline.stages.s01_termexpand import (
            TermExpandInput,
            TermExpandStage,
        )

        mock_emitter = MagicMock()

        stage = TermExpandStage()
        input_data = TermExpandInput(
            run_id="test-run",
            run_dir=tmp_path,
            procedure_title="Test procedure",
            emitter=mock_emitter,
        )

        stage.execute(input_data)

        # Verify emitter was called
        mock_emitter.emit.assert_called()

    def test_termexpand_uses_static_mapping_for_known_terms(
        self, tmp_path: Path
    ) -> None:
        """TermExpand should use static mapping for known Danish medical terms."""
        from procedurewriter.pipeline.stages.s01_termexpand import (
            TermExpandInput,
            TermExpandStage,
        )

        stage = TermExpandStage()
        input_data = TermExpandInput(
            run_id="test-run",
            run_dir=tmp_path,
            procedure_title="Anafylaksi behandling",
        )

        result = stage.execute(input_data)

        # For known terms like "anafylaksi", should map to "anaphylaxis"
        english_lower = [t.lower() for t in result.english_terms]
        assert any("anaphylaxis" in t for t in english_lower)

    def test_termexpand_handles_unknown_terms_gracefully(
        self, tmp_path: Path
    ) -> None:
        """TermExpand should handle unknown/new terms without crashing."""
        from procedurewriter.pipeline.stages.s01_termexpand import (
            TermExpandInput,
            TermExpandStage,
        )

        stage = TermExpandStage()
        input_data = TermExpandInput(
            run_id="test-run",
            run_dir=tmp_path,
            procedure_title="Ukendt sjælden tilstand",  # Unknown rare condition
        )

        result = stage.execute(input_data)

        # Should still produce output with at least the original term
        assert result.danish_terms is not None
        assert "Ukendt sjælden tilstand" in result.danish_terms
        # Should have some search terms
        assert len(result.all_search_terms) >= 1

    def test_termexpand_normalizes_case_for_searching(self, tmp_path: Path) -> None:
        """Search terms should be normalized for case-insensitive matching."""
        from procedurewriter.pipeline.stages.s01_termexpand import (
            TermExpandInput,
            TermExpandStage,
        )

        stage = TermExpandStage()
        input_data = TermExpandInput(
            run_id="test-run",
            run_dir=tmp_path,
            procedure_title="ANAFYLAKSI BEHANDLING",  # Uppercase
        )

        result = stage.execute(input_data)

        # Should still map correctly despite case
        english_lower = [t.lower() for t in result.english_terms]
        assert any("anaphylaxis" in t for t in english_lower)

    def test_termexpand_passes_through_run_dir(self, tmp_path: Path) -> None:
        """TermExpand should pass through run_dir for file operations."""
        from procedurewriter.pipeline.stages.s01_termexpand import (
            TermExpandInput,
            TermExpandStage,
        )

        stage = TermExpandStage()
        input_data = TermExpandInput(
            run_id="test-run",
            run_dir=tmp_path / "runs" / "test-run",
            procedure_title="Test procedure",
        )

        result = stage.execute(input_data)

        assert result.run_dir == tmp_path / "runs" / "test-run"
