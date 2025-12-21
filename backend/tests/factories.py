"""Factory functions for test data creation.

These factories provide sensible defaults for model instantiation,
making tests more DRY and readable.

Usage:
    from tests.factories import make_claim, make_evidence_chunk

    # With all defaults
    claim = make_claim()

    # With overrides
    claim = make_claim(claim_type=ClaimType.THRESHOLD, confidence=0.99)
"""

import uuid
from typing import Optional
from uuid import UUID

from procedurewriter.models import (
    Claim,
    ClaimType,
    EvidenceChunk,
    ClaimEvidenceLink,
    BindingType,
    Issue,
    IssueCode,
    IssueSeverity,
    Gate,
    GateStatus,
    GateType,
)


def make_claim(
    *,
    id: Optional[UUID] = None,
    run_id: Optional[str] = None,
    claim_type: ClaimType = ClaimType.DOSE,
    text: str = "Default claim text for testing",
    normalized_value: Optional[str] = None,
    unit: Optional[str] = None,
    source_refs: Optional[list[str]] = None,
    line_number: int = 1,
    confidence: float = 0.9,
) -> Claim:
    """Create a Claim with sensible defaults.

    Args:
        id: UUID for the claim (auto-generated if not provided)
        run_id: Run ID (auto-generated if not provided)
        claim_type: Type of claim (default: DOSE)
        text: Claim text content
        normalized_value: Normalized value (optional)
        unit: Unit of measurement (optional)
        source_refs: Source references (default: empty list)
        line_number: Line number in procedure (default: 1)
        confidence: Confidence score (default: 0.9)

    Returns:
        Claim instance with provided or default values
    """
    return Claim(
        id=id or uuid.uuid4(),
        run_id=run_id or str(uuid.uuid4()),
        claim_type=claim_type,
        text=text,
        normalized_value=normalized_value,
        unit=unit,
        source_refs=source_refs or [],
        line_number=line_number,
        confidence=confidence,
    )


def make_evidence_chunk(
    *,
    id: Optional[UUID] = None,
    run_id: Optional[str] = None,
    source_id: str = "SRC001",
    text: str = "Default evidence text for testing",
    chunk_index: int = 0,
    start_char: Optional[int] = None,
    end_char: Optional[int] = None,
    embedding_vector: Optional[list[float]] = None,
    metadata: Optional[dict] = None,
) -> EvidenceChunk:
    """Create an EvidenceChunk with sensible defaults.

    Args:
        id: UUID for the chunk (auto-generated if not provided)
        run_id: Run ID (auto-generated if not provided)
        source_id: Source identifier (default: "SRC001")
        text: Evidence text content
        chunk_index: Index within source (default: 0)
        start_char: Start character position (optional)
        end_char: End character position (optional)
        embedding_vector: Vector embedding (optional)
        metadata: Additional metadata (default: empty dict)

    Returns:
        EvidenceChunk instance with provided or default values
    """
    return EvidenceChunk(
        id=id or uuid.uuid4(),
        run_id=run_id or str(uuid.uuid4()),
        source_id=source_id,
        text=text,
        chunk_index=chunk_index,
        start_char=start_char,
        end_char=end_char,
        embedding_vector=embedding_vector,
        metadata=metadata or {},
    )


def make_claim_evidence_link(
    *,
    id: Optional[UUID] = None,
    claim: Optional[Claim] = None,
    chunk: Optional[EvidenceChunk] = None,
    claim_id: Optional[UUID] = None,
    evidence_chunk_id: Optional[UUID] = None,
    binding_type: BindingType = BindingType.SEMANTIC,
    binding_score: float = 0.85,
) -> ClaimEvidenceLink:
    """Create a ClaimEvidenceLink with sensible defaults.

    Can accept either full Claim/EvidenceChunk objects (extracting their IDs)
    or direct UUID references.

    Args:
        id: UUID for the link (auto-generated if not provided)
        claim: Claim object (extracts claim_id)
        chunk: EvidenceChunk object (extracts evidence_chunk_id)
        claim_id: Direct claim UUID (used if claim not provided)
        evidence_chunk_id: Direct chunk UUID (used if chunk not provided)
        binding_type: Type of binding (default: SEMANTIC)
        binding_score: Binding confidence score (default: 0.85)

    Returns:
        ClaimEvidenceLink instance with provided or default values
    """
    # Use provided objects' IDs, fall back to direct IDs, then generate
    final_claim_id = claim_id
    if claim is not None:
        final_claim_id = claim.id
    elif final_claim_id is None:
        final_claim_id = uuid.uuid4()

    final_chunk_id = evidence_chunk_id
    if chunk is not None:
        final_chunk_id = chunk.id
    elif final_chunk_id is None:
        final_chunk_id = uuid.uuid4()

    return ClaimEvidenceLink(
        id=id or uuid.uuid4(),
        claim_id=final_claim_id,
        evidence_chunk_id=final_chunk_id,
        binding_type=binding_type,
        binding_score=binding_score,
    )


def make_issue(
    *,
    id: Optional[UUID] = None,
    run_id: Optional[str] = None,
    code: IssueCode = IssueCode.DOSE_WITHOUT_EVIDENCE,
    severity: IssueSeverity = IssueSeverity.S0,
    message: str = "Default issue message for testing",
    line_number: Optional[int] = None,
    claim_id: Optional[UUID] = None,
    source_id: Optional[str] = None,
    auto_detected: bool = True,
    resolved: bool = False,
    resolution_note: Optional[str] = None,
) -> Issue:
    """Create an Issue with sensible defaults.

    Args:
        id: UUID for the issue (auto-generated if not provided)
        run_id: Run ID (auto-generated if not provided)
        code: Issue code (default: DOSE_WITHOUT_EVIDENCE, an S0 issue)
        severity: Issue severity (default: S0 for safety)
        message: Issue description
        line_number: Line number where issue was detected (optional)
        claim_id: Related claim UUID (optional)
        source_id: Related source ID (optional)
        auto_detected: Whether auto-detected (default: True)
        resolved: Whether resolved (default: False)
        resolution_note: Resolution explanation (optional)

    Returns:
        Issue instance with provided or default values
    """
    return Issue(
        id=id or uuid.uuid4(),
        run_id=run_id or str(uuid.uuid4()),
        code=code,
        severity=severity,
        message=message,
        line_number=line_number,
        claim_id=claim_id,
        source_id=source_id,
        auto_detected=auto_detected,
        resolved=resolved,
        resolution_note=resolution_note,
    )


def make_gate(
    *,
    id: Optional[UUID] = None,
    run_id: Optional[str] = None,
    gate_type: GateType = GateType.S0_SAFETY,
    status: GateStatus = GateStatus.PENDING,
    issues_checked: int = 0,
    issues_failed: int = 0,
    message: Optional[str] = None,
) -> Gate:
    """Create a Gate with sensible defaults.

    Args:
        id: UUID for the gate (auto-generated if not provided)
        run_id: Run ID (auto-generated if not provided)
        gate_type: Type of gate (default: S0_SAFETY)
        status: Gate status (default: PENDING)
        issues_checked: Number of issues checked (default: 0)
        issues_failed: Number of failed issues (default: 0)
        message: Status message (optional)

    Returns:
        Gate instance with provided or default values
    """
    return Gate(
        id=id or uuid.uuid4(),
        run_id=run_id or str(uuid.uuid4()),
        gate_type=gate_type,
        status=status,
        issues_checked=issues_checked,
        issues_failed=issues_failed,
        message=message,
    )
