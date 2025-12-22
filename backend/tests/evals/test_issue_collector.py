"""Tests for the IssueCollector class.

The IssueCollector runs all registered linters against a LintContext
and aggregates the resulting issues into a single list.

TDD: Write tests first, then implement the collector.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from procedurewriter.evals.linter import Linter, LintContext
from procedurewriter.models.issues import Issue, IssueCode, IssueSeverity

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_run_id() -> str:
    """Generate a sample run ID."""
    return "issue_collector_test_001"


@pytest.fixture
def sample_context(sample_run_id: str, tmp_path: Path) -> LintContext:
    """Create a minimal LintContext for testing."""
    return LintContext(
        run_id=sample_run_id,
        run_dir=tmp_path,
        procedure_title="Test Procedure",
        draft_text="Sample draft text for testing.",
    )


class MockLinterNoIssues(Linter):
    """Mock linter that returns no issues."""

    @property
    def name(self) -> str:
        return "mock_no_issues"

    def _do_lint(self, context: LintContext) -> list[Issue]:
        return []


class MockLinterOneIssue(Linter):
    """Mock linter that returns one S2 issue."""

    @property
    def name(self) -> str:
        return "mock_one_issue"

    def _do_lint(self, context: LintContext) -> list[Issue]:
        return [
            Issue(
                run_id=context.run_id,
                code=IssueCode.INFORMAL_LANGUAGE,
                severity=IssueSeverity.S2,
                message="Mock S2 issue",
            )
        ]


class MockLinterTwoIssues(Linter):
    """Mock linter that returns two issues (S0 and S1)."""

    @property
    def name(self) -> str:
        return "mock_two_issues"

    def _do_lint(self, context: LintContext) -> list[Issue]:
        return [
            Issue(
                run_id=context.run_id,
                code=IssueCode.DOSE_WITHOUT_EVIDENCE,
                severity=IssueSeverity.S0,
                message="Mock S0 issue",
            ),
            Issue(
                run_id=context.run_id,
                code=IssueCode.OUTDATED_GUIDELINE,
                severity=IssueSeverity.S1,
                message="Mock S1 issue",
            ),
        ]


class MockLinterRaises(Linter):
    """Mock linter that raises an exception."""

    @property
    def name(self) -> str:
        return "mock_raises"

    def _do_lint(self, context: LintContext) -> list[Issue]:
        raise ValueError("Mock linter failure")


# ---------------------------------------------------------------------------
# BASIC FUNCTIONALITY TESTS
# ---------------------------------------------------------------------------


class TestIssueCollectorBasic:
    """Tests for basic IssueCollector functionality."""

    def test_empty_collector_returns_no_issues(
        self, sample_context: LintContext
    ) -> None:
        """Collector with no linters returns empty list."""
        from procedurewriter.evals.collector import IssueCollector

        collector = IssueCollector(linters=[])
        issues = collector.collect(sample_context)

        assert issues == []

    def test_single_linter_no_issues(self, sample_context: LintContext) -> None:
        """Single linter that finds no issues returns empty list."""
        from procedurewriter.evals.collector import IssueCollector

        collector = IssueCollector(linters=[MockLinterNoIssues()])
        issues = collector.collect(sample_context)

        assert issues == []

    def test_single_linter_with_issues(self, sample_context: LintContext) -> None:
        """Single linter that finds issues returns them."""
        from procedurewriter.evals.collector import IssueCollector

        collector = IssueCollector(linters=[MockLinterOneIssue()])
        issues = collector.collect(sample_context)

        assert len(issues) == 1
        assert issues[0].code == IssueCode.INFORMAL_LANGUAGE

    def test_multiple_linters_aggregate(self, sample_context: LintContext) -> None:
        """Multiple linters have their issues combined."""
        from procedurewriter.evals.collector import IssueCollector

        collector = IssueCollector(
            linters=[
                MockLinterOneIssue(),
                MockLinterTwoIssues(),
            ]
        )
        issues = collector.collect(sample_context)

        assert len(issues) == 3

    def test_order_preserved(self, sample_context: LintContext) -> None:
        """Issues are returned in linter order."""
        from procedurewriter.evals.collector import IssueCollector

        collector = IssueCollector(
            linters=[
                MockLinterTwoIssues(),  # S0, S1
                MockLinterOneIssue(),   # S2
            ]
        )
        issues = collector.collect(sample_context)

        assert len(issues) == 3
        # First linter's issues come first
        assert issues[0].severity == IssueSeverity.S0
        assert issues[1].severity == IssueSeverity.S1
        assert issues[2].severity == IssueSeverity.S2


# ---------------------------------------------------------------------------
# REGISTRATION TESTS
# ---------------------------------------------------------------------------


class TestIssueCollectorRegistration:
    """Tests for linter registration."""

    def test_register_linter(self, sample_context: LintContext) -> None:
        """Can register linters after construction."""
        from procedurewriter.evals.collector import IssueCollector

        collector = IssueCollector()
        collector.register(MockLinterOneIssue())

        issues = collector.collect(sample_context)
        assert len(issues) == 1

    def test_register_multiple_linters(self, sample_context: LintContext) -> None:
        """Can register multiple linters."""
        from procedurewriter.evals.collector import IssueCollector

        collector = IssueCollector()
        collector.register(MockLinterNoIssues())
        collector.register(MockLinterOneIssue())
        collector.register(MockLinterTwoIssues())

        issues = collector.collect(sample_context)
        assert len(issues) == 3

    def test_linter_count(self) -> None:
        """Can check number of registered linters."""
        from procedurewriter.evals.collector import IssueCollector

        collector = IssueCollector()
        assert collector.linter_count == 0

        collector.register(MockLinterOneIssue())
        assert collector.linter_count == 1

        collector.register(MockLinterTwoIssues())
        assert collector.linter_count == 2

    def test_linter_names(self) -> None:
        """Can list registered linter names."""
        from procedurewriter.evals.collector import IssueCollector

        collector = IssueCollector(
            linters=[MockLinterNoIssues(), MockLinterOneIssue()]
        )

        names = collector.linter_names
        assert "mock_no_issues" in names
        assert "mock_one_issue" in names


# ---------------------------------------------------------------------------
# ERROR HANDLING TESTS
# ---------------------------------------------------------------------------


class TestIssueCollectorErrorHandling:
    """Tests for error handling in IssueCollector."""

    def test_linter_error_creates_issue(self, sample_context: LintContext) -> None:
        """When a linter raises, an error issue is created."""
        from procedurewriter.evals.collector import IssueCollector

        collector = IssueCollector(linters=[MockLinterRaises()])
        issues = collector.collect(sample_context)

        # Should create an issue for the error, not raise
        assert len(issues) == 1
        assert "mock_raises" in issues[0].message.lower()

    def test_linter_error_doesnt_block_others(
        self, sample_context: LintContext
    ) -> None:
        """One failing linter doesn't block others."""
        from procedurewriter.evals.collector import IssueCollector

        collector = IssueCollector(
            linters=[
                MockLinterOneIssue(),  # Works, 1 issue
                MockLinterRaises(),     # Fails, 1 error issue
                MockLinterTwoIssues(),  # Works, 2 issues
            ]
        )
        issues = collector.collect(sample_context)

        # 1 + 1 (error) + 2 = 4
        assert len(issues) == 4


# ---------------------------------------------------------------------------
# DEFAULT LINTERS TESTS
# ---------------------------------------------------------------------------


class TestIssueCollectorDefaults:
    """Tests for default linter configuration."""

    def test_create_default_has_all_linters(self) -> None:
        """create_default() includes all standard linters."""
        from procedurewriter.evals.collector import IssueCollector

        collector = IssueCollector.create_default()

        # Should have all 7 linters
        assert collector.linter_count >= 7

        # Check expected linters are registered
        names = collector.linter_names
        assert "citation_integrity" in names
        assert "template_compliance" in names
        assert "claim_coverage" in names
        assert "unit_check" in names
        assert "overconfidence" in names
        assert "conflict_detection" in names
        assert "recency_check" in names


# ---------------------------------------------------------------------------
# STATISTICS TESTS
# ---------------------------------------------------------------------------


class TestIssueCollectorStatistics:
    """Tests for collection statistics."""

    def test_last_run_stats(self, sample_context: LintContext) -> None:
        """Collector tracks statistics from last run."""
        from procedurewriter.evals.collector import IssueCollector

        collector = IssueCollector(
            linters=[MockLinterOneIssue(), MockLinterTwoIssues()]
        )
        issues = collector.collect(sample_context)

        stats = collector.last_run_stats

        assert stats["total_issues"] == 3
        assert stats["linters_run"] == 2
        assert stats["linters_with_issues"] == 2

    def test_last_run_stats_by_severity(self, sample_context: LintContext) -> None:
        """Stats include breakdown by severity."""
        from procedurewriter.evals.collector import IssueCollector

        collector = IssueCollector(
            linters=[MockLinterOneIssue(), MockLinterTwoIssues()]
        )
        issues = collector.collect(sample_context)

        stats = collector.last_run_stats

        assert stats["by_severity"][IssueSeverity.S0] == 1
        assert stats["by_severity"][IssueSeverity.S1] == 1
        assert stats["by_severity"][IssueSeverity.S2] == 1

    def test_stats_reset_on_new_run(self, sample_context: LintContext) -> None:
        """Stats are reset for each new collection run."""
        from procedurewriter.evals.collector import IssueCollector

        collector = IssueCollector(linters=[MockLinterTwoIssues()])

        # First run
        collector.collect(sample_context)
        assert collector.last_run_stats["total_issues"] == 2

        # Second run with different linters
        collector._linters = [MockLinterOneIssue()]
        collector.collect(sample_context)
        assert collector.last_run_stats["total_issues"] == 1
