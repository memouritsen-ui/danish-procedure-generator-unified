"""Gate and GateStatus models for the auditable procedure system.

Gates are checkpoints in the pipeline that determine if procedure can proceed:
- S0 gate: Must have 0 S0 (safety-critical) issues to pass
- S1 gate: Must have 0 S1 (quality-critical) issues to pass
- Final gate: All gates must pass for release
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class GateStatus(str, Enum):
    """Status of a pipeline gate evaluation."""

    PASS = "pass"
    FAIL = "fail"
    PENDING = "pending"


class GateType(str, Enum):
    """Type of pipeline gate."""

    S0_SAFETY = "s0_safety"  # Safety-critical gate (S0 issues)
    S1_QUALITY = "s1_quality"  # Quality-critical gate (S1 issues)
    FINAL = "final"  # Final release gate (all must pass)


# Human-readable labels for gate types
_GATE_LABELS = {
    GateType.S0_SAFETY: "Safety Gate (S0)",
    GateType.S1_QUALITY: "Quality Gate (S1)",
    GateType.FINAL: "Final Gate",
}


class Gate(BaseModel):
    """A pipeline gate that determines if procedure can proceed.

    Gates are checkpoints that evaluate whether a procedure has passed
    all required checks. S0 and S1 gates check for specific issue types,
    while the final gate ensures all gates have passed.

    Attributes:
        id: Unique identifier (auto-generated UUID).
        run_id: The procedure run this gate belongs to.
        gate_type: Type of gate (S0_SAFETY, S1_QUALITY, FINAL).
        status: Current status (PASS, FAIL, PENDING).
        issues_checked: Number of issues evaluated.
        issues_failed: Number of issues that caused failure.
        message: Optional message about gate status.
        created_at: Timestamp when gate was created.
        evaluated_at: Timestamp when gate was evaluated.
    """

    id: UUID = Field(default_factory=uuid4)
    run_id: str = Field(..., description="The procedure run this gate belongs to")
    gate_type: GateType = Field(..., description="Type of gate")
    status: GateStatus = Field(..., description="Current gate status")
    issues_checked: int = Field(
        default=0, ge=0, description="Number of issues evaluated"
    )
    issues_failed: int = Field(
        default=0, ge=0, description="Number of failed issues"
    )
    message: str | None = Field(
        default=None, description="Optional status message"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when gate was created",
    )
    evaluated_at: datetime | None = Field(
        default=None, description="Timestamp when gate was evaluated"
    )

    @model_validator(mode="after")
    def validate_issues_counts(self) -> "Gate":
        """Validate that issues_failed does not exceed issues_checked."""
        if self.issues_failed > self.issues_checked:
            raise ValueError("issues_failed cannot exceed issues_checked")
        return self

    @property
    def is_passed(self) -> bool:
        """Check if gate has passed."""
        return self.status == GateStatus.PASS

    @property
    def is_evaluated(self) -> bool:
        """Check if gate has been evaluated (not pending)."""
        return self.status != GateStatus.PENDING

    @property
    def is_safety_gate(self) -> bool:
        """Check if this is a safety-critical gate."""
        return self.gate_type == GateType.S0_SAFETY

    @property
    def gate_label(self) -> str:
        """Get human-readable gate label."""
        return _GATE_LABELS[self.gate_type]

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "run_id": "5e5bbba1790a48d5ae1cf7cc270cfc6f",
                    "gate_type": "s0_safety",
                    "status": "pass",
                    "issues_checked": 15,
                    "issues_failed": 0,
                    "message": "All safety checks passed",
                    "created_at": "2024-12-21T12:00:00Z",
                    "evaluated_at": "2024-12-21T12:05:00Z",
                }
            ]
        }
    }
