"""Tests for Issue and IssueSeverity models.

TDD: These tests are written FIRST before implementation.
Run: pytest tests/models/test_issues.py -v

Issue Severity (from Phase 0 S0/S1/S2 taxonomy):
- S0: Ship-blocking, safety-critical (7 issue types)
- S1: Ship-blocking, quality-critical (6 issue types)
- S2: Warning, non-blocking (4 issue types)
"""

from datetime import datetime
from uuid import UUID

import pytest


class TestIssueSeverity:
    """Tests for IssueSeverity enum."""

    def test_issue_severity_has_all_levels(self):
        """IssueSeverity enum should have S0, S1, S2 levels."""
        from procedurewriter.models.issues import IssueSeverity

        assert IssueSeverity.S0.value == "s0"
        assert IssueSeverity.S1.value == "s1"
        assert IssueSeverity.S2.value == "s2"

    def test_issue_severity_count(self):
        """Should have exactly 3 severity levels."""
        from procedurewriter.models.issues import IssueSeverity

        assert len(IssueSeverity) == 3

    def test_issue_severity_from_string(self):
        """Should be able to get IssueSeverity from string."""
        from procedurewriter.models.issues import IssueSeverity

        assert IssueSeverity("s0") == IssueSeverity.S0
        assert IssueSeverity("s1") == IssueSeverity.S1
        assert IssueSeverity("s2") == IssueSeverity.S2


class TestIssueCode:
    """Tests for IssueCode enum."""

    def test_s0_issue_codes_exist(self):
        """S0 safety-critical issue codes should exist."""
        from procedurewriter.models.issues import IssueCode

        # 7 S0 issue types from Phase 0 taxonomy
        assert IssueCode.ORPHAN_CITATION.value == "S0-001"
        assert IssueCode.HALLUCINATED_SOURCE.value == "S0-002"
        assert IssueCode.DOSE_WITHOUT_EVIDENCE.value == "S0-003"
        assert IssueCode.THRESHOLD_WITHOUT_EVIDENCE.value == "S0-004"
        assert IssueCode.CONTRAINDICATION_UNBOUND.value == "S0-005"
        assert IssueCode.CONFLICTING_DOSES.value == "S0-006"
        assert IssueCode.MISSING_MANDATORY_SECTION.value == "S0-007"

    def test_s1_issue_codes_exist(self):
        """S1 quality-critical issue codes should exist."""
        from procedurewriter.models.issues import IssueCode

        # 6 S1 issue types from Phase 0 taxonomy
        assert IssueCode.CLAIM_BINDING_FAILED.value == "S1-001"
        assert IssueCode.WEAK_EVIDENCE_FOR_STRONG_CLAIM.value == "S1-002"
        assert IssueCode.OUTDATED_GUIDELINE.value == "S1-003"
        assert IssueCode.TEMPLATE_INCOMPLETE.value == "S1-004"
        assert IssueCode.UNIT_MISMATCH.value == "S1-005"
        assert IssueCode.AGE_GROUP_CONFLICT.value == "S1-006"

    def test_s2_issue_codes_exist(self):
        """S2 warning issue codes should exist."""
        from procedurewriter.models.issues import IssueCode

        # 4 S2 issue types from Phase 0 taxonomy
        assert IssueCode.DANISH_TERM_VARIANT.value == "S2-001"
        assert IssueCode.EVIDENCE_REDUNDANCY.value == "S2-002"
        assert IssueCode.INFORMAL_LANGUAGE.value == "S2-003"
        assert IssueCode.MISSING_DURATION.value == "S2-004"

    def test_issue_code_count(self):
        """Should have exactly 17 issue codes (7+6+4)."""
        from procedurewriter.models.issues import IssueCode

        assert len(IssueCode) == 17


class TestIssue:
    """Tests for Issue Pydantic model."""

    def test_issue_creation_minimal(self):
        """Should create Issue with minimal required fields."""
        from procedurewriter.models.issues import Issue, IssueCode, IssueSeverity

        issue = Issue(
            run_id="test-run-123",
            code=IssueCode.ORPHAN_CITATION,
            severity=IssueSeverity.S0,
            message="Citation [CIT-99] not found in sources",
        )

        assert issue.run_id == "test-run-123"
        assert issue.code == IssueCode.ORPHAN_CITATION
        assert issue.severity == IssueSeverity.S0
        assert issue.message == "Citation [CIT-99] not found in sources"
        assert issue.line_number is None
        assert issue.claim_id is None
        assert issue.source_id is None
        assert issue.auto_detected is True
        assert issue.resolved is False

    def test_issue_creation_full(self):
        """Should create Issue with all fields populated."""
        from procedurewriter.models.issues import Issue, IssueCode, IssueSeverity

        issue = Issue(
            run_id="test-run-456",
            code=IssueCode.DOSE_WITHOUT_EVIDENCE,
            severity=IssueSeverity.S0,
            message="Dose claim 'amoxicillin 50mg' has no source reference",
            line_number=42,
            claim_id="550e8400-e29b-41d4-a716-446655440001",
            source_id=None,
            auto_detected=True,
            resolved=False,
            resolution_note=None,
        )

        assert issue.run_id == "test-run-456"
        assert issue.code == IssueCode.DOSE_WITHOUT_EVIDENCE
        assert issue.line_number == 42
        assert str(issue.claim_id) == "550e8400-e29b-41d4-a716-446655440001"

    def test_issue_has_auto_id(self):
        """Issue should auto-generate a UUID id."""
        from procedurewriter.models.issues import Issue, IssueCode, IssueSeverity

        issue = Issue(
            run_id="test-run",
            code=IssueCode.ORPHAN_CITATION,
            severity=IssueSeverity.S0,
            message="Test issue",
        )

        assert issue.id is not None
        UUID(str(issue.id))

    def test_issue_has_created_at(self):
        """Issue should have auto-generated created_at timestamp."""
        from procedurewriter.models.issues import Issue, IssueCode, IssueSeverity

        issue = Issue(
            run_id="test-run",
            code=IssueCode.ORPHAN_CITATION,
            severity=IssueSeverity.S0,
            message="Test issue",
        )

        assert issue.created_at is not None
        assert isinstance(issue.created_at, datetime)

    def test_issue_message_required(self):
        """Message field should be required and non-empty."""
        from pydantic import ValidationError

        from procedurewriter.models.issues import Issue, IssueCode, IssueSeverity

        with pytest.raises(ValidationError):
            Issue(
                run_id="test-run",
                code=IssueCode.ORPHAN_CITATION,
                severity=IssueSeverity.S0,
                message="",  # Invalid: empty
            )

    def test_issue_serialization(self):
        """Should serialize to dict/JSON properly."""
        from procedurewriter.models.issues import Issue, IssueCode, IssueSeverity

        issue = Issue(
            run_id="test-run",
            code=IssueCode.WEAK_EVIDENCE_FOR_STRONG_CLAIM,
            severity=IssueSeverity.S1,
            message="Using tier 8 evidence for definitive statement",
            line_number=25,
        )

        data = issue.model_dump()

        assert data["run_id"] == "test-run"
        assert data["code"] == "S1-002"
        assert data["severity"] == "s1"
        assert data["message"] == "Using tier 8 evidence for definitive statement"
        assert data["line_number"] == 25
        assert "id" in data
        assert "created_at" in data

    def test_issue_deserialization(self):
        """Should deserialize from dict properly."""
        from procedurewriter.models.issues import Issue, IssueCode, IssueSeverity

        data = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "run_id": "test-run",
            "code": "S0-003",
            "severity": "s0",
            "message": "Dose without evidence",
            "line_number": 15,
            "auto_detected": True,
            "resolved": False,
            "created_at": "2024-12-21T12:00:00Z",
        }

        issue = Issue.model_validate(data)

        assert issue.run_id == "test-run"
        assert issue.code == IssueCode.DOSE_WITHOUT_EVIDENCE
        assert issue.severity == IssueSeverity.S0


class TestIssueHelpers:
    """Tests for helper methods on Issue model."""

    def test_is_blocking_property(self):
        """S0 and S1 issues should be blocking, S2 should not."""
        from procedurewriter.models.issues import Issue, IssueCode, IssueSeverity

        s0_issue = Issue(
            run_id="test-run",
            code=IssueCode.ORPHAN_CITATION,
            severity=IssueSeverity.S0,
            message="Test",
        )
        assert s0_issue.is_blocking is True

        s1_issue = Issue(
            run_id="test-run",
            code=IssueCode.CLAIM_BINDING_FAILED,
            severity=IssueSeverity.S1,
            message="Test",
        )
        assert s1_issue.is_blocking is True

        s2_issue = Issue(
            run_id="test-run",
            code=IssueCode.INFORMAL_LANGUAGE,
            severity=IssueSeverity.S2,
            message="Test",
        )
        assert s2_issue.is_blocking is False

    def test_is_safety_critical_property(self):
        """Only S0 issues should be safety critical."""
        from procedurewriter.models.issues import Issue, IssueCode, IssueSeverity

        s0_issue = Issue(
            run_id="test-run",
            code=IssueCode.CONFLICTING_DOSES,
            severity=IssueSeverity.S0,
            message="Test",
        )
        assert s0_issue.is_safety_critical is True

        s1_issue = Issue(
            run_id="test-run",
            code=IssueCode.OUTDATED_GUIDELINE,
            severity=IssueSeverity.S1,
            message="Test",
        )
        assert s1_issue.is_safety_critical is False

    def test_severity_label_property(self):
        """Should have human-readable severity labels."""
        from procedurewriter.models.issues import Issue, IssueCode, IssueSeverity

        s0 = Issue(
            run_id="test-run",
            code=IssueCode.ORPHAN_CITATION,
            severity=IssueSeverity.S0,
            message="Test",
        )
        assert s0.severity_label == "Safety Critical"

        s1 = Issue(
            run_id="test-run",
            code=IssueCode.CLAIM_BINDING_FAILED,
            severity=IssueSeverity.S1,
            message="Test",
        )
        assert s1.severity_label == "Quality Critical"

        s2 = Issue(
            run_id="test-run",
            code=IssueCode.DANISH_TERM_VARIANT,
            severity=IssueSeverity.S2,
            message="Test",
        )
        assert s2.severity_label == "Warning"


class TestIssueResolution:
    """Tests for issue resolution workflow."""

    def test_issue_resolution(self):
        """Should be able to mark issue as resolved with note."""
        from procedurewriter.models.issues import Issue, IssueCode, IssueSeverity

        issue = Issue(
            run_id="test-run",
            code=IssueCode.ORPHAN_CITATION,
            severity=IssueSeverity.S0,
            message="Citation [CIT-99] not found",
            resolved=True,
            resolution_note="Added source SRC0099 to sources.jsonl",
        )

        assert issue.resolved is True
        assert issue.resolution_note == "Added source SRC0099 to sources.jsonl"

    def test_resolved_at_timestamp(self):
        """Resolved issues should have resolved_at timestamp when resolved."""
        from procedurewriter.models.issues import Issue, IssueCode, IssueSeverity

        resolved_issue = Issue(
            run_id="test-run",
            code=IssueCode.ORPHAN_CITATION,
            severity=IssueSeverity.S0,
            message="Test",
            resolved=True,
            resolved_at="2024-12-21T14:00:00Z",
        )

        assert resolved_issue.resolved_at is not None

        unresolved = Issue(
            run_id="test-run",
            code=IssueCode.ORPHAN_CITATION,
            severity=IssueSeverity.S0,
            message="Test",
        )
        assert unresolved.resolved_at is None
