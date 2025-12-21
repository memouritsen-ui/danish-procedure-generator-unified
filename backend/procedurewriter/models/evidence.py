"""EvidenceChunk and ClaimEvidenceLink models for the auditable procedure system.

These models represent evidence chunks extracted from sources and their
links to claims in procedures.

EvidenceChunk: A chunk of text from a source document that contains evidence.
ClaimEvidenceLink: Links claims to evidence chunks with binding type and score.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Sequence
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class BindingType(str, Enum):
    """Type of binding between a claim and evidence chunk."""

    KEYWORD = "keyword"  # Matched via keyword overlap
    SEMANTIC = "semantic"  # Matched via embedding similarity
    MANUAL = "manual"  # Manually linked by reviewer


class EvidenceChunk(BaseModel):
    """A chunk of evidence text from a source document.

    Evidence chunks are segments of source documents (papers, guidelines, etc.)
    that can be linked to claims in procedures. Each chunk has a source ID,
    the text content, position info, and optional embedding for semantic search.

    Attributes:
        id: Unique identifier (auto-generated UUID).
        run_id: The procedure run this chunk belongs to.
        source_id: Reference to the source document (e.g., "SRC0023").
        text: The actual chunk text content.
        chunk_index: Index of this chunk within the source (0-based).
        start_char: Starting character position in source (optional).
        end_char: Ending character position in source (optional).
        embedding_vector: Vector embedding for semantic search (optional).
        metadata: Additional metadata (section, page, etc.).
        created_at: Timestamp when chunk was created.
    """

    id: UUID = Field(default_factory=uuid4)
    run_id: str = Field(..., description="The procedure run this chunk belongs to")
    source_id: str = Field(..., description="Reference to source document")
    text: Annotated[str, Field(min_length=1, description="Chunk text content")]
    chunk_index: int = Field(..., ge=0, description="Index within source (0-based)")
    start_char: int | None = Field(
        default=None, ge=0, description="Start position in source"
    )
    end_char: int | None = Field(
        default=None, ge=0, description="End position in source"
    )
    embedding_vector: list[float] | None = Field(
        default=None, description="Vector embedding for semantic search"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when chunk was created",
    )

    @model_validator(mode="after")
    def validate_char_range(self) -> "EvidenceChunk":
        """Validate that start_char < end_char when both are provided."""
        if self.start_char is not None and self.end_char is not None:
            if self.start_char >= self.end_char:
                raise ValueError("start_char must be less than end_char")
        return self

    @property
    def has_embedding(self) -> bool:
        """Check if chunk has an embedding vector."""
        return self.embedding_vector is not None and len(self.embedding_vector) > 0

    @property
    def char_length(self) -> int | None:
        """Get the character length of the chunk if range is set."""
        if self.start_char is not None and self.end_char is not None:
            return self.end_char - self.start_char
        return None

    def to_db_row(self) -> tuple:
        """Convert model to database row tuple.

        Returns tuple matching evidence_chunks table column order:
        (id, run_id, source_id, text, chunk_index, start_char, end_char,
         embedding_vector_json, metadata_json, created_at_utc)
        """
        return (
            str(self.id),
            self.run_id,
            self.source_id,
            self.text,
            self.chunk_index,
            self.start_char,
            self.end_char,
            json.dumps(self.embedding_vector) if self.embedding_vector else None,
            json.dumps(self.metadata),
            self.created_at.isoformat(),
        )

    @classmethod
    def from_db_row(cls, row: Sequence) -> "EvidenceChunk":
        """Reconstruct EvidenceChunk from database row tuple.

        Args:
            row: Tuple/sequence in same order as to_db_row() output:
                (id, run_id, source_id, text, chunk_index, start_char, end_char,
                 embedding_vector_json, metadata_json, created_at_utc)

        Returns:
            EvidenceChunk instance with all fields populated from DB row.
        """
        return cls(
            id=UUID(row[0]),
            run_id=row[1],
            source_id=row[2],
            text=row[3],
            chunk_index=row[4],
            start_char=row[5],
            end_char=row[6],
            embedding_vector=json.loads(row[7]) if row[7] else None,
            metadata=json.loads(row[8]) if row[8] else {},
            created_at=datetime.fromisoformat(row[9]),
        )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "run_id": "5e5bbba1790a48d5ae1cf7cc270cfc6f",
                    "source_id": "SRC0023",
                    "text": "First-line treatment for community-acquired pneumonia...",
                    "chunk_index": 0,
                    "start_char": 1500,
                    "end_char": 2000,
                    "metadata": {"section": "treatment", "page": 5},
                    "created_at": "2024-12-21T12:00:00Z",
                }
            ]
        }
    }


class ClaimEvidenceLink(BaseModel):
    """Links a claim to an evidence chunk with binding type and score.

    ClaimEvidenceLinks represent the traceability from claims in procedures
    to the evidence that supports them. Each link has a binding type
    (keyword, semantic, manual) and a score indicating binding strength.

    Attributes:
        id: Unique identifier (auto-generated UUID).
        claim_id: UUID of the linked claim.
        evidence_chunk_id: UUID of the linked evidence chunk.
        binding_type: How the binding was established.
        binding_score: Strength of the binding (0.0-1.0).
        created_at: Timestamp when link was created.
    """

    id: UUID = Field(default_factory=uuid4)
    claim_id: UUID = Field(..., description="UUID of the linked claim")
    evidence_chunk_id: UUID = Field(
        ..., description="UUID of the linked evidence chunk"
    )
    binding_type: BindingType = Field(
        ..., description="How the binding was established"
    )
    binding_score: float = Field(
        ..., ge=0.0, le=1.0, description="Binding strength (0-1)"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when link was created",
    )

    @property
    def is_strong_binding(self) -> bool:
        """Check if this is a strong binding (score >= 0.7)."""
        return self.binding_score >= 0.7

    def to_db_row(self) -> tuple:
        """Convert model to database row tuple.

        Returns tuple matching claim_evidence_links table column order:
        (id, claim_id, evidence_chunk_id, binding_type, binding_score, created_at_utc)
        """
        return (
            str(self.id),
            str(self.claim_id),
            str(self.evidence_chunk_id),
            self.binding_type.value,
            self.binding_score,
            self.created_at.isoformat(),
        )

    @classmethod
    def from_db_row(cls, row: Sequence) -> "ClaimEvidenceLink":
        """Reconstruct ClaimEvidenceLink from database row tuple.

        Args:
            row: Tuple/sequence in same order as to_db_row() output:
                (id, claim_id, evidence_chunk_id, binding_type, binding_score, created_at_utc)

        Returns:
            ClaimEvidenceLink instance with all fields populated from DB row.
        """
        return cls(
            id=UUID(row[0]),
            claim_id=UUID(row[1]),
            evidence_chunk_id=UUID(row[2]),
            binding_type=BindingType(row[3]),
            binding_score=row[4],
            created_at=datetime.fromisoformat(row[5]),
        )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440010",
                    "claim_id": "550e8400-e29b-41d4-a716-446655440001",
                    "evidence_chunk_id": "550e8400-e29b-41d4-a716-446655440002",
                    "binding_type": "semantic",
                    "binding_score": 0.92,
                    "created_at": "2024-12-21T12:00:00Z",
                }
            ]
        }
    }
