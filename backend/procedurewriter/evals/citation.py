"""CitationIntegrityLinter - Checks that all citations resolve to sources.

This linter scans the procedure draft text for citation references
(e.g., [CIT-1], [CIT-42]) and verifies that each one exists in the
sources list. Orphan citations are safety-critical (S0) issues.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from procedurewriter.evals.linter import Linter, LintContext
from procedurewriter.models.issues import Issue, IssueCode

if TYPE_CHECKING:
    pass

# Regex pattern for citations: [CIT-X] where X is alphanumeric
# Matches: [CIT-1], [CIT-42], [CIT-ABC], [CIT-A1B2]
# Does NOT match: [1], [Citation needed], CIT-1, [cit-1]
CITATION_PATTERN = re.compile(r"\[CIT-([A-Z0-9]+)\]")


class CitationIntegrityLinter(Linter):
    """Linter that checks all citations resolve to actual sources.

    This linter:
    1. Finds all [CIT-X] patterns in the draft text
    2. Extracts the set of unique citation IDs
    3. Compares against source IDs from the sources list
    4. Creates S0 ORPHAN_CITATION issues for unresolved citations

    Orphan citations are safety-critical because they indicate the
    procedure references evidence that cannot be verified.
    """

    @property
    def name(self) -> str:
        """Return the linter name."""
        return "citation_integrity"

    @property
    def description(self) -> str:
        """Return a description of what this linter checks."""
        return "Verifies that all [CIT-X] citation references resolve to sources in the sources list"

    def _do_lint(self, context: LintContext) -> list[Issue]:
        """Check that all citations in the draft resolve to sources.

        Args:
            context: LintContext containing draft_text and sources

        Returns:
            List of ORPHAN_CITATION issues for unresolved citations
        """
        issues: list[Issue] = []

        # Extract all citation IDs from draft text
        citation_ids = self._extract_citations(context.draft_text)

        if not citation_ids:
            # No citations in draft, nothing to check
            return issues

        # Get set of valid source IDs
        valid_source_ids = self._extract_source_ids(context.sources)

        # Find orphan citations (in draft but not in sources)
        orphan_ids = citation_ids - valid_source_ids

        # Create issue for each orphan citation
        for orphan_id in sorted(orphan_ids):
            issue = self.create_issue(
                context=context,
                code=IssueCode.ORPHAN_CITATION,
                message=f"Citation [CIT-{orphan_id}] not found in sources",
                source_id=f"CIT-{orphan_id}",
            )
            issues.append(issue)

        return issues

    def _extract_citations(self, text: str) -> set[str]:
        """Extract unique citation IDs from text.

        Args:
            text: The draft text to scan

        Returns:
            Set of citation IDs (without the CIT- prefix and brackets)
        """
        matches = CITATION_PATTERN.findall(text)
        return set(matches)

    def _extract_source_ids(self, sources: list[dict]) -> set[str]:
        """Extract valid source IDs from sources list.

        Args:
            sources: List of source dicts, each may have an 'id' field

        Returns:
            Set of source IDs (extracted from the id field, without CIT- prefix if present)
        """
        source_ids: set[str] = set()

        for source in sources:
            source_id = source.get("id")
            if source_id:
                # If id is "CIT-1", extract "1"
                # If id is already "1", use as-is
                if source_id.startswith("CIT-"):
                    source_ids.add(source_id[4:])  # Remove "CIT-" prefix
                else:
                    # Store both with and without prefix to handle both cases
                    source_ids.add(source_id)
                    if source_id.startswith("CIT-"):
                        source_ids.add(source_id[4:])

        return source_ids
