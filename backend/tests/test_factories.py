"""TDD tests for model factory functions.

Factory functions provide DRY test data creation with sensible defaults.
"""

import uuid
from uuid import UUID

import pytest

from tests.factories import (
    make_claim,
    make_evidence_chunk,
    make_claim_evidence_link,
    make_issue,
    make_gate,
)
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


class TestClaimFactory:
    """Tests for make_claim factory function."""

    def test_make_claim_returns_claim(self):
        """Factory should return a Claim instance."""
        claim = make_claim()
        assert isinstance(claim, Claim)

    def test_make_claim_has_uuid_id(self):
        """Factory should generate UUID id."""
        claim = make_claim()
        assert isinstance(claim.id, UUID)

    def test_make_claim_has_run_id(self):
        """Factory should set a run_id."""
        claim = make_claim()
        assert claim.run_id is not None
        assert len(claim.run_id) > 0

    def test_make_claim_allows_override(self):
        """Factory should allow overriding any field."""
        claim = make_claim(
            claim_type=ClaimType.THRESHOLD,
            text="Custom text",
            confidence=0.99,
        )
        assert claim.claim_type == ClaimType.THRESHOLD
        assert claim.text == "Custom text"
        assert claim.confidence == 0.99

    def test_make_claim_with_run_id(self):
        """Factory should accept explicit run_id."""
        run_id = "test-run-123"
        claim = make_claim(run_id=run_id)
        assert claim.run_id == run_id


class TestEvidenceChunkFactory:
    """Tests for make_evidence_chunk factory function."""

    def test_make_evidence_chunk_returns_chunk(self):
        """Factory should return an EvidenceChunk instance."""
        chunk = make_evidence_chunk()
        assert isinstance(chunk, EvidenceChunk)

    def test_make_evidence_chunk_has_defaults(self):
        """Factory should have sensible defaults."""
        chunk = make_evidence_chunk()
        assert chunk.source_id is not None
        assert chunk.text is not None
        assert chunk.chunk_index >= 0

    def test_make_evidence_chunk_allows_override(self):
        """Factory should allow overriding any field."""
        chunk = make_evidence_chunk(
            source_id="SRC-999",
            text="Custom evidence text",
        )
        assert chunk.source_id == "SRC-999"
        assert chunk.text == "Custom evidence text"


class TestClaimEvidenceLinkFactory:
    """Tests for make_claim_evidence_link factory function."""

    def test_make_link_returns_link(self):
        """Factory should return a ClaimEvidenceLink instance."""
        link = make_claim_evidence_link()
        assert isinstance(link, ClaimEvidenceLink)

    def test_make_link_with_claim_and_chunk(self):
        """Factory should accept claim and chunk to extract IDs."""
        claim = make_claim()
        chunk = make_evidence_chunk()
        link = make_claim_evidence_link(claim=claim, chunk=chunk)
        assert link.claim_id == claim.id
        assert link.evidence_chunk_id == chunk.id

    def test_make_link_allows_id_override(self):
        """Factory should allow direct ID override."""
        claim_id = uuid.uuid4()
        chunk_id = uuid.uuid4()
        link = make_claim_evidence_link(
            claim_id=claim_id,
            evidence_chunk_id=chunk_id,
        )
        assert link.claim_id == claim_id
        assert link.evidence_chunk_id == chunk_id


class TestIssueFactory:
    """Tests for make_issue factory function."""

    def test_make_issue_returns_issue(self):
        """Factory should return an Issue instance."""
        issue = make_issue()
        assert isinstance(issue, Issue)

    def test_make_issue_has_s0_default(self):
        """Factory should default to S0 severity for safety."""
        issue = make_issue()
        assert issue.severity == IssueSeverity.S0

    def test_make_issue_allows_severity_override(self):
        """Factory should allow overriding severity."""
        issue = make_issue(severity=IssueSeverity.S2)
        assert issue.severity == IssueSeverity.S2

    def test_make_issue_allows_code_override(self):
        """Factory should allow overriding issue code."""
        issue = make_issue(code=IssueCode.OUTDATED_GUIDELINE)
        assert issue.code == IssueCode.OUTDATED_GUIDELINE


class TestGateFactory:
    """Tests for make_gate factory function."""

    def test_make_gate_returns_gate(self):
        """Factory should return a Gate instance."""
        gate = make_gate()
        assert isinstance(gate, Gate)

    def test_make_gate_defaults_pending(self):
        """Factory should default to PENDING status."""
        gate = make_gate()
        assert gate.status == GateStatus.PENDING

    def test_make_gate_allows_override(self):
        """Factory should allow overriding any field."""
        gate = make_gate(
            gate_type=GateType.FINAL,
            status=GateStatus.PASS,
            issues_checked=10,
        )
        assert gate.gate_type == GateType.FINAL
        assert gate.status == GateStatus.PASS
        assert gate.issues_checked == 10
