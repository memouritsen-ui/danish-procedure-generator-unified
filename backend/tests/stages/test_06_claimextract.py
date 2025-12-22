"""Tests for Stage 06: ClaimExtract.

The ClaimExtract stage parses claims from procedure drafts:
1. Receives draft markdown from Stage 05 (Draft)
2. Uses LLM to extract verifiable claims
3. Creates Claim objects with types (dose, threshold, etc.)
4. Outputs claims for Bind stage
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch
import json

import pytest

from procedurewriter.models.claims import Claim, ClaimType

if TYPE_CHECKING:
    pass


class TestClaimExtractStage:
    """Tests for Stage 06: ClaimExtract."""

    def test_claimextract_stage_name_is_claimextract(self) -> None:
        """ClaimExtract stage should identify itself as 'claimextract'."""
        from procedurewriter.pipeline.stages.s06_claimextract import ClaimExtractStage

        stage = ClaimExtractStage()
        assert stage.name == "claimextract"

    def test_claimextract_input_requires_content_markdown(self) -> None:
        """ClaimExtract input must have content_markdown field."""
        from procedurewriter.pipeline.stages.s06_claimextract import ClaimExtractInput

        input_data = ClaimExtractInput(
            run_id="test-run",
            run_dir=Path("/tmp/test"),
            procedure_title="Test Procedure",
            content_markdown="# Test\n\nSome content",
        )
        assert "# Test" in input_data.content_markdown

    def test_claimextract_output_has_claims_list(self, tmp_path: Path) -> None:
        """ClaimExtract output should contain a list of claims."""
        from procedurewriter.pipeline.stages.s06_claimextract import (
            ClaimExtractInput,
            ClaimExtractStage,
        )

        # Mock LLM to return structured claims
        mock_llm = MagicMock()
        mock_llm.chat_completion.return_value = MagicMock(
            content=json.dumps([
                {
                    "claim_type": "dose",
                    "text": "amoxicillin 50 mg/kg/d",
                    "normalized_value": "50",
                    "unit": "mg/kg/d",
                    "line_number": 5,
                    "confidence": 0.9,
                    "source_refs": ["SRC001"],
                }
            ]),
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
        )

        stage = ClaimExtractStage(llm_client=mock_llm)
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = ClaimExtractInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            content_markdown="# Test\n\n- amoxicillin 50 mg/kg/d [S:SRC001]",
        )

        result = stage.execute(input_data)

        assert hasattr(result, "claims")
        assert isinstance(result.claims, list)

    def test_claimextract_output_has_all_required_fields(self, tmp_path: Path) -> None:
        """ClaimExtract output should contain all fields needed by Bind stage."""
        from procedurewriter.pipeline.stages.s06_claimextract import (
            ClaimExtractInput,
            ClaimExtractStage,
        )

        mock_llm = MagicMock()
        mock_llm.chat_completion.return_value = MagicMock(
            content=json.dumps([]),
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
        )

        stage = ClaimExtractStage(llm_client=mock_llm)
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = ClaimExtractInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            content_markdown="# Test",
        )

        result = stage.execute(input_data)

        assert hasattr(result, "run_id")
        assert hasattr(result, "run_dir")
        assert hasattr(result, "procedure_title")
        assert hasattr(result, "claims")
        assert hasattr(result, "total_claims")
        assert result.run_id == "test-run"

    def test_claimextract_creates_claim_objects(self, tmp_path: Path) -> None:
        """ClaimExtract should create proper Claim objects."""
        from procedurewriter.pipeline.stages.s06_claimextract import (
            ClaimExtractInput,
            ClaimExtractStage,
        )

        mock_llm = MagicMock()
        mock_llm.chat_completion.return_value = MagicMock(
            content=json.dumps([
                {
                    "claim_type": "threshold",
                    "text": "CURB-65 score >= 3 indicates severe pneumonia",
                    "normalized_value": "3",
                    "unit": None,
                    "line_number": 10,
                    "confidence": 0.85,
                    "source_refs": ["SRC002"],
                }
            ]),
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
        )

        stage = ClaimExtractStage(llm_client=mock_llm)
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = ClaimExtractInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Pneumonia Treatment",
            content_markdown="# Pneumonia\n\n- CURB-65 score >= 3 indicates severe pneumonia [S:SRC002]",
        )

        result = stage.execute(input_data)

        assert len(result.claims) == 1
        claim = result.claims[0]
        assert isinstance(claim, Claim)
        assert claim.claim_type == ClaimType.THRESHOLD
        assert claim.run_id == "test-run"

    def test_claimextract_extracts_multiple_claim_types(self, tmp_path: Path) -> None:
        """ClaimExtract should extract different types of claims."""
        from procedurewriter.pipeline.stages.s06_claimextract import (
            ClaimExtractInput,
            ClaimExtractStage,
        )

        mock_llm = MagicMock()
        mock_llm.chat_completion.return_value = MagicMock(
            content=json.dumps([
                {"claim_type": "dose", "text": "amoxicillin 50 mg/kg", "line_number": 5, "confidence": 0.9, "source_refs": []},
                {"claim_type": "threshold", "text": "SpO2 < 92%", "line_number": 8, "confidence": 0.85, "source_refs": []},
                {"claim_type": "contraindication", "text": "penicillin allergy", "line_number": 12, "confidence": 0.95, "source_refs": []},
            ]),
            input_tokens=100,
            output_tokens=100,
            total_tokens=200,
        )

        stage = ClaimExtractStage(llm_client=mock_llm)
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = ClaimExtractInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test",
            content_markdown="# Test\n\nMultiple claims here",
        )

        result = stage.execute(input_data)

        assert len(result.claims) == 3
        types = {c.claim_type for c in result.claims}
        assert ClaimType.DOSE in types
        assert ClaimType.THRESHOLD in types
        assert ClaimType.CONTRAINDICATION in types

    def test_claimextract_emits_progress_event(self, tmp_path: Path) -> None:
        """ClaimExtract should emit a progress event when starting."""
        from procedurewriter.pipeline.stages.s06_claimextract import (
            ClaimExtractInput,
            ClaimExtractStage,
        )

        mock_llm = MagicMock()
        mock_llm.chat_completion.return_value = MagicMock(
            content=json.dumps([]),
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
        )

        mock_emitter = MagicMock()
        stage = ClaimExtractStage(llm_client=mock_llm)
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = ClaimExtractInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            content_markdown="# Test",
            emitter=mock_emitter,
        )

        stage.execute(input_data)

        mock_emitter.emit.assert_called()

    def test_claimextract_handles_empty_content(self, tmp_path: Path) -> None:
        """ClaimExtract should handle empty markdown content."""
        from procedurewriter.pipeline.stages.s06_claimextract import (
            ClaimExtractInput,
            ClaimExtractStage,
        )

        mock_llm = MagicMock()
        mock_llm.chat_completion.return_value = MagicMock(
            content=json.dumps([]),
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
        )

        stage = ClaimExtractStage(llm_client=mock_llm)
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = ClaimExtractInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            content_markdown="",
        )

        result = stage.execute(input_data)

        assert result.claims == []
        assert result.total_claims == 0

    def test_claimextract_handles_llm_error_gracefully(self, tmp_path: Path) -> None:
        """ClaimExtract should handle LLM errors without crashing."""
        from procedurewriter.pipeline.stages.s06_claimextract import (
            ClaimExtractInput,
            ClaimExtractStage,
        )

        mock_llm = MagicMock()
        mock_llm.chat_completion.side_effect = Exception("API rate limit exceeded")

        stage = ClaimExtractStage(llm_client=mock_llm)
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = ClaimExtractInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            content_markdown="# Test content",
        )

        # Should not raise
        result = stage.execute(input_data)
        assert isinstance(result.claims, list)

    def test_claimextract_handles_malformed_llm_response(self, tmp_path: Path) -> None:
        """ClaimExtract should handle malformed JSON from LLM."""
        from procedurewriter.pipeline.stages.s06_claimextract import (
            ClaimExtractInput,
            ClaimExtractStage,
        )

        mock_llm = MagicMock()
        mock_llm.chat_completion.return_value = MagicMock(
            content="This is not valid JSON",
            input_tokens=10,
            output_tokens=10,
            total_tokens=20,
        )

        stage = ClaimExtractStage(llm_client=mock_llm)
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = ClaimExtractInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            content_markdown="# Test content",
        )

        # Should not crash, return empty claims
        result = stage.execute(input_data)
        assert isinstance(result.claims, list)

    def test_claimextract_passes_through_run_dir(self, tmp_path: Path) -> None:
        """ClaimExtract should pass through run_dir for subsequent stages."""
        from procedurewriter.pipeline.stages.s06_claimextract import (
            ClaimExtractInput,
            ClaimExtractStage,
        )

        mock_llm = MagicMock()
        mock_llm.chat_completion.return_value = MagicMock(
            content=json.dumps([]),
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
        )

        stage = ClaimExtractStage(llm_client=mock_llm)
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = ClaimExtractInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test procedure",
            content_markdown="# Test",
        )

        result = stage.execute(input_data)

        assert result.run_dir == run_dir

    def test_claimextract_preserves_source_refs(self, tmp_path: Path) -> None:
        """ClaimExtract should preserve source references from content."""
        from procedurewriter.pipeline.stages.s06_claimextract import (
            ClaimExtractInput,
            ClaimExtractStage,
        )

        mock_llm = MagicMock()
        mock_llm.chat_completion.return_value = MagicMock(
            content=json.dumps([
                {
                    "claim_type": "dose",
                    "text": "Drug X 100mg daily",
                    "line_number": 5,
                    "confidence": 0.9,
                    "source_refs": ["SRC001", "SRC002"],
                }
            ]),
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
        )

        stage = ClaimExtractStage(llm_client=mock_llm)
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = ClaimExtractInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test",
            content_markdown="# Test\n\n- Drug X 100mg daily [S:SRC001][S:SRC002]",
        )

        result = stage.execute(input_data)

        assert len(result.claims) == 1
        assert "SRC001" in result.claims[0].source_refs
        assert "SRC002" in result.claims[0].source_refs

    def test_claimextract_tracks_total_claims_count(self, tmp_path: Path) -> None:
        """ClaimExtract output should track total number of claims."""
        from procedurewriter.pipeline.stages.s06_claimextract import (
            ClaimExtractInput,
            ClaimExtractStage,
        )

        mock_llm = MagicMock()
        mock_llm.chat_completion.return_value = MagicMock(
            content=json.dumps([
                {"claim_type": "dose", "text": "Claim 1", "line_number": 1, "confidence": 0.9, "source_refs": []},
                {"claim_type": "dose", "text": "Claim 2", "line_number": 2, "confidence": 0.9, "source_refs": []},
                {"claim_type": "dose", "text": "Claim 3", "line_number": 3, "confidence": 0.9, "source_refs": []},
            ]),
            input_tokens=100,
            output_tokens=100,
            total_tokens=200,
        )

        stage = ClaimExtractStage(llm_client=mock_llm)
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        input_data = ClaimExtractInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Test",
            content_markdown="# Test with claims",
        )

        result = stage.execute(input_data)

        assert result.total_claims == len(result.claims)
        assert result.total_claims == 3

    def test_claimextract_passes_content_to_llm(self, tmp_path: Path) -> None:
        """ClaimExtract should pass markdown content to LLM for extraction."""
        from procedurewriter.pipeline.stages.s06_claimextract import (
            ClaimExtractInput,
            ClaimExtractStage,
        )

        mock_llm = MagicMock()
        mock_llm.chat_completion.return_value = MagicMock(
            content=json.dumps([]),
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
        )

        stage = ClaimExtractStage(llm_client=mock_llm)
        run_dir = tmp_path / "runs" / "test-run"
        run_dir.mkdir(parents=True)

        test_content = "# Pneumonia Treatment\n\n- amoxicillin 50 mg/kg/d [S:SRC001]"

        input_data = ClaimExtractInput(
            run_id="test-run",
            run_dir=run_dir,
            procedure_title="Pneumonia",
            content_markdown=test_content,
        )

        stage.execute(input_data)

        # Check LLM was called with content
        call_args = mock_llm.chat_completion.call_args
        messages = call_args.kwargs.get("messages") or call_args[0][0]
        prompt_text = str(messages)
        assert "amoxicillin" in prompt_text or "Pneumonia" in prompt_text
