"""Tests for the ClaimCoverageLinter.

This linter checks that all claims have been bound to evidence.
Unbound claims are issues - severity depends on claim type.

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
    return "coverage_test_run_001"


@pytest.fixture
def dose_claim() -> Claim:
    """A DOSE claim that is unbound."""
    return Claim(
        id=uuid4(),
        run_id="test_run",
        claim_type=ClaimType.DOSE,
        text="Amoxicillin 50 mg/kg/dag fordelt på 3 doser",
        normalized_value="50",
        unit="mg/kg/dag",
        line_number=10,
        confidence=0.95,
    )


@pytest.fixture
def threshold_claim() -> Claim:
    """A THRESHOLD claim that is unbound."""
    return Claim(
        id=uuid4(),
        run_id="test_run",
        claim_type=ClaimType.THRESHOLD,
        text="CURB-65 score >= 3",
        normalized_value=">=3",
        unit="score",
        line_number=20,
        confidence=0.90,
    )


@pytest.fixture
def contraindication_claim() -> Claim:
    """A CONTRAINDICATION claim that is unbound."""
    return Claim(
        id=uuid4(),
        run_id="test_run",
        claim_type=ClaimType.CONTRAINDICATION,
        text="Kontraindiceret ved penicillinallergi",
        line_number=30,
        confidence=0.95,
    )


@pytest.fixture
def recommendation_claim() -> Claim:
    """A RECOMMENDATION claim that is unbound."""
    return Claim(
        id=uuid4(),
        run_id="test_run",
        claim_type=ClaimType.RECOMMENDATION,
        text="Patienter bør indlægges til observation",
        line_number=40,
        confidence=0.85,
    )


@pytest.fixture
def red_flag_claim() -> Claim:
    """A RED_FLAG claim that is unbound."""
    return Claim(
        id=uuid4(),
        run_id="test_run",
        claim_type=ClaimType.RED_FLAG,
        text="Sepsis-tegn kræver omgående handling",
        line_number=50,
        confidence=0.90,
    )


@pytest.fixture
def algorithm_step_claim() -> Claim:
    """An ALGORITHM_STEP claim that is unbound."""
    return Claim(
        id=uuid4(),
        run_id="test_run",
        claim_type=ClaimType.ALGORITHM_STEP,
        text="Trin 3: Anlæg IV-adgang",
        line_number=60,
        confidence=0.95,
    )


# ---------------------------------------------------------------------------
# NO UNBOUND CLAIMS TESTS
# ---------------------------------------------------------------------------


class TestNoUnboundClaims:
    """Tests when all claims are bound."""

    def test_no_issues_when_no_unbound_claims(self, sample_run_id: str) -> None:
        """Linter returns no issues when unbound_claims is empty."""
        from procedurewriter.evals.coverage import ClaimCoverageLinter
        from procedurewriter.evals.linter import LintContext

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="Sample draft text",
            unbound_claims=[],  # No unbound claims
        )

        linter = ClaimCoverageLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 0

    def test_no_issues_when_all_claims_bound(
        self, sample_run_id: str, dose_claim: Claim
    ) -> None:
        """Linter returns no issues when claims exist but none are unbound."""
        from procedurewriter.evals.coverage import ClaimCoverageLinter
        from procedurewriter.evals.linter import LintContext

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="Sample draft text",
            claims=[dose_claim],  # Claim exists in claims list
            unbound_claims=[],  # But not in unbound_claims
        )

        linter = ClaimCoverageLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 0


# ---------------------------------------------------------------------------
# SAFETY-CRITICAL UNBOUND CLAIMS (S0)
# ---------------------------------------------------------------------------


class TestSafetyCriticalUnboundClaims:
    """Tests for S0 issues from unbound safety-critical claims."""

    def test_unbound_dose_is_s0(
        self, sample_run_id: str, dose_claim: Claim
    ) -> None:
        """Unbound DOSE claims produce S0 DOSE_WITHOUT_EVIDENCE issues."""
        from procedurewriter.evals.coverage import ClaimCoverageLinter
        from procedurewriter.evals.linter import LintContext

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="Sample draft text",
            unbound_claims=[dose_claim],
        )

        linter = ClaimCoverageLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 1
        assert issues[0].code == IssueCode.DOSE_WITHOUT_EVIDENCE
        assert issues[0].severity == IssueSeverity.S0

    def test_unbound_threshold_is_s0(
        self, sample_run_id: str, threshold_claim: Claim
    ) -> None:
        """Unbound THRESHOLD claims produce S0 THRESHOLD_WITHOUT_EVIDENCE issues."""
        from procedurewriter.evals.coverage import ClaimCoverageLinter
        from procedurewriter.evals.linter import LintContext

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="Sample draft text",
            unbound_claims=[threshold_claim],
        )

        linter = ClaimCoverageLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 1
        assert issues[0].code == IssueCode.THRESHOLD_WITHOUT_EVIDENCE
        assert issues[0].severity == IssueSeverity.S0

    def test_unbound_contraindication_is_s0(
        self, sample_run_id: str, contraindication_claim: Claim
    ) -> None:
        """Unbound CONTRAINDICATION claims produce S0 CONTRAINDICATION_UNBOUND issues."""
        from procedurewriter.evals.coverage import ClaimCoverageLinter
        from procedurewriter.evals.linter import LintContext

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="Sample draft text",
            unbound_claims=[contraindication_claim],
        )

        linter = ClaimCoverageLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 1
        assert issues[0].code == IssueCode.CONTRAINDICATION_UNBOUND
        assert issues[0].severity == IssueSeverity.S0


# ---------------------------------------------------------------------------
# QUALITY-CRITICAL UNBOUND CLAIMS (S1)
# ---------------------------------------------------------------------------


class TestQualityCriticalUnboundClaims:
    """Tests for S1 issues from unbound non-safety claims."""

    def test_unbound_recommendation_is_s1(
        self, sample_run_id: str, recommendation_claim: Claim
    ) -> None:
        """Unbound RECOMMENDATION claims produce S1 CLAIM_BINDING_FAILED issues."""
        from procedurewriter.evals.coverage import ClaimCoverageLinter
        from procedurewriter.evals.linter import LintContext

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="Sample draft text",
            unbound_claims=[recommendation_claim],
        )

        linter = ClaimCoverageLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 1
        assert issues[0].code == IssueCode.CLAIM_BINDING_FAILED
        assert issues[0].severity == IssueSeverity.S1

    def test_unbound_red_flag_is_s1(
        self, sample_run_id: str, red_flag_claim: Claim
    ) -> None:
        """Unbound RED_FLAG claims produce S1 CLAIM_BINDING_FAILED issues."""
        from procedurewriter.evals.coverage import ClaimCoverageLinter
        from procedurewriter.evals.linter import LintContext

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="Sample draft text",
            unbound_claims=[red_flag_claim],
        )

        linter = ClaimCoverageLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 1
        assert issues[0].code == IssueCode.CLAIM_BINDING_FAILED
        assert issues[0].severity == IssueSeverity.S1

    def test_unbound_algorithm_step_is_s1(
        self, sample_run_id: str, algorithm_step_claim: Claim
    ) -> None:
        """Unbound ALGORITHM_STEP claims produce S1 CLAIM_BINDING_FAILED issues."""
        from procedurewriter.evals.coverage import ClaimCoverageLinter
        from procedurewriter.evals.linter import LintContext

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="Sample draft text",
            unbound_claims=[algorithm_step_claim],
        )

        linter = ClaimCoverageLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 1
        assert issues[0].code == IssueCode.CLAIM_BINDING_FAILED
        assert issues[0].severity == IssueSeverity.S1


# ---------------------------------------------------------------------------
# MULTIPLE UNBOUND CLAIMS TESTS
# ---------------------------------------------------------------------------


class TestMultipleUnboundClaims:
    """Tests for multiple unbound claims."""

    def test_multiple_unbound_claims(
        self,
        sample_run_id: str,
        dose_claim: Claim,
        threshold_claim: Claim,
        recommendation_claim: Claim,
    ) -> None:
        """Linter creates one issue per unbound claim."""
        from procedurewriter.evals.coverage import ClaimCoverageLinter
        from procedurewriter.evals.linter import LintContext

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="Sample draft text",
            unbound_claims=[dose_claim, threshold_claim, recommendation_claim],
        )

        linter = ClaimCoverageLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 3

        # Count severity levels
        s0_count = sum(1 for i in issues if i.severity == IssueSeverity.S0)
        s1_count = sum(1 for i in issues if i.severity == IssueSeverity.S1)

        # Dose and threshold are S0, recommendation is S1
        assert s0_count == 2
        assert s1_count == 1


# ---------------------------------------------------------------------------
# ISSUE CONTENT TESTS
# ---------------------------------------------------------------------------


class TestIssueContent:
    """Tests for issue message and metadata content."""

    def test_issue_includes_claim_text(
        self, sample_run_id: str, dose_claim: Claim
    ) -> None:
        """Issue message includes the unbound claim text."""
        from procedurewriter.evals.coverage import ClaimCoverageLinter
        from procedurewriter.evals.linter import LintContext

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="Sample draft text",
            unbound_claims=[dose_claim],
        )

        linter = ClaimCoverageLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 1
        assert "Amoxicillin" in issues[0].message or "50 mg" in issues[0].message

    def test_issue_includes_claim_id(
        self, sample_run_id: str, dose_claim: Claim
    ) -> None:
        """Issue claim_id field is set to the unbound claim's ID."""
        from procedurewriter.evals.coverage import ClaimCoverageLinter
        from procedurewriter.evals.linter import LintContext

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="Sample draft text",
            unbound_claims=[dose_claim],
        )

        linter = ClaimCoverageLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 1
        assert issues[0].claim_id == dose_claim.id


# ---------------------------------------------------------------------------
# LINTER METADATA TESTS
# ---------------------------------------------------------------------------


class TestLinterMetadata:
    """Tests for linter name and description."""

    def test_linter_name(self) -> None:
        """Linter has correct name."""
        from procedurewriter.evals.coverage import ClaimCoverageLinter

        linter = ClaimCoverageLinter()
        assert linter.name == "claim_coverage"

    def test_linter_description(self) -> None:
        """Linter has a description."""
        from procedurewriter.evals.coverage import ClaimCoverageLinter

        linter = ClaimCoverageLinter()
        assert len(linter.description) > 0
        assert "claim" in linter.description.lower()
