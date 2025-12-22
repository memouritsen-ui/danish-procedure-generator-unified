"""IssueCollector - Aggregates issues from all registered linters.

The IssueCollector runs all registered linters against a LintContext
and combines the resulting issues into a single list.

It provides:
- Registration of multiple linters
- Error handling for failing linters
- Statistics tracking for each run
- Factory method for default linter configuration
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from procedurewriter.evals.linter import Linter, LintContext
from procedurewriter.models.issues import Issue, IssueCode, IssueSeverity

if TYPE_CHECKING:
    pass


class IssueCollector:
    """Collects issues from multiple linters.

    The IssueCollector runs all registered linters against a procedure
    context and aggregates their issues. It handles linter errors gracefully
    by creating error issues rather than failing the entire collection.

    Example:
        collector = IssueCollector.create_default()
        issues = collector.collect(context)

        # Check statistics
        stats = collector.last_run_stats
        print(f"Found {stats['total_issues']} issues")
    """

    def __init__(self, linters: list[Linter] | None = None) -> None:
        """Initialize the collector with optional linters.

        Args:
            linters: Optional list of linters to register. If None, no
                     linters are registered (use register() or create_default()).
        """
        self._linters: list[Linter] = linters if linters is not None else []
        self._last_run_stats: dict = {}

    def register(self, linter: Linter) -> None:
        """Register a linter to be run during collection.

        Args:
            linter: The Linter instance to register.
        """
        self._linters.append(linter)

    @property
    def linter_count(self) -> int:
        """Return the number of registered linters."""
        return len(self._linters)

    @property
    def linter_names(self) -> list[str]:
        """Return the names of all registered linters."""
        return [linter.name for linter in self._linters]

    def collect(self, context: LintContext) -> list[Issue]:
        """Run all linters and collect their issues.

        Each linter is run against the provided context. If a linter raises
        an exception, an error issue is created instead of failing the
        entire collection. This ensures all linters get a chance to run.

        Args:
            context: The LintContext containing procedure data.

        Returns:
            Combined list of issues from all linters, in linter order.
        """
        all_issues: list[Issue] = []
        linters_with_issues = 0

        for linter in self._linters:
            try:
                issues = linter.lint(context)
                all_issues.extend(issues)
                if issues:
                    linters_with_issues += 1
            except Exception as e:
                # Create an error issue for the failing linter
                error_issue = Issue(
                    run_id=context.run_id,
                    code=IssueCode.TEMPLATE_INCOMPLETE,  # Use generic code
                    severity=IssueSeverity.S1,
                    message=f"Linter '{linter.name}' failed: {str(e)}",
                )
                all_issues.append(error_issue)
                linters_with_issues += 1

        # Track statistics
        self._update_stats(all_issues, len(self._linters), linters_with_issues)

        return all_issues

    def _update_stats(
        self,
        issues: list[Issue],
        linters_run: int,
        linters_with_issues: int,
    ) -> None:
        """Update statistics from the last collection run.

        Args:
            issues: List of collected issues.
            linters_run: Number of linters that were run.
            linters_with_issues: Number of linters that found issues.
        """
        # Count by severity
        severity_counts: Counter[IssueSeverity] = Counter()
        for issue in issues:
            severity_counts[issue.severity] += 1

        # Ensure all severity levels present
        for severity in IssueSeverity:
            if severity not in severity_counts:
                severity_counts[severity] = 0

        self._last_run_stats = {
            "total_issues": len(issues),
            "linters_run": linters_run,
            "linters_with_issues": linters_with_issues,
            "by_severity": dict(severity_counts),
        }

    @property
    def last_run_stats(self) -> dict:
        """Return statistics from the last collection run.

        Returns:
            Dict containing:
            - total_issues: Total number of issues found
            - linters_run: Number of linters that were run
            - linters_with_issues: Number of linters that found issues
            - by_severity: Dict mapping IssueSeverity to count
        """
        return self._last_run_stats

    @classmethod
    def create_default(cls) -> "IssueCollector":
        """Create an IssueCollector with all standard linters.

        This factory method creates a collector with all 7 standard linters:
        - CitationIntegrityLinter
        - TemplateComplianceLinter
        - ClaimCoverageLinter
        - UnitCheckLinter
        - OverconfidenceLinter
        - ConflictDetectionLinter
        - RecencyCheckLinter

        Returns:
            IssueCollector with all standard linters registered.
        """
        from procedurewriter.evals.citation import CitationIntegrityLinter
        from procedurewriter.evals.conflict import ConflictDetectionLinter
        from procedurewriter.evals.coverage import ClaimCoverageLinter
        from procedurewriter.evals.overconfidence import OverconfidenceLinter
        from procedurewriter.evals.recency import RecencyCheckLinter
        from procedurewriter.evals.template import TemplateComplianceLinter
        from procedurewriter.evals.units import UnitCheckLinter

        return cls(
            linters=[
                CitationIntegrityLinter(),
                TemplateComplianceLinter(),
                ClaimCoverageLinter(),
                UnitCheckLinter(),
                OverconfidenceLinter(),
                ConflictDetectionLinter(),
                RecencyCheckLinter(),
            ]
        )
