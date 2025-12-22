"""OverconfidenceLinter - Detects overconfident/absolute language in procedures.

This linter scans procedure text for absolute terms that should be avoided
in medical documentation (e.g., "always", "never", "guaranteed", "definitely").

Medical procedures should use hedged language because:
1. Medicine is not absolute - there are always exceptions
2. Absolute language can create liability issues
3. Evidence-based medicine uses qualified language ("typically", "usually", "may")
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from procedurewriter.evals.linter import Linter, LintContext
from procedurewriter.models.issues import Issue, IssueCode

if TYPE_CHECKING:
    pass


# Overconfident terms to detect (lowercase for matching)
# Each tuple is (pattern, display_name)
OVERCONFIDENT_TERMS: list[tuple[str, str]] = [
    # English terms
    (r"\balways\b", "always"),
    (r"\bnever\b", "never"),
    (r"\bguaranteed?\b", "guaranteed"),
    (r"\bdefinitely\b", "definitely"),
    (r"\bcertainly\b", "certainly"),
    (r"\babsolutely\b", "absolutely"),
    (r"\b100%", "100%"),
    (r"\bwill cure\b", "will cure"),
    (r"\bimpossible\b", "impossible"),
    # Danish terms
    (r"\baltid\b", "altid"),
    (r"\baldrig\b", "aldrig"),
    (r"\bgaranteret\b", "garanteret"),
    (r"\bhelt sikkert\b", "helt sikkert"),
    (r"\bdefinitivt\b", "definitivt"),
    (r"\bbestemt\b", "bestemt"),
    (r"\bumiddelbart\b", "umiddelbart"),  # "immediately" - can be overconfident in context
    (r"\bvil kurere\b", "vil kurere"),
]


class OverconfidenceLinter(Linter):
    """Linter that detects overconfident/absolute language.

    This linter:
    1. Scans the draft text for absolute/overconfident terms
    2. Matches both English and Danish terms
    3. Uses word boundary matching to avoid false positives
    4. Creates S2 OVERCONFIDENT_LANGUAGE issues for each match

    Overconfident language is a warning (S2) because while it should
    be avoided, it doesn't necessarily indicate factual errors.
    """

    def __init__(self) -> None:
        """Initialize the linter with compiled regex patterns."""
        super().__init__()
        # Compile all patterns for efficiency (case-insensitive)
        self._patterns: list[tuple[re.Pattern[str], str]] = [
            (re.compile(pattern, re.IGNORECASE), name)
            for pattern, name in OVERCONFIDENT_TERMS
        ]

    @property
    def name(self) -> str:
        """Return the linter name."""
        return "overconfidence"

    @property
    def description(self) -> str:
        """Return a description of what this linter checks."""
        return (
            "Detects overconfident or absolute language that should be avoided "
            "in medical procedures (e.g., 'always', 'never', 'guaranteed')"
        )

    def _do_lint(self, context: LintContext) -> list[Issue]:
        """Scan draft text for overconfident language.

        Args:
            context: LintContext containing draft_text to check

        Returns:
            List of OVERCONFIDENT_LANGUAGE issues for each match
        """
        issues: list[Issue] = []

        if not context.draft_text:
            return issues

        # Split into lines to track line numbers
        lines = context.draft_text.split("\n")

        for line_num, line in enumerate(lines, start=1):
            # Check each pattern against this line
            for pattern, term_name in self._patterns:
                matches = pattern.finditer(line)
                for match in matches:
                    issue = self.create_issue(
                        context=context,
                        code=IssueCode.OVERCONFIDENT_LANGUAGE,
                        message=(
                            f"Overconfident language detected: '{term_name}' - "
                            f"consider using hedged language (e.g., 'typically', 'usually', 'may')"
                        ),
                        line_number=line_num,
                    )
                    issues.append(issue)

        return issues
