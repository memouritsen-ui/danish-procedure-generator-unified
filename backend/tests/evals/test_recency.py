"""Tests for the RecencyCheckLinter.

This linter flags evidence sources that are more than 5 years old.
Outdated guidelines are S1 (quality-critical) issues because medical
evidence evolves and old guidelines may not reflect current best practices.

The 5-year threshold is common in evidence-based medicine guidelines.

TDD: Write tests first, then implement the linter.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from procedurewriter.models.issues import IssueCode, IssueSeverity


# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_run_id() -> str:
    """Generate a sample run ID."""
    return "recency_test_run_001"


@pytest.fixture
def current_year() -> int:
    """Get current year for calculating thresholds."""
    return datetime.now().year


@pytest.fixture
def recent_sources(current_year: int) -> list[dict]:
    """Sources within the 5-year threshold."""
    return [
        {
            "id": "CIT-1",
            "title": "Danish Guidelines for Anaphylaxis 2023",
            "publication_date": f"{current_year - 1}-03-15",
            "url": "https://example.dk/guidelines/2023",
        },
        {
            "id": "CIT-2",
            "title": "Nordic Treatment Protocol",
            "publication_date": f"{current_year - 2}-06-01",
            "url": "https://example.no/protocol",
        },
        {
            "id": "CIT-3",
            "title": "Recent Cochrane Review",
            "publication_date": f"{current_year}-01-20",
            "url": "https://cochrane.org/reviews",
        },
    ]


@pytest.fixture
def outdated_sources(current_year: int) -> list[dict]:
    """Sources older than 5 years."""
    return [
        {
            "id": "CIT-OLD1",
            "title": "Old Treatment Guidelines",
            "publication_date": f"{current_year - 6}-03-15",
            "url": "https://example.dk/old",
        },
        {
            "id": "CIT-OLD2",
            "title": "Ancient Protocol from 2010",
            "publication_date": "2010-06-01",
            "url": "https://example.org/ancient",
        },
    ]


@pytest.fixture
def mixed_sources(current_year: int) -> list[dict]:
    """Mix of recent and outdated sources."""
    return [
        {
            "id": "CIT-NEW",
            "title": "Current Guidelines",
            "publication_date": f"{current_year - 1}-03-15",
            "url": "https://example.dk/current",
        },
        {
            "id": "CIT-OLD",
            "title": "Outdated Guidelines",
            "publication_date": f"{current_year - 7}-06-01",
            "url": "https://example.dk/old",
        },
    ]


@pytest.fixture
def sources_with_year_only(current_year: int) -> list[dict]:
    """Sources with only year specified (no month/day)."""
    return [
        {
            "id": "CIT-1",
            "title": "Recent Study",
            "year": current_year - 2,
            "url": "https://example.org/study",
        },
        {
            "id": "CIT-2",
            "title": "Old Study",
            "year": current_year - 8,
            "url": "https://example.org/old-study",
        },
    ]


@pytest.fixture
def sources_missing_dates() -> list[dict]:
    """Sources without date information."""
    return [
        {
            "id": "CIT-1",
            "title": "Guidelines without date",
            "url": "https://example.org/nodates",
        },
        {
            "id": "CIT-2",
            "title": "Another source",
            "url": "https://example.org/another",
        },
    ]


# ---------------------------------------------------------------------------
# NO ISSUES TESTS
# ---------------------------------------------------------------------------


class TestNoIssues:
    """Tests for sources that should not trigger issues."""

    def test_no_issues_for_recent_sources(
        self, sample_run_id: str, recent_sources: list[dict]
    ) -> None:
        """Sources within 5 years produce no issues."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.recency import RecencyCheckLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="",
            sources=recent_sources,
        )

        linter = RecencyCheckLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 0

    def test_no_issues_for_empty_sources(self, sample_run_id: str) -> None:
        """Empty sources list produces no issues."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.recency import RecencyCheckLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="",
            sources=[],
        )

        linter = RecencyCheckLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 0

    def test_sources_exactly_5_years_old_are_ok(
        self, sample_run_id: str, current_year: int
    ) -> None:
        """Sources exactly 5 years old are not flagged (threshold is >5 years)."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.recency import RecencyCheckLinter

        sources = [
            {
                "id": "CIT-1",
                "title": "Five Year Old Guideline",
                "publication_date": f"{current_year - 5}-01-01",
            },
        ]

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="",
            sources=sources,
        )

        linter = RecencyCheckLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 0


# ---------------------------------------------------------------------------
# OUTDATED SOURCE TESTS
# ---------------------------------------------------------------------------


class TestOutdatedSources:
    """Tests for detecting outdated sources."""

    def test_detects_outdated_source(
        self, sample_run_id: str, outdated_sources: list[dict]
    ) -> None:
        """Sources older than 5 years are flagged."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.recency import RecencyCheckLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="",
            sources=outdated_sources,
        )

        linter = RecencyCheckLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 2
        assert all(i.code == IssueCode.OUTDATED_GUIDELINE for i in issues)

    def test_outdated_is_s1_severity(
        self, sample_run_id: str, outdated_sources: list[dict]
    ) -> None:
        """Outdated guideline issues are S1 (quality-critical)."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.recency import RecencyCheckLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="",
            sources=outdated_sources,
        )

        linter = RecencyCheckLinter()
        issues = linter.lint(ctx)

        assert len(issues) >= 1
        assert all(i.severity == IssueSeverity.S1 for i in issues)

    def test_only_flags_outdated_in_mixed_list(
        self, sample_run_id: str, mixed_sources: list[dict]
    ) -> None:
        """Only outdated sources are flagged, recent sources pass."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.recency import RecencyCheckLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="",
            sources=mixed_sources,
        )

        linter = RecencyCheckLinter()
        issues = linter.lint(ctx)

        # Should only flag CIT-OLD, not CIT-NEW
        assert len(issues) == 1
        assert "CIT-OLD" in issues[0].message or issues[0].source_id == "CIT-OLD"

    def test_issue_includes_source_info(
        self, sample_run_id: str, current_year: int
    ) -> None:
        """Issue message includes source title and age."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.recency import RecencyCheckLinter

        sources = [
            {
                "id": "CIT-1",
                "title": "Very Old Guidelines",
                "publication_date": f"{current_year - 10}-01-01",
            },
        ]

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="",
            sources=sources,
        )

        linter = RecencyCheckLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 1
        msg = issues[0].message.lower()
        # Should mention the source or age
        assert "old" in msg or "year" in msg or "outdated" in msg


# ---------------------------------------------------------------------------
# DATE FORMAT TESTS
# ---------------------------------------------------------------------------


class TestDateFormats:
    """Tests for handling various date formats."""

    def test_handles_iso_date_format(
        self, sample_run_id: str, current_year: int
    ) -> None:
        """Handles ISO date format (YYYY-MM-DD)."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.recency import RecencyCheckLinter

        sources = [
            {
                "id": "CIT-1",
                "title": "Old Source",
                "publication_date": f"{current_year - 7}-06-15",
            },
        ]

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="",
            sources=sources,
        )

        linter = RecencyCheckLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 1

    def test_handles_year_field(
        self, sample_run_id: str, sources_with_year_only: list[dict]
    ) -> None:
        """Handles sources with only 'year' field (integer)."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.recency import RecencyCheckLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="",
            sources=sources_with_year_only,
        )

        linter = RecencyCheckLinter()
        issues = linter.lint(ctx)

        # Should flag the old study (8 years old), not the recent one (2 years)
        assert len(issues) == 1

    def test_handles_date_field(
        self, sample_run_id: str, current_year: int
    ) -> None:
        """Handles sources with 'date' field instead of 'publication_date'."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.recency import RecencyCheckLinter

        sources = [
            {
                "id": "CIT-1",
                "title": "Old Source",
                "date": f"{current_year - 8}-06-15",
            },
        ]

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="",
            sources=sources,
        )

        linter = RecencyCheckLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 1

    def test_handles_published_field(
        self, sample_run_id: str, current_year: int
    ) -> None:
        """Handles sources with 'published' field."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.recency import RecencyCheckLinter

        sources = [
            {
                "id": "CIT-1",
                "title": "Old Source",
                "published": f"{current_year - 9}",
            },
        ]

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="",
            sources=sources,
        )

        linter = RecencyCheckLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 1


# ---------------------------------------------------------------------------
# EDGE CASES
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and unusual inputs."""

    def test_sources_without_dates_are_skipped(
        self, sample_run_id: str, sources_missing_dates: list[dict]
    ) -> None:
        """Sources without date information are skipped (not flagged)."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.recency import RecencyCheckLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="",
            sources=sources_missing_dates,
        )

        linter = RecencyCheckLinter()
        issues = linter.lint(ctx)

        # No dates means no age check possible - don't flag
        assert len(issues) == 0

    def test_handles_invalid_date_format(self, sample_run_id: str) -> None:
        """Invalid date formats don't crash the linter."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.recency import RecencyCheckLinter

        sources = [
            {
                "id": "CIT-1",
                "title": "Source with bad date",
                "publication_date": "not-a-date",
            },
        ]

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="",
            sources=sources,
        )

        linter = RecencyCheckLinter()
        # Should not crash
        issues = linter.lint(ctx)
        assert isinstance(issues, list)

    def test_callable_interface(self, sample_run_id: str) -> None:
        """Linter can be called as a function."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.recency import RecencyCheckLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="",
            sources=[],
        )

        linter = RecencyCheckLinter()
        issues = linter(ctx)

        assert isinstance(issues, list)


# ---------------------------------------------------------------------------
# LINTER METADATA TESTS
# ---------------------------------------------------------------------------


class TestLinterMetadata:
    """Tests for linter name and description."""

    def test_linter_name(self) -> None:
        """Linter has correct name."""
        from procedurewriter.evals.recency import RecencyCheckLinter

        linter = RecencyCheckLinter()
        assert linter.name == "recency_check"

    def test_linter_description(self) -> None:
        """Linter has a description."""
        from procedurewriter.evals.recency import RecencyCheckLinter

        linter = RecencyCheckLinter()
        assert len(linter.description) > 0
        assert "5" in linter.description or "year" in linter.description.lower()

    def test_linter_tracks_issue_count(
        self, sample_run_id: str, outdated_sources: list[dict]
    ) -> None:
        """Linter tracks number of issues found."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.recency import RecencyCheckLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="",
            sources=outdated_sources,
        )

        linter = RecencyCheckLinter()
        issues = linter.lint(ctx)

        assert linter.last_run_issue_count == len(issues)
