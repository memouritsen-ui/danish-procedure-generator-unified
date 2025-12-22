"""Tests for the CitationIntegrityLinter.

This linter checks that all citation references (e.g., [CIT-1]) in the
procedure draft text resolve to actual sources in the sources list.

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
    return "citation_test_run_001"


@pytest.fixture
def valid_sources() -> list[dict]:
    """Sources that exist and can be referenced."""
    return [
        {"id": "CIT-1", "title": "Danish Cardiology Guidelines 2023", "year": 2023, "tier": 1},
        {"id": "CIT-2", "title": "NICE Anaphylaxis Guidelines", "year": 2022, "tier": 4},
        {"id": "CIT-3", "title": "WHO Emergency Care Manual", "year": 2021, "tier": 4},
    ]


@pytest.fixture
def draft_with_valid_citations() -> str:
    """Draft text where all citations resolve to sources."""
    return """# Anafylaksi behandling

## Indikation
Akut allergisk reaktion med kredsløbspåvirkning [CIT-1].

## Behandling
- Adrenalin 0.5 mg i.m. [CIT-1]
- Ved bronkospasme: salbutamol inhalation [CIT-2]
- Overvåg vitale parametre [CIT-3]

## Referencer
[CIT-1] Danish Cardiology Guidelines 2023
[CIT-2] NICE Anaphylaxis Guidelines
[CIT-3] WHO Emergency Care Manual
"""


@pytest.fixture
def draft_with_orphan_citations() -> str:
    """Draft text with citations that don't resolve to sources."""
    return """# Anafylaksi behandling

## Indikation
Akut allergisk reaktion med kredsløbspåvirkning [CIT-1].

## Behandling
- Adrenalin 0.5 mg i.m. [CIT-1]
- Ved bronkospasme: salbutamol inhalation [CIT-99]
- Overvåg vitale parametre [CIT-MISSING]

## Referencer
[CIT-1] Danish Cardiology Guidelines 2023
"""


@pytest.fixture
def draft_with_no_citations() -> str:
    """Draft text with no citation references."""
    return """# Simple Procedure

## Description
This procedure has no citations at all.

## Steps
1. Do this
2. Do that
"""


@pytest.fixture
def draft_with_duplicate_citations() -> str:
    """Draft text with the same citation used multiple times."""
    return """# Procedure

## Section 1
First reference [CIT-1].

## Section 2
Second reference to same source [CIT-1].

## Section 3
Third reference [CIT-1] and another [CIT-2].
"""


# ---------------------------------------------------------------------------
# CITATION EXTRACTION TESTS
# ---------------------------------------------------------------------------


class TestCitationExtraction:
    """Tests for citation pattern recognition."""

    def test_finds_standard_citations(
        self, sample_run_id: str, draft_with_valid_citations: str, valid_sources: list[dict]
    ) -> None:
        """Linter correctly identifies [CIT-N] patterns."""
        from procedurewriter.evals.citation import CitationIntegrityLinter
        from procedurewriter.evals.linter import LintContext

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text=draft_with_valid_citations,
            sources=valid_sources,
        )

        linter = CitationIntegrityLinter()
        # All citations resolve, so no issues
        issues = linter.lint(ctx)
        assert len(issues) == 0

    def test_finds_citations_with_text_ids(self, sample_run_id: str) -> None:
        """Linter handles [CIT-ABC] style citations."""
        from procedurewriter.evals.citation import CitationIntegrityLinter
        from procedurewriter.evals.linter import LintContext

        sources = [{"id": "CIT-ABC", "title": "Source ABC"}]
        draft = "Reference to [CIT-ABC] in text."

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text=draft,
            sources=sources,
        )

        linter = CitationIntegrityLinter()
        issues = linter.lint(ctx)
        assert len(issues) == 0

    def test_no_issues_when_no_citations(
        self, sample_run_id: str, draft_with_no_citations: str
    ) -> None:
        """Linter returns no issues when draft has no citations."""
        from procedurewriter.evals.citation import CitationIntegrityLinter
        from procedurewriter.evals.linter import LintContext

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text=draft_with_no_citations,
            sources=[],
        )

        linter = CitationIntegrityLinter()
        issues = linter.lint(ctx)
        assert len(issues) == 0


# ---------------------------------------------------------------------------
# ORPHAN CITATION DETECTION TESTS
# ---------------------------------------------------------------------------


class TestOrphanCitationDetection:
    """Tests for detecting citations that don't resolve to sources."""

    def test_detects_orphan_citation(
        self, sample_run_id: str, draft_with_orphan_citations: str, valid_sources: list[dict]
    ) -> None:
        """Linter detects citations that don't exist in sources."""
        from procedurewriter.evals.citation import CitationIntegrityLinter
        from procedurewriter.evals.linter import LintContext

        # Only CIT-1 exists in sources
        sources = [{"id": "CIT-1", "title": "Valid Source"}]

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text=draft_with_orphan_citations,
            sources=sources,
        )

        linter = CitationIntegrityLinter()
        issues = linter.lint(ctx)

        # Should find CIT-99 and CIT-MISSING as orphans
        assert len(issues) == 2

    def test_orphan_citation_has_correct_issue_code(
        self, sample_run_id: str
    ) -> None:
        """Orphan citations produce S0-001 ORPHAN_CITATION issues."""
        from procedurewriter.evals.citation import CitationIntegrityLinter
        from procedurewriter.evals.linter import LintContext

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="Reference to [CIT-NONEXISTENT] here.",
            sources=[],
        )

        linter = CitationIntegrityLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 1
        assert issues[0].code == IssueCode.ORPHAN_CITATION

    def test_orphan_citation_is_s0_severity(self, sample_run_id: str) -> None:
        """Orphan citations are safety-critical (S0)."""
        from procedurewriter.evals.citation import CitationIntegrityLinter
        from procedurewriter.evals.linter import LintContext

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="Reference to [CIT-MISSING] here.",
            sources=[],
        )

        linter = CitationIntegrityLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 1
        assert issues[0].severity == IssueSeverity.S0

    def test_orphan_citation_message_includes_citation_id(
        self, sample_run_id: str
    ) -> None:
        """Issue message includes the orphan citation ID."""
        from procedurewriter.evals.citation import CitationIntegrityLinter
        from procedurewriter.evals.linter import LintContext

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="Reference to [CIT-42] here.",
            sources=[],
        )

        linter = CitationIntegrityLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 1
        assert "CIT-42" in issues[0].message

    def test_orphan_citation_includes_source_id(self, sample_run_id: str) -> None:
        """Issue source_id field is set to the orphan citation ID."""
        from procedurewriter.evals.citation import CitationIntegrityLinter
        from procedurewriter.evals.linter import LintContext

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="Reference to [CIT-ORPHAN] here.",
            sources=[],
        )

        linter = CitationIntegrityLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 1
        assert issues[0].source_id == "CIT-ORPHAN"


# ---------------------------------------------------------------------------
# DUPLICATE CITATION HANDLING TESTS
# ---------------------------------------------------------------------------


class TestDuplicateCitationHandling:
    """Tests for handling the same citation appearing multiple times."""

    def test_duplicate_valid_citations_no_issues(
        self, sample_run_id: str, draft_with_duplicate_citations: str
    ) -> None:
        """Same valid citation used multiple times produces no issues."""
        from procedurewriter.evals.citation import CitationIntegrityLinter
        from procedurewriter.evals.linter import LintContext

        sources = [
            {"id": "CIT-1", "title": "Source 1"},
            {"id": "CIT-2", "title": "Source 2"},
        ]

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text=draft_with_duplicate_citations,
            sources=sources,
        )

        linter = CitationIntegrityLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 0

    def test_duplicate_orphan_citation_single_issue(self, sample_run_id: str) -> None:
        """Same orphan citation appearing multiple times produces one issue."""
        from procedurewriter.evals.citation import CitationIntegrityLinter
        from procedurewriter.evals.linter import LintContext

        draft = """
        First [CIT-ORPHAN] reference.
        Second [CIT-ORPHAN] reference.
        Third [CIT-ORPHAN] reference.
        """

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text=draft,
            sources=[],
        )

        linter = CitationIntegrityLinter()
        issues = linter.lint(ctx)

        # Only one issue, not three
        assert len(issues) == 1
        assert issues[0].source_id == "CIT-ORPHAN"


# ---------------------------------------------------------------------------
# LINTER METADATA TESTS
# ---------------------------------------------------------------------------


class TestLinterMetadata:
    """Tests for linter name and description."""

    def test_linter_name(self) -> None:
        """Linter has correct name."""
        from procedurewriter.evals.citation import CitationIntegrityLinter

        linter = CitationIntegrityLinter()
        assert linter.name == "citation_integrity"

    def test_linter_description(self) -> None:
        """Linter has a description."""
        from procedurewriter.evals.citation import CitationIntegrityLinter

        linter = CitationIntegrityLinter()
        assert len(linter.description) > 0
        assert "citation" in linter.description.lower()


# ---------------------------------------------------------------------------
# EDGE CASES
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and unusual inputs."""

    def test_empty_draft(self, sample_run_id: str) -> None:
        """Empty draft produces no issues."""
        from procedurewriter.evals.citation import CitationIntegrityLinter
        from procedurewriter.evals.linter import LintContext

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="",
            sources=[],
        )

        linter = CitationIntegrityLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 0

    def test_citation_like_text_not_matched(self, sample_run_id: str) -> None:
        """Text that looks like citations but isn't should not match."""
        from procedurewriter.evals.citation import CitationIntegrityLinter
        from procedurewriter.evals.linter import LintContext

        # These should NOT be matched as citations
        draft = """
        [1] is a numbered list item
        [Citation needed] is a Wikipedia-style marker
        CIT-1 without brackets is not a citation
        [cit-1] lowercase might be ignored
        """

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text=draft,
            sources=[],
        )

        linter = CitationIntegrityLinter()
        issues = linter.lint(ctx)

        # No valid [CIT-X] patterns, so no orphan issues
        assert len(issues) == 0

    def test_case_sensitive_source_matching(self, sample_run_id: str) -> None:
        """Citation matching against sources is case-sensitive."""
        from procedurewriter.evals.citation import CitationIntegrityLinter
        from procedurewriter.evals.linter import LintContext

        # Source has lowercase id
        sources = [{"id": "cit-1", "title": "Source"}]
        # Draft has uppercase citation
        draft = "Reference to [CIT-1] here."

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text=draft,
            sources=sources,
        )

        linter = CitationIntegrityLinter()
        issues = linter.lint(ctx)

        # CIT-1 and cit-1 are different, so orphan
        assert len(issues) == 1

    def test_sources_with_no_id_field(self, sample_run_id: str) -> None:
        """Handles sources that don't have an 'id' field gracefully."""
        from procedurewriter.evals.citation import CitationIntegrityLinter
        from procedurewriter.evals.linter import LintContext

        # Source missing 'id' field
        sources = [{"title": "Source without ID"}]
        draft = "Reference to [CIT-1] here."

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text=draft,
            sources=sources,
        )

        linter = CitationIntegrityLinter()
        # Should not crash
        issues = linter.lint(ctx)

        # CIT-1 is orphan since source has no id
        assert len(issues) == 1
