"""Tests for Stage 07: Bind.

The Bind stage links claims to their supporting evidence:
1. Receives claims from Stage 06 (ClaimExtract)
2. Receives evidence chunks (from earlier in pipeline)
3. Uses keyword and/or semantic matching to find links
4. Creates ClaimEvidenceLink objects
5. Outputs bound claims for Evals stage
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from procedurewriter.models.claims import Claim, ClaimType
from procedurewriter.models.evidence import BindingType, ClaimEvidenceLink, EvidenceChunk

if TYPE_CHECKING:
    pass


def make_claim(
    run_id: str = "test-run",
    claim_type: ClaimType = ClaimType.DOSE,
    text: str = "amoxicillin 50 mg/kg/d",
    source_refs: list[str] | None = None,
) -> Claim:
    """Factory function to create test Claim objects."""
    return Claim(
        run_id=run_id,
        claim_type=claim_type,
        text=text,
        source_refs=source_refs or [],
        line_number=1,
        confidence=0.9,
    )


def make_chunk(
    run_id: str = "test-run",
    source_id: str = "SRC001",
    text: str = "First-line treatment is amoxicillin 50 mg/kg/d",
    chunk_index: int = 0,
) -> EvidenceChunk:
    """Factory function to create test EvidenceChunk objects."""
    return EvidenceChunk(
        run_id=run_id,
        source_id=source_id,
        text=text,
        chunk_index=chunk_index,
    )


class TestBindStage:
    """Tests for Stage 07: Bind."""

    def test_bind_stage_name_is_bind(self) -> None:
        """Bind stage should identify itself as 'bind'."""
        from procedurewriter.pipeline.stages.s07_bind import BindStage

        stage = BindStage()
        assert stage.name == "bind"

    def test_bind_input_requires_claims_and_chunks(self) -> None:
        """Bind input must have claims and chunks fields."""
        from procedurewriter.pipeline.stages.s07_bind import BindInput

        claim = make_claim()
        chunk = make_chunk()

        input_data = BindInput(
            run_id="test-run",
            run_dir=Path("/tmp/test"),
            procedure_title="Test Procedure",
            claims=[claim],
            chunks=[chunk],
        )
        assert len(input_data.claims) == 1
        assert len(input_data.chunks) == 1

    def test_bind_output_has_links_list(self, tmp_path: Path) -> None:
        """Bind output should contain a list of ClaimEvidenceLink objects."""
        from procedurewriter.pipeline.stages.s07_bind import (
            BindInput,
            BindStage,
        )

        claim = make_claim(text="amoxicillin 50 mg/kg/d", source_refs=["SRC001"])
        chunk = make_chunk(source_id="SRC001", text="amoxicillin 50 mg/kg/d is recommended")

        stage = BindStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = BindInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            claims=[claim],
            chunks=[chunk],
        )

        result = stage.execute(input_data)

        assert hasattr(result, "links")
        assert isinstance(result.links, list)

    def test_bind_output_has_all_required_fields(self, tmp_path: Path) -> None:
        """Bind output should contain all fields needed by Evals stage."""
        from procedurewriter.pipeline.stages.s07_bind import (
            BindInput,
            BindStage,
        )

        stage = BindStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = BindInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            claims=[],
            chunks=[],
        )

        result = stage.execute(input_data)

        assert hasattr(result, "run_id")
        assert hasattr(result, "run_dir")
        assert hasattr(result, "procedure_title")
        assert hasattr(result, "links")
        assert hasattr(result, "total_links")
        assert hasattr(result, "claims")
        assert hasattr(result, "unbound_claims")
        assert result.run_id == "test-run"

    def test_bind_creates_link_for_matching_source_ref(self, tmp_path: Path) -> None:
        """Bind should create links when claim source_refs match chunk source_id."""
        from procedurewriter.pipeline.stages.s07_bind import (
            BindInput,
            BindStage,
        )

        claim = make_claim(
            text="amoxicillin 50 mg/kg/d",
            source_refs=["SRC001"],
        )
        chunk = make_chunk(source_id="SRC001", text="Treatment: amoxicillin 50 mg/kg/d")

        stage = BindStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = BindInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test",
            claims=[claim],
            chunks=[chunk],
        )

        result = stage.execute(input_data)

        assert len(result.links) >= 1
        link = result.links[0]
        assert isinstance(link, ClaimEvidenceLink)
        assert link.claim_id == claim.id
        assert link.evidence_chunk_id == chunk.id

    def test_bind_uses_keyword_binding_type(self, tmp_path: Path) -> None:
        """Bind should use KEYWORD binding type for text matching."""
        from procedurewriter.pipeline.stages.s07_bind import (
            BindInput,
            BindStage,
        )

        claim = make_claim(
            text="penicillin allergy",
            source_refs=["SRC002"],
        )
        chunk = make_chunk(
            source_id="SRC002",
            text="Contraindication: penicillin allergy must be checked",
        )

        stage = BindStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = BindInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test",
            claims=[claim],
            chunks=[chunk],
        )

        result = stage.execute(input_data)

        assert len(result.links) >= 1
        assert result.links[0].binding_type == BindingType.KEYWORD

    def test_bind_tracks_unbound_claims(self, tmp_path: Path) -> None:
        """Bind should track claims that couldn't be linked to evidence."""
        from procedurewriter.pipeline.stages.s07_bind import (
            BindInput,
            BindStage,
        )

        # Claim with no matching source or keywords
        claim = make_claim(
            text="completely unrelated claim about xyz",
            source_refs=["NONEXISTENT"],
        )
        chunk = make_chunk(source_id="SRC001", text="Different content about abc")

        stage = BindStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = BindInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test",
            claims=[claim],
            chunks=[chunk],
        )

        result = stage.execute(input_data)

        assert len(result.unbound_claims) == 1
        assert result.unbound_claims[0].id == claim.id

    def test_bind_emits_progress_event(self, tmp_path: Path) -> None:
        """Bind should emit a progress event when starting."""
        from procedurewriter.pipeline.stages.s07_bind import (
            BindInput,
            BindStage,
        )

        mock_emitter = MagicMock()
        stage = BindStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = BindInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            claims=[],
            chunks=[],
            emitter=mock_emitter,
        )

        stage.execute(input_data)

        mock_emitter.emit.assert_called()

    def test_bind_handles_empty_claims(self, tmp_path: Path) -> None:
        """Bind should handle empty claims list."""
        from procedurewriter.pipeline.stages.s07_bind import (
            BindInput,
            BindStage,
        )

        chunk = make_chunk()
        stage = BindStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = BindInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            claims=[],
            chunks=[chunk],
        )

        result = stage.execute(input_data)

        assert result.links == []
        assert result.total_links == 0

    def test_bind_handles_empty_chunks(self, tmp_path: Path) -> None:
        """Bind should handle empty chunks list (all claims become unbound)."""
        from procedurewriter.pipeline.stages.s07_bind import (
            BindInput,
            BindStage,
        )

        claim = make_claim()
        stage = BindStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = BindInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            claims=[claim],
            chunks=[],
        )

        result = stage.execute(input_data)

        assert result.links == []
        assert len(result.unbound_claims) == 1

    def test_bind_passes_through_run_dir(self, tmp_path: Path) -> None:
        """Bind should pass through run_dir for subsequent stages."""
        from procedurewriter.pipeline.stages.s07_bind import (
            BindInput,
            BindStage,
        )

        stage = BindStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = BindInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            claims=[],
            chunks=[],
        )

        result = stage.execute(input_data)

        assert result.run_dir == run_dir

    def test_bind_calculates_binding_score(self, tmp_path: Path) -> None:
        """Bind should calculate binding score based on keyword overlap."""
        from procedurewriter.pipeline.stages.s07_bind import (
            BindInput,
            BindStage,
        )

        claim = make_claim(
            text="amoxicillin 50 mg/kg/d for pneumonia",
            source_refs=["SRC001"],
        )
        chunk = make_chunk(
            source_id="SRC001",
            text="Treatment: amoxicillin 50 mg/kg/d is the standard for pneumonia",
        )

        stage = BindStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = BindInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test",
            claims=[claim],
            chunks=[chunk],
        )

        result = stage.execute(input_data)

        assert len(result.links) >= 1
        assert 0.0 <= result.links[0].binding_score <= 1.0

    def test_bind_links_claim_to_multiple_chunks(self, tmp_path: Path) -> None:
        """Bind should link a claim to multiple relevant chunks."""
        from procedurewriter.pipeline.stages.s07_bind import (
            BindInput,
            BindStage,
        )

        claim = make_claim(
            text="amoxicillin dosing",
            source_refs=["SRC001", "SRC002"],
        )
        chunk1 = make_chunk(source_id="SRC001", text="Amoxicillin dosing guidelines")
        chunk2 = make_chunk(source_id="SRC002", text="Amoxicillin dosing recommendations")

        stage = BindStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = BindInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test",
            claims=[claim],
            chunks=[chunk1, chunk2],
        )

        result = stage.execute(input_data)

        # Should have links to both chunks
        assert len(result.links) >= 2
        linked_chunk_ids = {link.evidence_chunk_id for link in result.links}
        assert chunk1.id in linked_chunk_ids
        assert chunk2.id in linked_chunk_ids

    def test_bind_passes_through_claims(self, tmp_path: Path) -> None:
        """Bind should pass through claims for subsequent stages."""
        from procedurewriter.pipeline.stages.s07_bind import (
            BindInput,
            BindStage,
        )

        claim = make_claim()
        chunk = make_chunk()
        stage = BindStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = BindInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test",
            claims=[claim],
            chunks=[chunk],
        )

        result = stage.execute(input_data)

        assert result.claims == [claim]

    def test_bind_tracks_total_links_count(self, tmp_path: Path) -> None:
        """Bind output should track total number of links."""
        from procedurewriter.pipeline.stages.s07_bind import (
            BindInput,
            BindStage,
        )

        claim = make_claim(source_refs=["SRC001"])
        chunk = make_chunk(source_id="SRC001", text="matching text")

        stage = BindStage()
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = BindInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test",
            claims=[claim],
            chunks=[chunk],
        )

        result = stage.execute(input_data)

        assert result.total_links == len(result.links)
