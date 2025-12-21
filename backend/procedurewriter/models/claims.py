"""Claim and ClaimType models for the auditable procedure system.

These models represent verifiable medical claims extracted from procedures.

Claim Types (from Phase 0 spec):
- DOSE: Drug dosages (e.g., "amoxicillin 50 mg/kg/d")
- THRESHOLD: Clinical thresholds (e.g., "CURB-65 >= 3", "sat < 92%")
- RECOMMENDATION: Clinical recommendations (e.g., "bor indlaegges")
- CONTRAINDICATION: When NOT to do something
- RED_FLAG: Warning signs requiring action
- ALGORITHM_STEP: Numbered procedure steps
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Sequence
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ClaimType(str, Enum):
    """Type of medical claim extracted from procedure text."""

    DOSE = "dose"
    THRESHOLD = "threshold"
    RECOMMENDATION = "recommendation"
    CONTRAINDICATION = "contraindication"
    RED_FLAG = "red_flag"
    ALGORITHM_STEP = "algorithm_step"


class Claim(BaseModel):
    """A verifiable medical claim extracted from a procedure.

    Claims represent specific, checkable statements that must be traceable
    to evidence sources. Each claim has a type, the original text, optional
    normalized value/unit, and confidence score.

    Attributes:
        id: Unique identifier (auto-generated UUID).
        run_id: The procedure run this claim belongs to.
        claim_type: Type of claim (dose, threshold, etc.).
        text: Original claim text from the procedure.
        normalized_value: Standardized representation of the claim value.
        unit: Unit of measurement if applicable (e.g., "mg/kg/d").
        source_refs: List of source reference IDs (e.g., ["SRC0023"]).
        line_number: Line number in the procedure where claim was found.
        confidence: Extraction confidence score (0.0-1.0).
        created_at: Timestamp when claim was created.
    """

    id: UUID = Field(default_factory=uuid4)
    run_id: str = Field(..., description="The procedure run this claim belongs to")
    claim_type: ClaimType = Field(..., description="Type of medical claim")
    text: Annotated[str, Field(min_length=1, description="Original claim text")]
    normalized_value: str | None = Field(
        default=None, description="Standardized representation"
    )
    unit: str | None = Field(default=None, description="Unit of measurement")
    source_refs: list[str] = Field(
        default_factory=list, description="Source reference IDs"
    )
    line_number: int = Field(..., ge=1, description="Line number in procedure")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Extraction confidence (0-1)"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when claim was created",
    )

    @property
    def has_sources(self) -> bool:
        """Check if claim has associated source references."""
        return len(self.source_refs) > 0

    @property
    def is_high_confidence(self) -> bool:
        """Check if claim has high confidence (>= 0.8)."""
        return self.confidence >= 0.8

    def to_db_row(self) -> tuple:
        """Convert model to database row tuple.

        Returns tuple matching claims table column order:
        (id, run_id, claim_type, text, normalized_value, unit,
         source_refs_json, line_number, confidence, created_at_utc)
        """
        return (
            str(self.id),
            self.run_id,
            self.claim_type.value,
            self.text,
            self.normalized_value,
            self.unit,
            json.dumps(self.source_refs),
            self.line_number,
            self.confidence,
            self.created_at.isoformat(),
        )

    @classmethod
    def from_db_row(cls, row: Sequence) -> "Claim":
        """Reconstruct Claim from database row tuple.

        Args:
            row: Tuple/sequence in same order as to_db_row() output:
                (id, run_id, claim_type, text, normalized_value, unit,
                 source_refs_json, line_number, confidence, created_at_utc)

        Returns:
            Claim instance with all fields populated from DB row.
        """
        return cls(
            id=UUID(row[0]),
            run_id=row[1],
            claim_type=ClaimType(row[2]),
            text=row[3],
            normalized_value=row[4],
            unit=row[5],
            source_refs=json.loads(row[6]) if row[6] else [],
            line_number=row[7],
            confidence=row[8],
            created_at=datetime.fromisoformat(row[9]),
        )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "run_id": "5e5bbba1790a48d5ae1cf7cc270cfc6f",
                    "claim_type": "dose",
                    "text": "amoxicillin 50 mg/kg/d fordelt pa 2-3 doser",
                    "normalized_value": "50",
                    "unit": "mg/kg/d",
                    "source_refs": ["SRC0023"],
                    "line_number": 15,
                    "confidence": 0.9,
                    "created_at": "2024-12-21T12:00:00Z",
                }
            ]
        }
    }
