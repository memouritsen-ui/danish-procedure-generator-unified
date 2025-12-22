"""Tests for the OverconfidenceLinter.

This linter detects overconfident/absolute language in medical procedure text
that should be avoided (e.g., "always", "never", "guaranteed", "will cure").

Medical procedures should use hedged language because:
1. Medicine is not absolute - there are always exceptions
2. Absolute language can create liability issues
3. Evidence-based medicine uses qualified language

TDD: Write tests first, then implement the linter.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from procedurewriter.models.issues import IssueCode, IssueSeverity


# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_run_id() -> str:
    """Generate a sample run ID."""
    return "overconfidence_test_run_001"


@pytest.fixture
def draft_with_no_overconfidence() -> str:
    """Draft text with appropriate hedged language."""
    return """# Anafylaksi behandling

## Indikation
Akut allergisk reaktion med kredsløbspåvirkning.

## Behandling
- Adrenalin 0.5 mg i.m. gives typisk som førstevalg
- Ved bronkospasme kan salbutamol inhalation overvejes
- Patienten bør overvåges i mindst 4 timer
- De fleste patienter responderer godt på behandlingen

## Prognose
I de fleste tilfælde er prognosen god ved hurtig behandling.
"""


@pytest.fixture
def draft_with_english_overconfidence() -> str:
    """Draft text with overconfident English terms."""
    return """# Treatment Guide

## Overview
This treatment will always work for all patients.

## Dosing
The medication is guaranteed to cure the condition.
You will never see side effects with proper dosing.

## Outcomes
Patients will definitely recover within 24 hours.
This is 100% effective in all cases.
"""


@pytest.fixture
def draft_with_danish_overconfidence() -> str:
    """Draft text with overconfident Danish terms."""
    return """# Behandlingsvejledning

## Oversigt
Denne behandling virker altid hos alle patienter.

## Dosering
Medicinen vil garanteret kurere tilstanden.
Man vil aldrig se bivirkninger ved korrekt dosering.

## Resultater
Patienten vil helt sikkert blive rask inden for 24 timer.
"""


@pytest.fixture
def draft_with_mixed_overconfidence() -> str:
    """Draft text with mix of valid and overconfident language."""
    return """# Procedure

## Section 1
This approach is typically effective for most patients.

## Section 2
However, this treatment will always prevent complications.

## Section 3
Patients usually respond well to the medication.
"""


# ---------------------------------------------------------------------------
# NO OVERCONFIDENCE TESTS
# ---------------------------------------------------------------------------


class TestNoOverconfidence:
    """Tests for text without overconfident language."""

    def test_no_issues_for_hedged_language(
        self, sample_run_id: str, draft_with_no_overconfidence: str
    ) -> None:
        """Text with hedged language produces no issues."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.overconfidence import OverconfidenceLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text=draft_with_no_overconfidence,
        )

        linter = OverconfidenceLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 0

    def test_no_issues_for_empty_draft(self, sample_run_id: str) -> None:
        """Empty draft produces no issues."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.overconfidence import OverconfidenceLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="",
        )

        linter = OverconfidenceLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 0


# ---------------------------------------------------------------------------
# ENGLISH OVERCONFIDENCE TESTS
# ---------------------------------------------------------------------------


class TestEnglishOverconfidence:
    """Tests for detecting overconfident English terms."""

    def test_detects_always(self, sample_run_id: str) -> None:
        """Detects 'always' as overconfident."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.overconfidence import OverconfidenceLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="This treatment will always work.",
        )

        linter = OverconfidenceLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 1
        assert "always" in issues[0].message.lower()

    def test_detects_never(self, sample_run_id: str) -> None:
        """Detects 'never' as overconfident."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.overconfidence import OverconfidenceLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="Side effects will never occur.",
        )

        linter = OverconfidenceLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 1
        assert "never" in issues[0].message.lower()

    def test_detects_guaranteed(self, sample_run_id: str) -> None:
        """Detects 'guaranteed' as overconfident."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.overconfidence import OverconfidenceLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="Recovery is guaranteed with this treatment.",
        )

        linter = OverconfidenceLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 1
        assert "guaranteed" in issues[0].message.lower()

    def test_detects_definitely(self, sample_run_id: str) -> None:
        """Detects 'definitely' as overconfident."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.overconfidence import OverconfidenceLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="The patient will definitely improve.",
        )

        linter = OverconfidenceLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 1
        assert "definitely" in issues[0].message.lower()

    def test_detects_100_percent(self, sample_run_id: str) -> None:
        """Detects '100%' as overconfident."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.overconfidence import OverconfidenceLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="This treatment is 100% effective.",
        )

        linter = OverconfidenceLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 1
        assert "100%" in issues[0].message

    def test_detects_multiple_issues(
        self, sample_run_id: str, draft_with_english_overconfidence: str
    ) -> None:
        """Detects multiple overconfident terms in same text."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.overconfidence import OverconfidenceLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text=draft_with_english_overconfidence,
        )

        linter = OverconfidenceLinter()
        issues = linter.lint(ctx)

        # Should find: always, guaranteed, never, definitely, 100%
        assert len(issues) >= 5


# ---------------------------------------------------------------------------
# DANISH OVERCONFIDENCE TESTS
# ---------------------------------------------------------------------------


class TestDanishOverconfidence:
    """Tests for detecting overconfident Danish terms."""

    def test_detects_altid(self, sample_run_id: str) -> None:
        """Detects 'altid' (always) as overconfident."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.overconfidence import OverconfidenceLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="Denne behandling virker altid.",
        )

        linter = OverconfidenceLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 1
        assert "altid" in issues[0].message.lower()

    def test_detects_aldrig(self, sample_run_id: str) -> None:
        """Detects 'aldrig' (never) as overconfident."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.overconfidence import OverconfidenceLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="Bivirkninger forekommer aldrig.",
        )

        linter = OverconfidenceLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 1
        assert "aldrig" in issues[0].message.lower()

    def test_detects_garanteret(self, sample_run_id: str) -> None:
        """Detects 'garanteret' (guaranteed) as overconfident."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.overconfidence import OverconfidenceLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="Helbredelse er garanteret.",
        )

        linter = OverconfidenceLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 1
        assert "garanteret" in issues[0].message.lower()

    def test_detects_helt_sikkert(self, sample_run_id: str) -> None:
        """Detects 'helt sikkert' (definitely) as overconfident."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.overconfidence import OverconfidenceLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="Patienten vil helt sikkert blive rask.",
        )

        linter = OverconfidenceLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 1
        assert "helt sikkert" in issues[0].message.lower()


# ---------------------------------------------------------------------------
# ISSUE METADATA TESTS
# ---------------------------------------------------------------------------


class TestIssueMetadata:
    """Tests for issue properties (severity, code, line number)."""

    def test_issue_has_correct_code(self, sample_run_id: str) -> None:
        """Issues have OVERCONFIDENT_LANGUAGE code."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.overconfidence import OverconfidenceLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="This always works.",
        )

        linter = OverconfidenceLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 1
        assert issues[0].code == IssueCode.OVERCONFIDENT_LANGUAGE

    def test_issue_has_s2_severity(self, sample_run_id: str) -> None:
        """Issues are warnings (S2 severity)."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.overconfidence import OverconfidenceLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="This always works.",
        )

        linter = OverconfidenceLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 1
        assert issues[0].severity == IssueSeverity.S2

    def test_issue_includes_line_number(self, sample_run_id: str) -> None:
        """Issues include the line number where term was found."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.overconfidence import OverconfidenceLinter

        draft = """Line 1 is normal.
Line 2 is normal.
Line 3 always has problems.
Line 4 is normal."""

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text=draft,
        )

        linter = OverconfidenceLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 1
        assert issues[0].line_number == 3


# ---------------------------------------------------------------------------
# LINTER METADATA TESTS
# ---------------------------------------------------------------------------


class TestLinterMetadata:
    """Tests for linter name and description."""

    def test_linter_name(self) -> None:
        """Linter has correct name."""
        from procedurewriter.evals.overconfidence import OverconfidenceLinter

        linter = OverconfidenceLinter()
        assert linter.name == "overconfidence"

    def test_linter_description(self) -> None:
        """Linter has a description."""
        from procedurewriter.evals.overconfidence import OverconfidenceLinter

        linter = OverconfidenceLinter()
        assert len(linter.description) > 0
        assert "overconfident" in linter.description.lower() or "absolute" in linter.description.lower()


# ---------------------------------------------------------------------------
# EDGE CASES
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and unusual inputs."""

    def test_case_insensitive_detection(self, sample_run_id: str) -> None:
        """Detection is case-insensitive."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.overconfidence import OverconfidenceLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="This ALWAYS works. This NEVER fails.",
        )

        linter = OverconfidenceLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 2

    def test_word_boundary_matching(self, sample_run_id: str) -> None:
        """Only matches whole words, not substrings."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.overconfidence import OverconfidenceLinter

        # "Guarantee" within a word should not match "guaranteed"
        # "forever" should not match "never"
        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="This is a guaranteeing approach. Forever young.",
        )

        linter = OverconfidenceLinter()
        issues = linter.lint(ctx)

        # Should not find any overconfident terms
        assert len(issues) == 0

    def test_mixed_valid_invalid_text(
        self, sample_run_id: str, draft_with_mixed_overconfidence: str
    ) -> None:
        """Only flags overconfident sections, not valid text."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.overconfidence import OverconfidenceLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text=draft_with_mixed_overconfidence,
        )

        linter = OverconfidenceLinter()
        issues = linter.lint(ctx)

        # Should only find "always" in Section 2
        assert len(issues) == 1
        assert "always" in issues[0].message.lower()

    def test_same_term_multiple_lines_multiple_issues(self, sample_run_id: str) -> None:
        """Same term on different lines produces separate issues."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.overconfidence import OverconfidenceLinter

        draft = """Line 1: This always works.
Line 2: Normal text.
Line 3: This also always works."""

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text=draft,
        )

        linter = OverconfidenceLinter()
        issues = linter.lint(ctx)

        # Should find "always" twice on different lines
        assert len(issues) == 2
        line_numbers = [i.line_number for i in issues]
        assert 1 in line_numbers
        assert 3 in line_numbers
