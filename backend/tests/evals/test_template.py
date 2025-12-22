"""Tests for the TemplateComplianceLinter.

This linter checks that procedure drafts contain all 14 required sections
as defined in config/author_guide.yaml.

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
    return "template_test_run_001"


@pytest.fixture
def required_sections() -> list[str]:
    """The 14 required sections from author_guide.yaml."""
    return [
        "Formål og Målgruppe",
        "Scope og Setting",
        "Key Points",
        "Indikationer",
        "Kontraindikationer",
        "Anatomi og orientering",
        "Forudsætninger",
        "Udstyr og Forberedelse",
        "Procedure (trin-for-trin)",
        "Monitorering",
        "Komplikationer",
        "Dokumentation og Kommunikation",
        "Kvalitetstjekliste",
        "Evidens og Meta-analyse",
    ]


@pytest.fixture
def complete_draft(required_sections: list[str]) -> str:
    """Draft text with all 14 required sections."""
    sections = []
    for section in required_sections:
        sections.append(f"## {section}")
        sections.append("")
        sections.append("Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 5)
        sections.append("")
    return "\n".join(sections)


@pytest.fixture
def draft_missing_sections() -> str:
    """Draft text missing several sections."""
    return """# Pleuradræn

## Formål og Målgruppe
Denne procedure beskriver indlæggelse af pleuradræn.

## Indikationer
- Pneumothorax
- Hæmothorax

## Procedure (trin-for-trin)
1. Desinficér området
2. Anlæg lokalanæstesi
3. Indfør dræn
"""


@pytest.fixture
def draft_with_short_section() -> str:
    """Draft with a section that's too short (<100 chars)."""
    return """## Formål og Målgruppe
Denne procedure beskriver indlæggelse af pleuradræn ved akutte tilstande.
Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor.

## Scope og Setting
OK.

## Key Points
- Vigtigste punkter og kritiske handlinger som skal overholdes
- Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor

## Indikationer
- Pneumothorax
- Hæmothorax
- Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor

## Kontraindikationer
- Koagulationsforstyrrelser
- Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor

## Anatomi og orientering
5. interkostalrum i midtaksillærlinjen. Triangle of safety.
Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor.

## Forudsætninger
- Erfaring med proceduren
- Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor

## Udstyr og Forberedelse
- Pleuradræn kit
- Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor

## Procedure (trin-for-trin)
1. Desinficér
2. Anlæg
3. Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor

## Monitorering
- Overvåg vitale tegn
- Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor

## Komplikationer
- Blødning
- Infektion
- Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor

## Dokumentation og Kommunikation
- Dokumentér i journal
- Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor

## Kvalitetstjekliste
- Tjek A
- Tjek B
- Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor

## Evidens og Meta-analyse
Baseret på systematisk gennemgang af litteraturen.
Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor.
"""


# ---------------------------------------------------------------------------
# SECTION DETECTION TESTS
# ---------------------------------------------------------------------------


class TestSectionDetection:
    """Tests for detecting section headings in drafts."""

    def test_detects_all_sections_present(
        self, sample_run_id: str, complete_draft: str
    ) -> None:
        """Linter returns no issues when all sections are present."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.template import TemplateComplianceLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text=complete_draft,
            sources=[],
        )

        linter = TemplateComplianceLinter()
        issues = linter.lint(ctx)

        # All sections present with enough content
        assert len(issues) == 0

    def test_detects_missing_section(
        self, sample_run_id: str, draft_missing_sections: str
    ) -> None:
        """Linter detects sections that are completely missing."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.template import TemplateComplianceLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text=draft_missing_sections,
            sources=[],
        )

        linter = TemplateComplianceLinter()
        issues = linter.lint(ctx)

        # Should find multiple missing sections
        # Draft only has: Formål, Indikationer, Procedure
        # Missing: Scope og Setting, Key Points, Kontraindikationer, Anatomi,
        #          Forudsætninger, Udstyr, Monitorering, Komplikationer,
        #          Dokumentation, Kvalitetstjekliste, Evidens
        missing_issues = [i for i in issues if i.code == IssueCode.MISSING_MANDATORY_SECTION]
        assert len(missing_issues) == 11  # 14 - 3 = 11 missing

    def test_case_insensitive_matching(self, sample_run_id: str) -> None:
        """Section headings are matched case-insensitively."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.template import TemplateComplianceLinter

        # Use lowercase section heading
        draft = """## formål og målgruppe
Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor.
Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor.
"""

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text=draft,
            sources=[],
        )

        linter = TemplateComplianceLinter()
        issues = linter.lint(ctx)

        # "formål og målgruppe" should be recognized
        missing_issues = [i for i in issues if i.code == IssueCode.MISSING_MANDATORY_SECTION]
        section_names = [i.message for i in missing_issues]
        assert not any("Formål og Målgruppe" in name for name in section_names)

    def test_h2_and_h3_headings_detected(self, sample_run_id: str) -> None:
        """Both ## and ### style headings are detected."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.template import TemplateComplianceLinter

        draft = """### Formål og Målgruppe
Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor.
Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor.
"""

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text=draft,
            sources=[],
        )

        linter = TemplateComplianceLinter()
        issues = linter.lint(ctx)

        # "Formål og Målgruppe" should be recognized even as ###
        missing_issues = [i for i in issues if i.code == IssueCode.MISSING_MANDATORY_SECTION]
        section_names = [i.message for i in missing_issues]
        assert not any("Formål og Målgruppe" in name for name in section_names)


# ---------------------------------------------------------------------------
# MISSING SECTION ISSUE TESTS
# ---------------------------------------------------------------------------


class TestMissingSectionIssues:
    """Tests for MISSING_MANDATORY_SECTION issues."""

    def test_missing_section_has_correct_issue_code(
        self, sample_run_id: str
    ) -> None:
        """Missing sections produce S0-007 MISSING_MANDATORY_SECTION issues."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.template import TemplateComplianceLinter

        # Empty draft - all sections missing
        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="",
            sources=[],
        )

        linter = TemplateComplianceLinter()
        issues = linter.lint(ctx)

        # All 14 sections should be flagged
        assert len(issues) == 14
        assert all(i.code == IssueCode.MISSING_MANDATORY_SECTION for i in issues)

    def test_missing_section_is_s0_severity(self, sample_run_id: str) -> None:
        """Missing mandatory sections are safety-critical (S0)."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.template import TemplateComplianceLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="",
            sources=[],
        )

        linter = TemplateComplianceLinter()
        issues = linter.lint(ctx)

        assert len(issues) > 0
        assert all(i.severity == IssueSeverity.S0 for i in issues)

    def test_missing_section_message_includes_section_name(
        self, sample_run_id: str
    ) -> None:
        """Issue message includes the missing section name."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.template import TemplateComplianceLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="",
            sources=[],
        )

        linter = TemplateComplianceLinter()
        issues = linter.lint(ctx)

        messages = [i.message for i in issues]
        assert any("Formål og Målgruppe" in m for m in messages)
        assert any("Indikationer" in m for m in messages)


# ---------------------------------------------------------------------------
# SHORT SECTION TESTS
# ---------------------------------------------------------------------------


class TestShortSections:
    """Tests for TEMPLATE_INCOMPLETE issues (sections <100 chars)."""

    def test_detects_short_section(
        self, sample_run_id: str, draft_with_short_section: str
    ) -> None:
        """Linter detects sections with <100 chars content."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.template import TemplateComplianceLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text=draft_with_short_section,
            sources=[],
        )

        linter = TemplateComplianceLinter()
        issues = linter.lint(ctx)

        # "Scope og Setting" only has "OK." - too short
        incomplete_issues = [i for i in issues if i.code == IssueCode.TEMPLATE_INCOMPLETE]
        assert len(incomplete_issues) >= 1
        assert any("Scope og Setting" in i.message for i in incomplete_issues)

    def test_short_section_is_s1_severity(
        self, sample_run_id: str, draft_with_short_section: str
    ) -> None:
        """Short sections are quality-critical (S1)."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.template import TemplateComplianceLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text=draft_with_short_section,
            sources=[],
        )

        linter = TemplateComplianceLinter()
        issues = linter.lint(ctx)

        incomplete_issues = [i for i in issues if i.code == IssueCode.TEMPLATE_INCOMPLETE]
        assert len(incomplete_issues) > 0
        assert all(i.severity == IssueSeverity.S1 for i in incomplete_issues)


# ---------------------------------------------------------------------------
# LINTER METADATA TESTS
# ---------------------------------------------------------------------------


class TestLinterMetadata:
    """Tests for linter name and description."""

    def test_linter_name(self) -> None:
        """Linter has correct name."""
        from procedurewriter.evals.template import TemplateComplianceLinter

        linter = TemplateComplianceLinter()
        assert linter.name == "template_compliance"

    def test_linter_description(self) -> None:
        """Linter has a description."""
        from procedurewriter.evals.template import TemplateComplianceLinter

        linter = TemplateComplianceLinter()
        assert len(linter.description) > 0
        assert "section" in linter.description.lower()


# ---------------------------------------------------------------------------
# EDGE CASES
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and unusual inputs."""

    def test_empty_draft_all_sections_missing(self, sample_run_id: str) -> None:
        """Empty draft produces 14 missing section issues."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.template import TemplateComplianceLinter

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="",
            sources=[],
        )

        linter = TemplateComplianceLinter()
        issues = linter.lint(ctx)

        assert len(issues) == 14

    def test_section_heading_partial_match_not_detected(
        self, sample_run_id: str
    ) -> None:
        """Partial matches don't count as valid sections."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.template import TemplateComplianceLinter

        # "Formål" alone shouldn't match "Formål og Målgruppe"
        draft = """## Formål
Kort beskrivelse af formålet. Lorem ipsum dolor sit amet consectetur.
"""

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text=draft,
            sources=[],
        )

        linter = TemplateComplianceLinter()
        issues = linter.lint(ctx)

        # "Formål og Målgruppe" should still be missing
        missing_issues = [i for i in issues if i.code == IssueCode.MISSING_MANDATORY_SECTION]
        section_names = " ".join([i.message for i in missing_issues])
        assert "Formål og Målgruppe" in section_names

    def test_section_in_prose_not_as_heading_not_detected(
        self, sample_run_id: str
    ) -> None:
        """Section name appearing in prose (not as heading) doesn't count."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.template import TemplateComplianceLinter

        # Section name in text, not as heading
        draft = """# Procedure
This section covers Formål og Målgruppe as part of the introduction.
Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod.
"""

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text=draft,
            sources=[],
        )

        linter = TemplateComplianceLinter()
        issues = linter.lint(ctx)

        # All 14 sections should be missing (text isn't a heading)
        missing_issues = [i for i in issues if i.code == IssueCode.MISSING_MANDATORY_SECTION]
        assert len(missing_issues) == 14

    def test_section_with_variation_detected(self, sample_run_id: str) -> None:
        """Common variations of section names are detected."""
        from procedurewriter.evals.linter import LintContext
        from procedurewriter.evals.template import TemplateComplianceLinter

        # "Procedure" instead of "Procedure (trin-for-trin)"
        draft = """## Procedure
1. Trin 1. Lorem ipsum dolor sit amet consectetur adipiscing elit.
2. Trin 2. Lorem ipsum dolor sit amet consectetur adipiscing elit.
"""

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text=draft,
            sources=[],
        )

        linter = TemplateComplianceLinter()
        issues = linter.lint(ctx)

        # "Procedure" should match "Procedure (trin-for-trin)"
        missing_issues = [i for i in issues if i.code == IssueCode.MISSING_MANDATORY_SECTION]
        section_names = " ".join([i.message for i in missing_issues])
        assert "Procedure" not in section_names or "trin-for-trin" not in section_names


# ---------------------------------------------------------------------------
# REQUIRED SECTIONS LIST TESTS
# ---------------------------------------------------------------------------


class TestRequiredSectionsList:
    """Tests for the required sections configuration."""

    def test_has_14_required_sections(self) -> None:
        """Linter knows about all 14 required sections."""
        from procedurewriter.evals.template import REQUIRED_SECTIONS

        assert len(REQUIRED_SECTIONS) == 14

    def test_required_sections_match_author_guide(
        self, required_sections: list[str]
    ) -> None:
        """Linter's sections match author_guide.yaml."""
        from procedurewriter.evals.template import REQUIRED_SECTIONS

        # Convert both to sets for comparison
        linter_sections = set(s.lower() for s in REQUIRED_SECTIONS)
        guide_sections = set(s.lower() for s in required_sections)

        assert linter_sections == guide_sections
