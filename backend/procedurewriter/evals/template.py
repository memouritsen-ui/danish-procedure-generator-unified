"""TemplateComplianceLinter - Checks that all 14 required sections are present.

This linter verifies that procedure drafts contain all mandatory sections
as defined in config/author_guide.yaml. Missing sections are safety-critical
(S0) issues, while sections that are too short (<100 chars) are quality
issues (S1).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from procedurewriter.evals.linter import Linter, LintContext
from procedurewriter.models.issues import Issue, IssueCode

if TYPE_CHECKING:
    pass

# The 14 required sections from config/author_guide.yaml
REQUIRED_SECTIONS: list[str] = [
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

# Minimum content length for a section to be considered complete
MIN_SECTION_LENGTH = 100

# Section name variations that should match the canonical name
# Key: canonical name (lowercase), Value: list of acceptable variations
SECTION_VARIATIONS: dict[str, list[str]] = {
    "procedure (trin-for-trin)": ["procedure", "trin-for-trin", "fremgangsmåde"],
    "anatomi og orientering": ["anatomi", "anatomiske landmærker"],
    "udstyr og forberedelse": ["udstyr", "forberedelse"],
    "dokumentation og kommunikation": ["dokumentation", "kommunikation"],
    "evidens og meta-analyse": ["evidens", "meta-analyse", "metaanalyse"],
}


class TemplateComplianceLinter(Linter):
    """Linter that checks all 14 required sections are present.

    This linter:
    1. Scans for markdown headings (## or ###) in the draft
    2. Checks if each required section has a matching heading
    3. Creates S0 issues for missing sections
    4. Creates S1 issues for sections with <100 chars content
    """

    @property
    def name(self) -> str:
        """Return the linter name."""
        return "template_compliance"

    @property
    def description(self) -> str:
        """Return a description of what this linter checks."""
        return "Verifies all 14 required section headings are present and have sufficient content"

    def _do_lint(self, context: LintContext) -> list[Issue]:
        """Check that all required sections are present.

        Args:
            context: LintContext containing draft_text

        Returns:
            List of issues for missing or incomplete sections
        """
        issues: list[Issue] = []

        # Parse sections from draft
        sections = self._extract_sections(context.draft_text)

        # Check each required section
        for required in REQUIRED_SECTIONS:
            section_content = self._find_section(required, sections)

            if section_content is None:
                # Section is missing entirely
                issue = self.create_issue(
                    context=context,
                    code=IssueCode.MISSING_MANDATORY_SECTION,
                    message=f"Missing required section: {required}",
                )
                issues.append(issue)
            elif len(section_content.strip()) < MIN_SECTION_LENGTH:
                # Section exists but is too short
                issue = self.create_issue(
                    context=context,
                    code=IssueCode.TEMPLATE_INCOMPLETE,
                    message=f"Section too short (<{MIN_SECTION_LENGTH} chars): {required}",
                )
                issues.append(issue)

        return issues

    def _extract_sections(self, text: str) -> dict[str, str]:
        """Extract sections from markdown text.

        Args:
            text: The draft text (markdown format)

        Returns:
            Dict mapping lowercase section heading to section content
        """
        sections: dict[str, str] = {}

        # Pattern matches ## or ### headings
        # Captures heading text and everything until next heading or end
        heading_pattern = re.compile(
            r"^#{2,3}\s+(.+?)$",
            re.MULTILINE
        )

        matches = list(heading_pattern.finditer(text))

        for i, match in enumerate(matches):
            heading = match.group(1).strip().lower()

            # Get content between this heading and the next (or end)
            start = match.end()
            if i + 1 < len(matches):
                end = matches[i + 1].start()
            else:
                end = len(text)

            content = text[start:end].strip()
            sections[heading] = content

        return sections

    def _find_section(self, required: str, sections: dict[str, str]) -> str | None:
        """Find a required section in the extracted sections.

        Handles case-insensitive matching and common variations.

        Args:
            required: The required section name
            sections: Dict of extracted sections (lowercase keys)

        Returns:
            Section content if found, None otherwise
        """
        required_lower = required.lower()

        # Exact match (case-insensitive)
        if required_lower in sections:
            return sections[required_lower]

        # Check for variations
        variations = SECTION_VARIATIONS.get(required_lower, [])
        for variation in variations:
            if variation in sections:
                return sections[variation]

        # Check if any section starts with a variation
        for variation in [required_lower] + variations:
            for section_heading in sections:
                if section_heading.startswith(variation):
                    return sections[section_heading]

        return None
