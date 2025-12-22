"""Tests for the UnitCheckLinter.

This linter checks that all units in claims are valid SI units
as defined in the UnitNormalizer.UNIT_MAP.

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
    return "unit_check_test_run_001"


@pytest.fixture
def claim_with_valid_unit(sample_run_id: str) -> Claim:
    """A claim with a recognized SI unit."""
    return Claim(
        id=uuid4(),
        run_id=sample_run_id,
        claim_type=ClaimType.DOSE,
        text="Adrenalin 0.5 mg i.m.",
        normalized_value="0.5",
        unit="mg",
        source_refs=["SRC001"],
        line_number=10,
        confidence=0.9,
    )


@pytest.fixture
def claim_with_compound_unit(sample_run_id: str) -> Claim:
    """A claim with a compound SI unit."""
    return Claim(
        id=uuid4(),
        run_id=sample_run_id,
        claim_type=ClaimType.DOSE,
        text="Amoxicillin 50 mg/kg/d",
        normalized_value="50",
        unit="mg/kg/d",
        source_refs=["SRC002"],
        line_number=15,
        confidence=0.85,
    )


@pytest.fixture
def claim_with_invalid_unit(sample_run_id: str) -> Claim:
    """A claim with an unrecognized unit."""
    return Claim(
        id=uuid4(),
        run_id=sample_run_id,
        claim_type=ClaimType.DOSE,
        text="Some medication 10 flobbles",
        normalized_value="10",
        unit="flobbles",  # Not a valid unit
        source_refs=["SRC003"],
        line_number=20,
        confidence=0.7,
    )


@pytest.fixture
def claim_with_no_unit(sample_run_id: str) -> Claim:
    """A claim without a unit (e.g., a recommendation)."""
    return Claim(
        id=uuid4(),
        run_id=sample_run_id,
        claim_type=ClaimType.RECOMMENDATION,
        text="Patienten bør indlægges",
        normalized_value=None,
        unit=None,
        source_refs=["SRC004"],
        line_number=25,
        confidence=0.95,
    )


@pytest.fixture
def claim_with_threshold(sample_run_id: str) -> Claim:
    """A threshold claim with a percentage unit."""
    return Claim(
        id=uuid4(),
        run_id=sample_run_id,
        claim_type=ClaimType.THRESHOLD,
        text="SpO2 < 92%",
        normalized_value="92",
        unit="%",
        source_refs=["SRC005"],
        line_number=30,
        confidence=0.88,
    )


@pytest.fixture
def claim_with_danish_unit(sample_run_id: str) -> Claim:
    """A claim with a Danish unit abbreviation (should be valid)."""
    return Claim(
        id=uuid4(),
        run_id=sample_run_id,
        claim_type=ClaimType.DOSE,
        text="Insulin 10 IE subkutant",
        normalized_value="10",
        unit="IE",  # Danish for IU
        source_refs=["SRC006"],
        line_number=35,
        confidence=0.9,
    )


@pytest.fixture
def claim_with_partial_invalid_compound(sample_run_id: str) -> Claim:
    """A compound unit where one part is invalid."""
    return Claim(
        id=uuid4(),
        run_id=sample_run_id,
        claim_type=ClaimType.DOSE,
        text="Medication 5 mg/flurb/h",
        normalized_value="5",
        unit="mg/flurb/h",  # 'flurb' is not valid
        source_refs=["SRC007"],
        line_number=40,
        confidence=0.75,
    )


# ---------------------------------------------------------------------------
# VALID UNIT TESTS
# ---------------------------------------------------------------------------


class TestValidUnits:
    """Tests for claims with valid SI units."""

    def test_no_issues_for_valid_simple_unit(
        self, sample_run_id: str, claim_with_valid_unit: Claim
    ) -> None:
        """Claim with valid simple unit (mg) produces no issues."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.units import UnitCheckLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="Test procedure",
            claims=[claim_with_valid_unit],
        )

        linter = UnitCheckLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 0

    def test_no_issues_for_valid_compound_unit(
        self, sample_run_id: str, claim_with_compound_unit: Claim
    ) -> None:
        """Claim with valid compound unit (mg/kg/d) produces no issues."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.units import UnitCheckLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="Test procedure",
            claims=[claim_with_compound_unit],
        )

        linter = UnitCheckLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 0

    def test_no_issues_for_percentage_unit(
        self, sample_run_id: str, claim_with_threshold: Claim
    ) -> None:
        """Claim with percentage unit produces no issues."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.units import UnitCheckLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="Test procedure",
            claims=[claim_with_threshold],
        )

        linter = UnitCheckLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 0

    def test_no_issues_for_danish_unit(
        self, sample_run_id: str, claim_with_danish_unit: Claim
    ) -> None:
        """Claim with Danish unit abbreviation (IE) produces no issues."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.units import UnitCheckLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="Test procedure",
            claims=[claim_with_danish_unit],
        )

        linter = UnitCheckLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 0


# ---------------------------------------------------------------------------
# INVALID UNIT TESTS
# ---------------------------------------------------------------------------


class TestInvalidUnits:
    """Tests for claims with invalid/unrecognized units."""

    def test_detects_invalid_unit(
        self, sample_run_id: str, claim_with_invalid_unit: Claim
    ) -> None:
        """Claim with unrecognized unit produces UNIT_MISMATCH issue."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.units import UnitCheckLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="Test procedure",
            claims=[claim_with_invalid_unit],
        )

        linter = UnitCheckLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 1
        assert issues[0].code == IssueCode.UNIT_MISMATCH

    def test_invalid_unit_is_s1_severity(
        self, sample_run_id: str, claim_with_invalid_unit: Claim
    ) -> None:
        """Invalid unit issues are quality-critical (S1)."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.units import UnitCheckLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="Test procedure",
            claims=[claim_with_invalid_unit],
        )

        linter = UnitCheckLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 1
        assert issues[0].severity == IssueSeverity.S1

    def test_invalid_unit_message_includes_unit(
        self, sample_run_id: str, claim_with_invalid_unit: Claim
    ) -> None:
        """Issue message includes the invalid unit."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.units import UnitCheckLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="Test procedure",
            claims=[claim_with_invalid_unit],
        )

        linter = UnitCheckLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 1
        assert "flobbles" in issues[0].message

    def test_invalid_unit_includes_claim_id(
        self, sample_run_id: str, claim_with_invalid_unit: Claim
    ) -> None:
        """Issue includes the claim_id field."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.units import UnitCheckLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="Test procedure",
            claims=[claim_with_invalid_unit],
        )

        linter = UnitCheckLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 1
        assert issues[0].claim_id == claim_with_invalid_unit.id

    def test_invalid_unit_includes_line_number(
        self, sample_run_id: str, claim_with_invalid_unit: Claim
    ) -> None:
        """Issue includes line number from the claim."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.units import UnitCheckLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="Test procedure",
            claims=[claim_with_invalid_unit],
        )

        linter = UnitCheckLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 1
        assert issues[0].line_number == 20  # From fixture


# ---------------------------------------------------------------------------
# COMPOUND UNIT TESTS
# ---------------------------------------------------------------------------


class TestCompoundUnits:
    """Tests for compound units with mixed valid/invalid parts."""

    def test_detects_partial_invalid_compound_unit(
        self, sample_run_id: str, claim_with_partial_invalid_compound: Claim
    ) -> None:
        """Compound unit with one invalid part produces issue."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.units import UnitCheckLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="Test procedure",
            claims=[claim_with_partial_invalid_compound],
        )

        linter = UnitCheckLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 1
        assert "flurb" in issues[0].message.lower()


# ---------------------------------------------------------------------------
# NO UNIT TESTS
# ---------------------------------------------------------------------------


class TestNoUnit:
    """Tests for claims without units."""

    def test_no_issues_when_claim_has_no_unit(
        self, sample_run_id: str, claim_with_no_unit: Claim
    ) -> None:
        """Claim with no unit (None) produces no issues."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.units import UnitCheckLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="Test procedure",
            claims=[claim_with_no_unit],
        )

        linter = UnitCheckLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 0

    def test_no_issues_when_no_claims(self, sample_run_id: str) -> None:
        """Empty claims list produces no issues."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.units import UnitCheckLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="Test procedure",
            claims=[],
        )

        linter = UnitCheckLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 0


# ---------------------------------------------------------------------------
# MULTIPLE CLAIMS TESTS
# ---------------------------------------------------------------------------


class TestMultipleClaims:
    """Tests for multiple claims with different units."""

    def test_detects_all_invalid_units(self, sample_run_id: str) -> None:
        """Multiple claims with invalid units produce multiple issues."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.units import UnitCheckLinter

        claims = [
            Claim(
                id=uuid4(),
                run_id=sample_run_id,
                claim_type=ClaimType.DOSE,
                text="Med A 10 foo",
                normalized_value="10",
                unit="foo",
                line_number=10,
                confidence=0.8,
            ),
            Claim(
                id=uuid4(),
                run_id=sample_run_id,
                claim_type=ClaimType.DOSE,
                text="Med B 20 bar",
                normalized_value="20",
                unit="bar",
                line_number=20,
                confidence=0.8,
            ),
        ]

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="Test procedure",
            claims=claims,
        )

        linter = UnitCheckLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 2

    def test_only_invalid_units_produce_issues(self, sample_run_id: str) -> None:
        """Mix of valid and invalid units only produces issues for invalid."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.units import UnitCheckLinter

        claims = [
            Claim(
                id=uuid4(),
                run_id=sample_run_id,
                claim_type=ClaimType.DOSE,
                text="Valid med 10 mg",
                normalized_value="10",
                unit="mg",  # Valid
                line_number=10,
                confidence=0.8,
            ),
            Claim(
                id=uuid4(),
                run_id=sample_run_id,
                claim_type=ClaimType.DOSE,
                text="Invalid med 20 xyz",
                normalized_value="20",
                unit="xyz",  # Invalid
                line_number=20,
                confidence=0.8,
            ),
            Claim(
                id=uuid4(),
                run_id=sample_run_id,
                claim_type=ClaimType.THRESHOLD,
                text="SpO2 < 92%",
                normalized_value="92",
                unit="%",  # Valid
                line_number=30,
                confidence=0.85,
            ),
        ]

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="Test procedure",
            claims=claims,
        )

        linter = UnitCheckLinter()
        issues = linter.lint(ctx)

        # Only one invalid unit (xyz)
        assert len(issues) == 1
        assert "xyz" in issues[0].message


# ---------------------------------------------------------------------------
# LINTER METADATA TESTS
# ---------------------------------------------------------------------------


class TestLinterMetadata:
    """Tests for linter name and description."""

    def test_linter_name(self) -> None:
        """Linter has correct name."""
        from procedurewriter.evals.units import UnitCheckLinter

        linter = UnitCheckLinter()
        assert linter.name == "unit_check"

    def test_linter_description(self) -> None:
        """Linter has a description."""
        from procedurewriter.evals.units import UnitCheckLinter

        linter = UnitCheckLinter()
        assert len(linter.description) > 0
        assert "unit" in linter.description.lower()


# ---------------------------------------------------------------------------
# EDGE CASES
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and unusual inputs."""

    def test_empty_unit_string_no_issue(self, sample_run_id: str) -> None:
        """Empty string unit (vs None) is handled gracefully."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.units import UnitCheckLinter

        claim = Claim(
            id=uuid4(),
            run_id=sample_run_id,
            claim_type=ClaimType.DOSE,
            text="Medication with empty unit",
            normalized_value="10",
            unit="",  # Empty string, not None
            line_number=10,
            confidence=0.8,
        )

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="Test procedure",
            claims=[claim],
        )

        linter = UnitCheckLinter()
        # Should not crash, treat empty as "no unit"
        issues = linter.lint(ctx)

        assert len(issues) == 0

    def test_case_insensitive_unit_validation(self, sample_run_id: str) -> None:
        """Unit validation is case-insensitive for known units."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.units import UnitCheckLinter

        claims = [
            Claim(
                id=uuid4(),
                run_id=sample_run_id,
                claim_type=ClaimType.DOSE,
                text="Med 10 MG",
                normalized_value="10",
                unit="MG",  # Uppercase, but should be recognized
                line_number=10,
                confidence=0.8,
            ),
            Claim(
                id=uuid4(),
                run_id=sample_run_id,
                claim_type=ClaimType.DOSE,
                text="Med 10 Mg",
                normalized_value="10",
                unit="Mg",  # Mixed case
                line_number=15,
                confidence=0.8,
            ),
        ]

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="Test procedure",
            claims=claims,
        )

        linter = UnitCheckLinter()
        issues = linter.lint(ctx)

        # Both should be valid (case-insensitive)
        assert len(issues) == 0

    def test_microgram_variations_all_valid(self, sample_run_id: str) -> None:
        """All microgram variations (mcg, ug, μg) are valid."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.units import UnitCheckLinter

        claims = [
            Claim(
                id=uuid4(),
                run_id=sample_run_id,
                claim_type=ClaimType.DOSE,
                text="Med 100 mcg",
                normalized_value="100",
                unit="mcg",
                line_number=10,
                confidence=0.8,
            ),
            Claim(
                id=uuid4(),
                run_id=sample_run_id,
                claim_type=ClaimType.DOSE,
                text="Med 100 ug",
                normalized_value="100",
                unit="ug",
                line_number=15,
                confidence=0.8,
            ),
            Claim(
                id=uuid4(),
                run_id=sample_run_id,
                claim_type=ClaimType.DOSE,
                text="Med 100 μg",
                normalized_value="100",
                unit="μg",
                line_number=20,
                confidence=0.8,
            ),
        ]

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="Test procedure",
            claims=claims,
        )

        linter = UnitCheckLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 0
