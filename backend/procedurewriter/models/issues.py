"""Issue and IssueSeverity models for the auditable procedure system.

These models represent issues detected during procedure evaluation.

Issue Severity (from Phase 0 S0/S1/S2 taxonomy):
- S0: Ship-blocking, safety-critical (7 issue types)
- S1: Ship-blocking, quality-critical (6 issue types)
- S2: Warning, non-blocking (4 issue types)
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class IssueSeverity(str, Enum):
    """Severity level for issues detected during evaluation.

    S0: Safety-critical, ship-blocking
    S1: Quality-critical, ship-blocking
    S2: Warning, non-blocking
    """

    S0 = "s0"
    S1 = "s1"
    S2 = "s2"


class IssueCode(str, Enum):
    """Specific issue codes from Phase 0 S0/S1/S2 taxonomy.

    S0: Safety-critical (7 types)
    S1: Quality-critical (6 types)
    S2: Warnings (4 types)
    """

    # S0: Safety-critical (ship-blocking)
    ORPHAN_CITATION = "S0-001"  # Citation [CIT-X] not in sources
    HALLUCINATED_SOURCE = "S0-002"  # Source ID doesn't exist
    DOSE_WITHOUT_EVIDENCE = "S0-003"  # DOSE claim has no source ref
    THRESHOLD_WITHOUT_EVIDENCE = "S0-004"  # THRESHOLD claim has no source ref
    CONTRAINDICATION_UNBOUND = "S0-005"  # CONTRAINDICATION without evidence
    CONFLICTING_DOSES = "S0-006"  # Same drug, different doses, same tier
    MISSING_MANDATORY_SECTION = "S0-007"  # Required section empty/missing

    # S1: Quality-critical (ship-blocking)
    CLAIM_BINDING_FAILED = "S1-001"  # Claim couldn't be matched to evidence
    WEAK_EVIDENCE_FOR_STRONG_CLAIM = "S1-002"  # Tier 7+ for definitive statement
    OUTDATED_GUIDELINE = "S1-003"  # Source >5 years old
    TEMPLATE_INCOMPLETE = "S1-004"  # Section present but <100 chars
    UNIT_MISMATCH = "S1-005"  # Inconsistent units in same section
    AGE_GROUP_CONFLICT = "S1-006"  # Contradictory age recommendations

    # S2: Warnings (non-blocking)
    DANISH_TERM_VARIANT = "S2-001"  # Multiple spellings of same term
    EVIDENCE_REDUNDANCY = "S2-002"  # Same claim bound to >3 sources
    INFORMAL_LANGUAGE = "S2-003"  # Non-clinical phrasing detected
    MISSING_DURATION = "S2-004"  # Treatment without duration specified


# Mapping of issue codes to their severity
_CODE_TO_SEVERITY = {
    # S0
    IssueCode.ORPHAN_CITATION: IssueSeverity.S0,
    IssueCode.HALLUCINATED_SOURCE: IssueSeverity.S0,
    IssueCode.DOSE_WITHOUT_EVIDENCE: IssueSeverity.S0,
    IssueCode.THRESHOLD_WITHOUT_EVIDENCE: IssueSeverity.S0,
    IssueCode.CONTRAINDICATION_UNBOUND: IssueSeverity.S0,
    IssueCode.CONFLICTING_DOSES: IssueSeverity.S0,
    IssueCode.MISSING_MANDATORY_SECTION: IssueSeverity.S0,
    # S1
    IssueCode.CLAIM_BINDING_FAILED: IssueSeverity.S1,
    IssueCode.WEAK_EVIDENCE_FOR_STRONG_CLAIM: IssueSeverity.S1,
    IssueCode.OUTDATED_GUIDELINE: IssueSeverity.S1,
    IssueCode.TEMPLATE_INCOMPLETE: IssueSeverity.S1,
    IssueCode.UNIT_MISMATCH: IssueSeverity.S1,
    IssueCode.AGE_GROUP_CONFLICT: IssueSeverity.S1,
    # S2
    IssueCode.DANISH_TERM_VARIANT: IssueSeverity.S2,
    IssueCode.EVIDENCE_REDUNDANCY: IssueSeverity.S2,
    IssueCode.INFORMAL_LANGUAGE: IssueSeverity.S2,
    IssueCode.MISSING_DURATION: IssueSeverity.S2,
}

# Human-readable labels for severity levels
_SEVERITY_LABELS = {
    IssueSeverity.S0: "Safety Critical",
    IssueSeverity.S1: "Quality Critical",
    IssueSeverity.S2: "Warning",
}


class Issue(BaseModel):
    """An issue detected during procedure evaluation.

    Issues represent problems found during the evaluation pipeline,
    categorized by severity (S0/S1/S2) and specific issue code.

    Attributes:
        id: Unique identifier (auto-generated UUID).
        run_id: The procedure run this issue belongs to.
        code: Specific issue code (e.g., S0-001).
        severity: Severity level (S0, S1, or S2).
        message: Human-readable description of the issue.
        line_number: Line number where issue was detected (optional).
        claim_id: UUID of related claim if applicable.
        source_id: ID of related source if applicable.
        auto_detected: Whether issue was auto-detected vs manual.
        resolved: Whether issue has been resolved.
        resolution_note: Note explaining how issue was resolved.
        resolved_at: Timestamp when issue was resolved.
        created_at: Timestamp when issue was created.
    """

    id: UUID = Field(default_factory=uuid4)
    run_id: str = Field(..., description="The procedure run this issue belongs to")
    code: IssueCode = Field(..., description="Specific issue code")
    severity: IssueSeverity = Field(..., description="Severity level")
    message: Annotated[str, Field(min_length=1, description="Issue description")]
    line_number: int | None = Field(
        default=None, ge=1, description="Line number in procedure"
    )
    claim_id: UUID | None = Field(
        default=None, description="UUID of related claim"
    )
    source_id: str | None = Field(
        default=None, description="ID of related source"
    )
    auto_detected: bool = Field(
        default=True, description="Whether issue was auto-detected"
    )
    resolved: bool = Field(default=False, description="Whether issue is resolved")
    resolution_note: str | None = Field(
        default=None, description="How issue was resolved"
    )
    resolved_at: datetime | None = Field(
        default=None, description="When issue was resolved"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when issue was created",
    )

    @property
    def is_blocking(self) -> bool:
        """Check if this issue blocks shipping (S0 or S1)."""
        return self.severity in (IssueSeverity.S0, IssueSeverity.S1)

    @property
    def is_safety_critical(self) -> bool:
        """Check if this issue is safety-critical (S0 only)."""
        return self.severity == IssueSeverity.S0

    @property
    def severity_label(self) -> str:
        """Get human-readable severity label."""
        return _SEVERITY_LABELS[self.severity]

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "run_id": "5e5bbba1790a48d5ae1cf7cc270cfc6f",
                    "code": "S0-003",
                    "severity": "s0",
                    "message": "Dose claim 'amoxicillin 50mg' has no source reference",
                    "line_number": 42,
                    "auto_detected": True,
                    "resolved": False,
                    "created_at": "2024-12-21T12:00:00Z",
                }
            ]
        }
    }
