"""Tests for the ConflictDetectionLinter.

This linter detects conflicting claims on the same topic:
1. DOSE claims: Same drug with different doses (S0 - safety critical)
2. THRESHOLD claims: Contradictory age/value recommendations (S1 - quality critical)

Medical procedures must be internally consistent. Conflicting doses for the
same drug can cause serious patient harm, hence S0 severity.

TDD: Write tests first, then implement the linter.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from procedurewriter.models.claims import Claim, ClaimType
from procedurewriter.models.issues import IssueCode, IssueSeverity


# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_run_id() -> str:
    """Generate a sample run ID."""
    return "conflict_test_run_001"


@pytest.fixture
def consistent_dose_claims(sample_run_id: str) -> list[Claim]:
    """Claims with no conflicts (different drugs or same dose)."""
    return [
        Claim(
            run_id=sample_run_id,
            claim_type=ClaimType.DOSE,
            text="Adrenalin 0.5 mg i.m.",
            normalized_value="0.5",
            unit="mg",
            line_number=10,
            confidence=0.95,
        ),
        Claim(
            run_id=sample_run_id,
            claim_type=ClaimType.DOSE,
            text="Hydrocortison 200 mg i.v.",
            normalized_value="200",
            unit="mg",
            line_number=15,
            confidence=0.92,
        ),
        Claim(
            run_id=sample_run_id,
            claim_type=ClaimType.DOSE,
            text="Salbutamol 2.5 mg nebulisator",
            normalized_value="2.5",
            unit="mg",
            line_number=20,
            confidence=0.90,
        ),
    ]


@pytest.fixture
def conflicting_dose_claims(sample_run_id: str) -> list[Claim]:
    """Claims with conflicting doses for the same drug."""
    return [
        Claim(
            run_id=sample_run_id,
            claim_type=ClaimType.DOSE,
            text="Adrenalin 0.5 mg i.m.",
            normalized_value="0.5",
            unit="mg",
            line_number=10,
            confidence=0.95,
        ),
        Claim(
            run_id=sample_run_id,
            claim_type=ClaimType.DOSE,
            text="Adrenalin 1.0 mg i.v.",
            normalized_value="1.0",
            unit="mg",
            line_number=25,
            confidence=0.93,
        ),
    ]


@pytest.fixture
def conflicting_dose_claims_same_text(sample_run_id: str) -> list[Claim]:
    """Claims with same drug name but different dose values."""
    return [
        Claim(
            run_id=sample_run_id,
            claim_type=ClaimType.DOSE,
            text="amoxicillin 50 mg/kg/d",
            normalized_value="50",
            unit="mg/kg/d",
            line_number=5,
            confidence=0.95,
        ),
        Claim(
            run_id=sample_run_id,
            claim_type=ClaimType.DOSE,
            text="amoxicillin 75 mg/kg/d",
            normalized_value="75",
            unit="mg/kg/d",
            line_number=30,
            confidence=0.92,
        ),
    ]


@pytest.fixture
def claims_same_drug_same_dose(sample_run_id: str) -> list[Claim]:
    """Multiple claims for same drug with same dose (no conflict)."""
    return [
        Claim(
            run_id=sample_run_id,
            claim_type=ClaimType.DOSE,
            text="Adrenalin 0.5 mg i.m. (voksen)",
            normalized_value="0.5",
            unit="mg",
            line_number=10,
            confidence=0.95,
        ),
        Claim(
            run_id=sample_run_id,
            claim_type=ClaimType.DOSE,
            text="Adrenalin 0.5 mg i.m. ved anafylaksi",
            normalized_value="0.5",
            unit="mg",
            line_number=25,
            confidence=0.93,
        ),
    ]


@pytest.fixture
def threshold_claims_no_conflict(sample_run_id: str) -> list[Claim]:
    """Threshold claims with no conflicts."""
    return [
        Claim(
            run_id=sample_run_id,
            claim_type=ClaimType.THRESHOLD,
            text="SpO2 < 92%",
            normalized_value="92",
            unit="%",
            line_number=8,
            confidence=0.94,
        ),
        Claim(
            run_id=sample_run_id,
            claim_type=ClaimType.THRESHOLD,
            text="temperatur > 38.5°C",
            normalized_value="38.5",
            unit="°C",
            line_number=12,
            confidence=0.91,
        ),
    ]


@pytest.fixture
def conflicting_threshold_claims(sample_run_id: str) -> list[Claim]:
    """Threshold claims with conflicting values for same parameter."""
    return [
        Claim(
            run_id=sample_run_id,
            claim_type=ClaimType.THRESHOLD,
            text="SpO2 < 92%",
            normalized_value="92",
            unit="%",
            line_number=8,
            confidence=0.94,
        ),
        Claim(
            run_id=sample_run_id,
            claim_type=ClaimType.THRESHOLD,
            text="SpO2 < 88%",
            normalized_value="88",
            unit="%",
            line_number=20,
            confidence=0.92,
        ),
    ]


# ---------------------------------------------------------------------------
# NO CONFLICT TESTS
# ---------------------------------------------------------------------------


class TestNoConflicts:
    """Tests for procedures with no conflicting claims."""

    def test_no_issues_for_different_drugs(
        self, sample_run_id: str, consistent_dose_claims: list[Claim]
    ) -> None:
        """Different drugs with different doses produce no conflicts."""
        from procedurewriter.evals.conflict import ConflictDetectionLinter
        from procedurewriter.evals.linter import LintContext

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="",
            claims=consistent_dose_claims,
        )

        linter = ConflictDetectionLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 0

    def test_no_issues_for_same_drug_same_dose(
        self, sample_run_id: str, claims_same_drug_same_dose: list[Claim]
    ) -> None:
        """Same drug with same dose in different contexts is not a conflict."""
        from procedurewriter.evals.conflict import ConflictDetectionLinter
        from procedurewriter.evals.linter import LintContext

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="",
            claims=claims_same_drug_same_dose,
        )

        linter = ConflictDetectionLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 0

    def test_no_issues_for_empty_claims(self, sample_run_id: str) -> None:
        """Empty claims list produces no issues."""
        from procedurewriter.evals.conflict import ConflictDetectionLinter
        from procedurewriter.evals.linter import LintContext

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="",
            claims=[],
        )

        linter = ConflictDetectionLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 0

    def test_no_issues_for_non_dose_claims_only(self, sample_run_id: str) -> None:
        """Non-DOSE claims without conflicts produce no issues."""
        from procedurewriter.evals.conflict import ConflictDetectionLinter
        from procedurewriter.evals.linter import LintContext

        claims = [
            Claim(
                run_id=sample_run_id,
                claim_type=ClaimType.RECOMMENDATION,
                text="Patient bør indlægges",
                normalized_value=None,
                line_number=5,
                confidence=0.90,
            ),
            Claim(
                run_id=sample_run_id,
                claim_type=ClaimType.RED_FLAG,
                text="OBS: stridor",
                normalized_value=None,
                line_number=10,
                confidence=0.85,
            ),
        ]

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="",
            claims=claims,
        )

        linter = ConflictDetectionLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 0


# ---------------------------------------------------------------------------
# DOSE CONFLICT TESTS
# ---------------------------------------------------------------------------


class TestDoseConflicts:
    """Tests for detecting conflicting DOSE claims."""

    def test_detects_same_drug_different_dose(
        self, sample_run_id: str, conflicting_dose_claims: list[Claim]
    ) -> None:
        """Same drug with different doses creates a conflict issue."""
        from procedurewriter.evals.conflict import ConflictDetectionLinter
        from procedurewriter.evals.linter import LintContext

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="",
            claims=conflicting_dose_claims,
        )

        linter = ConflictDetectionLinter()
        issues = linter.lint(ctx)

        assert len(issues) >= 1
        assert any(i.code == IssueCode.CONFLICTING_DOSES for i in issues)

    def test_conflicting_doses_is_s0(
        self, sample_run_id: str, conflicting_dose_claims: list[Claim]
    ) -> None:
        """Conflicting doses is S0 (safety critical)."""
        from procedurewriter.evals.conflict import ConflictDetectionLinter
        from procedurewriter.evals.linter import LintContext

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="",
            claims=conflicting_dose_claims,
        )

        linter = ConflictDetectionLinter()
        issues = linter.lint(ctx)

        dose_issues = [i for i in issues if i.code == IssueCode.CONFLICTING_DOSES]
        assert len(dose_issues) >= 1
        assert all(i.severity == IssueSeverity.S0 for i in dose_issues)

    def test_detects_case_insensitive_drug_name(self, sample_run_id: str) -> None:
        """Drug name comparison is case-insensitive."""
        from procedurewriter.evals.conflict import ConflictDetectionLinter
        from procedurewriter.evals.linter import LintContext

        claims = [
            Claim(
                run_id=sample_run_id,
                claim_type=ClaimType.DOSE,
                text="ADRENALIN 0.5 mg i.m.",
                normalized_value="0.5",
                unit="mg",
                line_number=10,
                confidence=0.95,
            ),
            Claim(
                run_id=sample_run_id,
                claim_type=ClaimType.DOSE,
                text="adrenalin 1.0 mg i.v.",
                normalized_value="1.0",
                unit="mg",
                line_number=25,
                confidence=0.93,
            ),
        ]

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="",
            claims=claims,
        )

        linter = ConflictDetectionLinter()
        issues = linter.lint(ctx)

        assert len(issues) >= 1
        assert any(i.code == IssueCode.CONFLICTING_DOSES for i in issues)

    def test_conflict_message_includes_drug_and_doses(
        self, sample_run_id: str, conflicting_dose_claims: list[Claim]
    ) -> None:
        """Conflict issue message includes drug name and conflicting doses."""
        from procedurewriter.evals.conflict import ConflictDetectionLinter
        from procedurewriter.evals.linter import LintContext

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="",
            claims=conflicting_dose_claims,
        )

        linter = ConflictDetectionLinter()
        issues = linter.lint(ctx)

        assert len(issues) >= 1
        msg = issues[0].message.lower()
        # Should mention the drug
        assert "adrenalin" in msg
        # Should mention the conflicting doses
        assert "0.5" in msg or "1.0" in msg

    def test_multiple_conflicting_drugs(self, sample_run_id: str) -> None:
        """Multiple drugs with conflicts each produce separate issues."""
        from procedurewriter.evals.conflict import ConflictDetectionLinter
        from procedurewriter.evals.linter import LintContext

        claims = [
            # Adrenalin conflict
            Claim(
                run_id=sample_run_id,
                claim_type=ClaimType.DOSE,
                text="Adrenalin 0.5 mg",
                normalized_value="0.5",
                unit="mg",
                line_number=10,
                confidence=0.95,
            ),
            Claim(
                run_id=sample_run_id,
                claim_type=ClaimType.DOSE,
                text="Adrenalin 1.0 mg",
                normalized_value="1.0",
                unit="mg",
                line_number=15,
                confidence=0.93,
            ),
            # Hydrocortison conflict
            Claim(
                run_id=sample_run_id,
                claim_type=ClaimType.DOSE,
                text="Hydrocortison 100 mg",
                normalized_value="100",
                unit="mg",
                line_number=20,
                confidence=0.92,
            ),
            Claim(
                run_id=sample_run_id,
                claim_type=ClaimType.DOSE,
                text="Hydrocortison 200 mg",
                normalized_value="200",
                unit="mg",
                line_number=25,
                confidence=0.91,
            ),
        ]

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="",
            claims=claims,
        )

        linter = ConflictDetectionLinter()
        issues = linter.lint(ctx)

        # Should find conflicts for both drugs
        assert len(issues) >= 2


# ---------------------------------------------------------------------------
# THRESHOLD CONFLICT TESTS
# ---------------------------------------------------------------------------


class TestThresholdConflicts:
    """Tests for detecting conflicting THRESHOLD claims."""

    def test_detects_conflicting_threshold_values(
        self, sample_run_id: str, conflicting_threshold_claims: list[Claim]
    ) -> None:
        """Same parameter with different threshold values creates conflict."""
        from procedurewriter.evals.conflict import ConflictDetectionLinter
        from procedurewriter.evals.linter import LintContext

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="",
            claims=conflicting_threshold_claims,
        )

        linter = ConflictDetectionLinter()
        issues = linter.lint(ctx)

        # Should detect SpO2 threshold conflict
        assert len(issues) >= 1

    def test_no_conflict_for_different_parameters(
        self, sample_run_id: str, threshold_claims_no_conflict: list[Claim]
    ) -> None:
        """Different threshold parameters (SpO2 vs temp) don't conflict."""
        from procedurewriter.evals.conflict import ConflictDetectionLinter
        from procedurewriter.evals.linter import LintContext

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="",
            claims=threshold_claims_no_conflict,
        )

        linter = ConflictDetectionLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 0


# ---------------------------------------------------------------------------
# LINTER METADATA TESTS
# ---------------------------------------------------------------------------


class TestLinterMetadata:
    """Tests for linter name and description."""

    def test_linter_name(self) -> None:
        """Linter has correct name."""
        from procedurewriter.evals.conflict import ConflictDetectionLinter

        linter = ConflictDetectionLinter()
        assert linter.name == "conflict_detection"

    def test_linter_description(self) -> None:
        """Linter has a description."""
        from procedurewriter.evals.conflict import ConflictDetectionLinter

        linter = ConflictDetectionLinter()
        assert len(linter.description) > 0
        assert "conflict" in linter.description.lower()

    def test_linter_tracks_issue_count(self, sample_run_id: str) -> None:
        """Linter tracks number of issues found."""
        from procedurewriter.evals.conflict import ConflictDetectionLinter
        from procedurewriter.evals.linter import LintContext

        claims = [
            Claim(
                run_id=sample_run_id,
                claim_type=ClaimType.DOSE,
                text="Adrenalin 0.5 mg",
                normalized_value="0.5",
                unit="mg",
                line_number=10,
                confidence=0.95,
            ),
            Claim(
                run_id=sample_run_id,
                claim_type=ClaimType.DOSE,
                text="Adrenalin 1.0 mg",
                normalized_value="1.0",
                unit="mg",
                line_number=15,
                confidence=0.93,
            ),
        ]

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="",
            claims=claims,
        )

        linter = ConflictDetectionLinter()
        issues = linter.lint(ctx)

        assert linter.last_run_issue_count == len(issues)


# ---------------------------------------------------------------------------
# EDGE CASES
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and unusual inputs."""

    def test_single_claim_no_conflict(self, sample_run_id: str) -> None:
        """Single claim cannot conflict with itself."""
        from procedurewriter.evals.conflict import ConflictDetectionLinter
        from procedurewriter.evals.linter import LintContext

        claims = [
            Claim(
                run_id=sample_run_id,
                claim_type=ClaimType.DOSE,
                text="Adrenalin 0.5 mg",
                normalized_value="0.5",
                unit="mg",
                line_number=10,
                confidence=0.95,
            ),
        ]

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="",
            claims=claims,
        )

        linter = ConflictDetectionLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 0

    def test_claims_missing_normalized_value(self, sample_run_id: str) -> None:
        """Claims without normalized values are handled gracefully."""
        from procedurewriter.evals.conflict import ConflictDetectionLinter
        from procedurewriter.evals.linter import LintContext

        claims = [
            Claim(
                run_id=sample_run_id,
                claim_type=ClaimType.DOSE,
                text="Adrenalin dose as appropriate",
                normalized_value=None,  # No normalized value
                unit="mg",
                line_number=10,
                confidence=0.60,
            ),
            Claim(
                run_id=sample_run_id,
                claim_type=ClaimType.DOSE,
                text="Adrenalin 0.5 mg",
                normalized_value="0.5",
                unit="mg",
                line_number=15,
                confidence=0.95,
            ),
        ]

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="",
            claims=claims,
        )

        linter = ConflictDetectionLinter()
        # Should not raise, should handle gracefully
        issues = linter.lint(ctx)
        # No conflict because one has no normalized value
        assert isinstance(issues, list)

    def test_callable_interface(self, sample_run_id: str) -> None:
        """Linter can be called as a function."""
        from procedurewriter.evals.conflict import ConflictDetectionLinter
        from procedurewriter.evals.linter import LintContext

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="",
            claims=[],
        )

        linter = ConflictDetectionLinter()
        # Should work with function call syntax
        issues = linter(ctx)

        assert isinstance(issues, list)

    def test_different_units_same_drug(self, sample_run_id: str) -> None:
        """Same drug with different units should still detect conflict if values differ."""
        from procedurewriter.evals.conflict import ConflictDetectionLinter
        from procedurewriter.evals.linter import LintContext

        claims = [
            Claim(
                run_id=sample_run_id,
                claim_type=ClaimType.DOSE,
                text="Paracetamol 500 mg",
                normalized_value="500",
                unit="mg",
                line_number=10,
                confidence=0.95,
            ),
            Claim(
                run_id=sample_run_id,
                claim_type=ClaimType.DOSE,
                text="Paracetamol 1000 mg",
                normalized_value="1000",
                unit="mg",
                line_number=15,
                confidence=0.93,
            ),
        ]

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="",
            claims=claims,
        )

        linter = ConflictDetectionLinter()
        issues = linter.lint(ctx)

        # Should detect 500mg vs 1000mg conflict
        assert len(issues) >= 1
        assert any(i.code == IssueCode.CONFLICTING_DOSES for i in issues)
