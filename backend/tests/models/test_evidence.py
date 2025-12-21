"""Tests for EvidenceChunk and ClaimEvidenceLink models.

TDD: These tests are written FIRST before implementation.
Run: pytest tests/models/test_evidence.py -v
"""

from datetime import datetime
from uuid import UUID

import pytest


class TestEvidenceChunk:
    """Tests for EvidenceChunk Pydantic model."""

    def test_evidence_chunk_creation_minimal(self):
        """Should create EvidenceChunk with minimal required fields."""
        from procedurewriter.models.evidence import EvidenceChunk

        chunk = EvidenceChunk(
            run_id="test-run-123",
            source_id="SRC0023",
            text="Amoxicillin 50 mg/kg/d is the recommended first-line treatment.",
            chunk_index=0,
        )

        assert chunk.run_id == "test-run-123"
        assert chunk.source_id == "SRC0023"
        assert "Amoxicillin" in chunk.text
        assert chunk.chunk_index == 0
        assert chunk.start_char is None
        assert chunk.end_char is None
        assert chunk.embedding_vector is None
        assert chunk.metadata == {}

    def test_evidence_chunk_creation_full(self):
        """Should create EvidenceChunk with all fields populated."""
        from procedurewriter.models.evidence import EvidenceChunk

        chunk = EvidenceChunk(
            run_id="test-run-456",
            source_id="SRC0024",
            text="CURB-65 score >= 3 indicates need for ICU admission.",
            chunk_index=2,
            start_char=1500,
            end_char=1600,
            embedding_vector=[0.1, 0.2, 0.3, 0.4],
            metadata={"section": "treatment", "page": 5},
        )

        assert chunk.run_id == "test-run-456"
        assert chunk.source_id == "SRC0024"
        assert chunk.chunk_index == 2
        assert chunk.start_char == 1500
        assert chunk.end_char == 1600
        assert chunk.embedding_vector == [0.1, 0.2, 0.3, 0.4]
        assert chunk.metadata == {"section": "treatment", "page": 5}

    def test_evidence_chunk_has_auto_id(self):
        """EvidenceChunk should auto-generate a UUID id."""
        from procedurewriter.models.evidence import EvidenceChunk

        chunk = EvidenceChunk(
            run_id="test-run",
            source_id="SRC0001",
            text="Test chunk text",
            chunk_index=0,
        )

        assert chunk.id is not None
        UUID(str(chunk.id))  # Raises if invalid

    def test_evidence_chunk_has_created_at(self):
        """EvidenceChunk should have auto-generated created_at timestamp."""
        from procedurewriter.models.evidence import EvidenceChunk

        chunk = EvidenceChunk(
            run_id="test-run",
            source_id="SRC0001",
            text="Test chunk text",
            chunk_index=0,
        )

        assert chunk.created_at is not None
        assert isinstance(chunk.created_at, datetime)

    def test_evidence_chunk_text_required(self):
        """Text field should be required and non-empty."""
        from pydantic import ValidationError

        from procedurewriter.models.evidence import EvidenceChunk

        with pytest.raises(ValidationError):
            EvidenceChunk(
                run_id="test-run",
                source_id="SRC0001",
                text="",  # Invalid: empty
                chunk_index=0,
            )

    def test_evidence_chunk_index_non_negative(self):
        """Chunk index should be non-negative."""
        from pydantic import ValidationError

        from procedurewriter.models.evidence import EvidenceChunk

        # Valid: 0
        chunk = EvidenceChunk(
            run_id="test-run",
            source_id="SRC0001",
            text="Test",
            chunk_index=0,
        )
        assert chunk.chunk_index == 0

        # Invalid: negative
        with pytest.raises(ValidationError):
            EvidenceChunk(
                run_id="test-run",
                source_id="SRC0001",
                text="Test",
                chunk_index=-1,
            )

    def test_evidence_chunk_char_range_validation(self):
        """Start char should be less than end char when both provided."""
        from pydantic import ValidationError

        from procedurewriter.models.evidence import EvidenceChunk

        # Valid range
        chunk = EvidenceChunk(
            run_id="test-run",
            source_id="SRC0001",
            text="Test",
            chunk_index=0,
            start_char=100,
            end_char=200,
        )
        assert chunk.start_char == 100
        assert chunk.end_char == 200

        # Invalid: start >= end
        with pytest.raises(ValidationError):
            EvidenceChunk(
                run_id="test-run",
                source_id="SRC0001",
                text="Test",
                chunk_index=0,
                start_char=200,
                end_char=100,
            )

    def test_evidence_chunk_serialization(self):
        """Should serialize to dict/JSON properly."""
        from procedurewriter.models.evidence import EvidenceChunk

        chunk = EvidenceChunk(
            run_id="test-run",
            source_id="SRC0023",
            text="Evidence text here",
            chunk_index=1,
            start_char=50,
            end_char=100,
            metadata={"key": "value"},
        )

        data = chunk.model_dump()

        assert data["run_id"] == "test-run"
        assert data["source_id"] == "SRC0023"
        assert data["text"] == "Evidence text here"
        assert data["chunk_index"] == 1
        assert data["start_char"] == 50
        assert data["end_char"] == 100
        assert data["metadata"] == {"key": "value"}
        assert "id" in data
        assert "created_at" in data

    def test_evidence_chunk_deserialization(self):
        """Should deserialize from dict properly."""
        from procedurewriter.models.evidence import EvidenceChunk

        data = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "run_id": "test-run",
            "source_id": "SRC0025",
            "text": "Deserialized chunk",
            "chunk_index": 3,
            "start_char": 500,
            "end_char": 600,
            "embedding_vector": [0.5, 0.6],
            "metadata": {"type": "abstract"},
            "created_at": "2024-12-21T12:00:00Z",
        }

        chunk = EvidenceChunk.model_validate(data)

        assert chunk.run_id == "test-run"
        assert chunk.source_id == "SRC0025"
        assert chunk.chunk_index == 3
        assert chunk.embedding_vector == [0.5, 0.6]


class TestEvidenceChunkDbConversion:
    """Tests for database conversion methods on EvidenceChunk."""

    def test_to_db_row_returns_correct_tuple(self):
        """to_db_row() should return tuple matching DB column order."""
        import json
        from datetime import datetime, timezone
        from uuid import UUID

        from procedurewriter.models.evidence import EvidenceChunk

        fixed_id = UUID("550e8400-e29b-41d4-a716-446655440000")
        fixed_time = datetime(2024, 12, 21, 12, 0, 0, tzinfo=timezone.utc)

        chunk = EvidenceChunk(
            id=fixed_id,
            run_id="test-run-123",
            source_id="SRC0023",
            text="Evidence text content here",
            chunk_index=2,
            start_char=100,
            end_char=200,
            embedding_vector=[0.1, 0.2, 0.3],
            metadata={"section": "treatment", "page": 5},
            created_at=fixed_time,
        )

        row = chunk.to_db_row()

        # Verify tuple structure matches DB schema
        assert isinstance(row, tuple)
        assert len(row) == 10

        # Verify each field
        assert row[0] == "550e8400-e29b-41d4-a716-446655440000"  # id (str)
        assert row[1] == "test-run-123"  # run_id
        assert row[2] == "SRC0023"  # source_id
        assert row[3] == "Evidence text content here"  # text
        assert row[4] == 2  # chunk_index
        assert row[5] == 100  # start_char
        assert row[6] == 200  # end_char
        assert row[7] == "[0.1, 0.2, 0.3]"  # embedding_vector_json
        assert row[8] == '{"section": "treatment", "page": 5}'  # metadata_json
        assert row[9] == "2024-12-21T12:00:00+00:00"  # created_at_utc

    def test_to_db_row_with_null_optional_fields(self):
        """to_db_row() should handle None values for optional fields."""
        from procedurewriter.models.evidence import EvidenceChunk

        chunk = EvidenceChunk(
            run_id="test-run",
            source_id="SRC0001",
            text="Minimal chunk",
            chunk_index=0,
        )

        row = chunk.to_db_row()

        assert row[5] is None  # start_char
        assert row[6] is None  # end_char
        assert row[7] is None  # embedding_vector_json
        assert row[8] == "{}"  # metadata_json (empty dict)

    def test_to_db_row_id_is_string(self):
        """to_db_row() should convert UUID id to string."""
        from procedurewriter.models.evidence import EvidenceChunk

        chunk = EvidenceChunk(
            run_id="test-run",
            source_id="SRC0001",
            text="Test",
            chunk_index=0,
        )

        row = chunk.to_db_row()

        # First element should be string, not UUID
        assert isinstance(row[0], str)
        assert len(row[0]) == 36  # UUID string format


class TestEvidenceChunkHelpers:
    """Tests for helper methods on EvidenceChunk."""

    def test_has_embedding_property(self):
        """Should have has_embedding property."""
        from procedurewriter.models.evidence import EvidenceChunk

        with_embedding = EvidenceChunk(
            run_id="test-run",
            source_id="SRC0001",
            text="Test",
            chunk_index=0,
            embedding_vector=[0.1, 0.2, 0.3],
        )
        assert with_embedding.has_embedding is True

        without_embedding = EvidenceChunk(
            run_id="test-run",
            source_id="SRC0001",
            text="Test",
            chunk_index=0,
        )
        assert without_embedding.has_embedding is False

    def test_char_length_property(self):
        """Should have char_length property when range is set."""
        from procedurewriter.models.evidence import EvidenceChunk

        chunk = EvidenceChunk(
            run_id="test-run",
            source_id="SRC0001",
            text="Test",
            chunk_index=0,
            start_char=100,
            end_char=250,
        )
        assert chunk.char_length == 150

        no_range = EvidenceChunk(
            run_id="test-run",
            source_id="SRC0001",
            text="Test",
            chunk_index=0,
        )
        assert no_range.char_length is None


class TestClaimEvidenceLink:
    """Tests for ClaimEvidenceLink model (P1-003 preview)."""

    def test_claim_evidence_link_creation(self):
        """Should create ClaimEvidenceLink with required fields."""
        from procedurewriter.models.evidence import BindingType, ClaimEvidenceLink

        link = ClaimEvidenceLink(
            claim_id="550e8400-e29b-41d4-a716-446655440001",
            evidence_chunk_id="550e8400-e29b-41d4-a716-446655440002",
            binding_type=BindingType.KEYWORD,
            binding_score=0.85,
        )

        assert str(link.claim_id) == "550e8400-e29b-41d4-a716-446655440001"
        assert str(link.evidence_chunk_id) == "550e8400-e29b-41d4-a716-446655440002"
        assert link.binding_type == BindingType.KEYWORD
        assert link.binding_score == 0.85

    def test_binding_type_enum(self):
        """BindingType enum should have expected values."""
        from procedurewriter.models.evidence import BindingType

        assert BindingType.KEYWORD.value == "keyword"
        assert BindingType.SEMANTIC.value == "semantic"
        assert BindingType.MANUAL.value == "manual"

    def test_claim_evidence_link_has_auto_id(self):
        """ClaimEvidenceLink should auto-generate a UUID id."""
        from procedurewriter.models.evidence import BindingType, ClaimEvidenceLink

        link = ClaimEvidenceLink(
            claim_id="550e8400-e29b-41d4-a716-446655440001",
            evidence_chunk_id="550e8400-e29b-41d4-a716-446655440002",
            binding_type=BindingType.SEMANTIC,
            binding_score=0.9,
        )

        assert link.id is not None
        UUID(str(link.id))

    def test_binding_score_validation(self):
        """Binding score should be between 0 and 1."""
        from pydantic import ValidationError

        from procedurewriter.models.evidence import BindingType, ClaimEvidenceLink

        # Valid
        link = ClaimEvidenceLink(
            claim_id="550e8400-e29b-41d4-a716-446655440001",
            evidence_chunk_id="550e8400-e29b-41d4-a716-446655440002",
            binding_type=BindingType.SEMANTIC,
            binding_score=0.5,
        )
        assert link.binding_score == 0.5

        # Invalid: > 1
        with pytest.raises(ValidationError):
            ClaimEvidenceLink(
                claim_id="550e8400-e29b-41d4-a716-446655440001",
                evidence_chunk_id="550e8400-e29b-41d4-a716-446655440002",
                binding_type=BindingType.SEMANTIC,
                binding_score=1.5,
            )

        # Invalid: < 0
        with pytest.raises(ValidationError):
            ClaimEvidenceLink(
                claim_id="550e8400-e29b-41d4-a716-446655440001",
                evidence_chunk_id="550e8400-e29b-41d4-a716-446655440002",
                binding_type=BindingType.SEMANTIC,
                binding_score=-0.1,
            )

    def test_claim_evidence_link_is_strong_binding(self):
        """Should have is_strong_binding property (>= 0.7)."""
        from procedurewriter.models.evidence import BindingType, ClaimEvidenceLink

        strong = ClaimEvidenceLink(
            claim_id="550e8400-e29b-41d4-a716-446655440001",
            evidence_chunk_id="550e8400-e29b-41d4-a716-446655440002",
            binding_type=BindingType.SEMANTIC,
            binding_score=0.85,
        )
        assert strong.is_strong_binding is True

        weak = ClaimEvidenceLink(
            claim_id="550e8400-e29b-41d4-a716-446655440001",
            evidence_chunk_id="550e8400-e29b-41d4-a716-446655440002",
            binding_type=BindingType.KEYWORD,
            binding_score=0.5,
        )
        assert weak.is_strong_binding is False

        boundary = ClaimEvidenceLink(
            claim_id="550e8400-e29b-41d4-a716-446655440001",
            evidence_chunk_id="550e8400-e29b-41d4-a716-446655440002",
            binding_type=BindingType.MANUAL,
            binding_score=0.7,
        )
        assert boundary.is_strong_binding is True
