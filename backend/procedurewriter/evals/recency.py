"""RecencyCheckLinter - Flags evidence sources older than 5 years.

This linter checks that all evidence sources are reasonably current.
Medical guidelines and evidence evolve, and outdated sources may not
reflect current best practices.

The 5-year threshold is standard in evidence-based medicine guidelines.
Sources older than 5 years are flagged as S1 (quality-critical) issues.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING, Any

from procedurewriter.evals.linter import Linter, LintContext
from procedurewriter.models.issues import Issue, IssueCode

if TYPE_CHECKING:
    pass


# Maximum age for sources in years
MAX_SOURCE_AGE_YEARS = 5


def _extract_year_from_source(source: dict[str, Any]) -> int | None:
    """Extract publication year from a source dict.

    Tries multiple common date fields:
    - publication_date: "YYYY-MM-DD" or "YYYY"
    - date: "YYYY-MM-DD" or "YYYY"
    - published: "YYYY-MM-DD" or "YYYY"
    - year: integer or string

    Args:
        source: Source dict with date information

    Returns:
        Publication year as integer, or None if not parseable.
    """
    # Try various date field names
    date_fields = ["publication_date", "date", "published", "year"]

    for field in date_fields:
        value = source.get(field)
        if value is None:
            continue

        # If it's already an integer (year field), return it
        if isinstance(value, int):
            return value

        # If it's a string, try to parse it
        if isinstance(value, str):
            # Try to extract 4-digit year from string
            year_match = re.search(r"(\d{4})", value)
            if year_match:
                return int(year_match.group(1))

    return None


class RecencyCheckLinter(Linter):
    """Linter that flags evidence sources older than 5 years.

    This linter:
    1. Scans all sources in the context
    2. Extracts publication year from each source
    3. Compares against the current year
    4. Creates S1 OUTDATED_GUIDELINE issues for sources >5 years old

    Outdated guidelines are S1 (quality-critical) because while old
    evidence may still be valid, it should be reviewed and potentially
    updated to reflect current best practices.
    """

    def __init__(self) -> None:
        """Initialize the linter."""
        super().__init__()

    @property
    def name(self) -> str:
        """Return the linter name."""
        return "recency_check"

    @property
    def description(self) -> str:
        """Return a description of what this linter checks."""
        return (
            f"Flags evidence sources older than {MAX_SOURCE_AGE_YEARS} years. "
            "Medical guidelines evolve and old sources may need review."
        )

    def _do_lint(self, context: LintContext) -> list[Issue]:
        """Check all sources for recency.

        Args:
            context: LintContext containing sources to check

        Returns:
            List of OUTDATED_GUIDELINE issues for old sources
        """
        issues: list[Issue] = []

        if not context.sources:
            return issues

        current_year = datetime.now().year
        threshold_year = current_year - MAX_SOURCE_AGE_YEARS

        for source in context.sources:
            pub_year = _extract_year_from_source(source)

            if pub_year is None:
                # No date information, skip this source
                continue

            if pub_year < threshold_year:
                # Source is too old
                age_years = current_year - pub_year
                source_id = source.get("id", "unknown")
                source_title = source.get("title", "Unknown source")

                issue = self.create_issue(
                    context=context,
                    code=IssueCode.OUTDATED_GUIDELINE,
                    message=(
                        f"Outdated source '{source_title}' ({source_id}): "
                        f"published in {pub_year}, now {age_years} years old. "
                        f"Sources older than {MAX_SOURCE_AGE_YEARS} years should be reviewed."
                    ),
                    source_id=source_id,
                )
                issues.append(issue)

        return issues
