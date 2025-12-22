"""Tests for the Linter base class.

TDD: Write tests first, then implement the Linter base class.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from procedurewriter.models.claims import Claim, ClaimType
from procedurewriter.models.evidence import BindingType, ClaimEvidenceLink, EvidenceChunk
from procedurewriter.models.issues import Issue, IssueCode, IssueSeverity

if TYPE_CHECKING:
    from procedurewriter.evals.linter import Linter, LintContext


# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_run_id() -> str:
    """Generate a sample run ID."""
    return "abc123def456"


@pytest.fixture
def sample_claims(sample_run_id: str) -> list[Claim]:
    """Generate sample claims for testing."""
    return [
        Claim(
            run_id=sample_run_id,
            claim_type=ClaimType.DOSE,
            text="Adrenalin 0.5 mg i.m.",
            line_number=10,
            confidence=0.95,
        ),
        Claim(
            run_id=sample_run_id,
            claim_type=ClaimType.THRESHOLD,
            text="SpO2 < 94%",
            line_number=15,
            confidence=0.90,
        ),
    ]


@pytest.fixture
def sample_chunks(sample_run_id: str) -> list[EvidenceChunk]:
    """Generate sample evidence chunks for testing."""
    return [
        EvidenceChunk(
            run_id=sample_run_id,
            source_id="src_001",
            text="Adrenalin 0.5 mg gives i.m. ved anafylaksi",
            chunk_index=0,
        ),
    ]


@pytest.fixture
def sample_links(sample_claims: list[Claim], sample_chunks: list[EvidenceChunk]) -> list[ClaimEvidenceLink]:
    """Generate sample claim-evidence links for testing."""
    return [
        ClaimEvidenceLink(
            claim_id=sample_claims[0].id,
            evidence_chunk_id=sample_chunks[0].id,
            binding_type=BindingType.KEYWORD,
            binding_score=0.95,
        ),
    ]


@pytest.fixture
def sample_draft_text() -> str:
    """Sample procedure draft text."""
    return """# Anafylaksi behandling

## Indikation
Akut allergisk reaktion med kredsløbspåvirkning.

## Behandling
- Adrenalin 0.5 mg i.m. [CIT-1]
- Overvåg SpO2 < 94% [CIT-2]

## Referencer
[CIT-1] Dansk Cardiologisk Selskab 2023
[CIT-2] Akut ABC 2022
"""


@pytest.fixture
def sample_sources() -> list[dict]:
    """Sample source metadata."""
    return [
        {"id": "CIT-1", "title": "Anafylaksi guideline", "year": 2023, "tier": 1},
        {"id": "CIT-2", "title": "Akut ABC", "year": 2022, "tier": 2},
    ]


@pytest.fixture
def lint_context(
    sample_run_id: str,
    sample_claims: list[Claim],
    sample_chunks: list[EvidenceChunk],
    sample_links: list[ClaimEvidenceLink],
    sample_draft_text: str,
    sample_sources: list[dict],
) -> "LintContext":
    """Create a LintContext for testing."""
    from procedurewriter.evals.linter import LintContext

    return LintContext(
        run_id=sample_run_id,
        run_dir=Path("/tmp/test_run"),
        procedure_title="Anafylaksi behandling",
        draft_text=sample_draft_text,
        claims=sample_claims,
        chunks=sample_chunks,
        links=sample_links,
        unbound_claims=[sample_claims[1]],  # Second claim is unbound
        sources=sample_sources,
    )


# ---------------------------------------------------------------------------
# LINT CONTEXT TESTS
# ---------------------------------------------------------------------------


class TestLintContext:
    """Tests for the LintContext dataclass."""

    def test_lint_context_creation(self, lint_context: "LintContext") -> None:
        """LintContext can be created with all required fields."""
        assert lint_context.run_id == "abc123def456"
        assert lint_context.procedure_title == "Anafylaksi behandling"
        assert len(lint_context.claims) == 2
        assert len(lint_context.chunks) == 1
        assert len(lint_context.links) == 1
        assert len(lint_context.unbound_claims) == 1

    def test_lint_context_has_draft_text(self, lint_context: "LintContext") -> None:
        """LintContext contains the procedure draft text."""
        assert "Anafylaksi behandling" in lint_context.draft_text
        assert "[CIT-1]" in lint_context.draft_text

    def test_lint_context_has_sources(self, lint_context: "LintContext") -> None:
        """LintContext contains source metadata."""
        assert len(lint_context.sources) == 2
        assert lint_context.sources[0]["id"] == "CIT-1"

    def test_lint_context_has_run_dir(self, lint_context: "LintContext") -> None:
        """LintContext contains run directory path."""
        assert lint_context.run_dir == Path("/tmp/test_run")

    def test_lint_context_optional_fields_default_to_empty(
        self, sample_run_id: str
    ) -> None:
        """LintContext optional fields default to empty lists."""
        from procedurewriter.evals.linter import LintContext

        ctx = LintContext(
            run_id=sample_run_id,
            run_dir=Path("/tmp"),
            procedure_title="Test",
            draft_text="",
        )
        assert ctx.claims == []
        assert ctx.chunks == []
        assert ctx.links == []
        assert ctx.unbound_claims == []
        assert ctx.sources == []


# ---------------------------------------------------------------------------
# LINTER BASE CLASS TESTS
# ---------------------------------------------------------------------------


class TestLinterBaseClass:
    """Tests for the abstract Linter base class."""

    def test_linter_is_abstract(self) -> None:
        """Linter cannot be instantiated directly."""
        from procedurewriter.evals.linter import Linter

        with pytest.raises(TypeError, match="abstract"):
            Linter()  # type: ignore[abstract]

    def test_concrete_linter_must_implement_name(self) -> None:
        """Concrete linter must implement name property."""
        from procedurewriter.evals.linter import Linter, LintContext

        class BadLinter(Linter):
            # Missing name property
            def _do_lint(self, context: LintContext) -> list[Issue]:
                return []

        with pytest.raises(TypeError, match="abstract"):
            BadLinter()

    def test_concrete_linter_must_implement_lint(self) -> None:
        """Concrete linter must implement _do_lint method."""
        from procedurewriter.evals.linter import Linter, LintContext

        class BadLinter(Linter):
            @property
            def name(self) -> str:
                return "bad"

            # Missing _do_lint method

        with pytest.raises(TypeError, match="abstract"):
            BadLinter()

    def test_concrete_linter_can_be_created(self) -> None:
        """Concrete linter with all methods can be instantiated."""
        from procedurewriter.evals.linter import Linter, LintContext

        class GoodLinter(Linter):
            @property
            def name(self) -> str:
                return "good_linter"

            def _do_lint(self, context: LintContext) -> list[Issue]:
                return []

        linter = GoodLinter()
        assert linter.name == "good_linter"

    def test_linter_lint_returns_issues(
        self, lint_context: "LintContext"
    ) -> None:
        """Linter.lint() returns a list of Issue objects."""
        from procedurewriter.evals.linter import Linter, LintContext

        class IssueCreatingLinter(Linter):
            @property
            def name(self) -> str:
                return "issue_creator"

            def _do_lint(self, context: LintContext) -> list[Issue]:
                return [
                    Issue(
                        run_id=context.run_id,
                        code=IssueCode.DOSE_WITHOUT_EVIDENCE,
                        severity=IssueSeverity.S0,
                        message="Test issue",
                    )
                ]

        linter = IssueCreatingLinter()
        issues = linter.lint(lint_context)

        assert len(issues) == 1
        assert issues[0].code == IssueCode.DOSE_WITHOUT_EVIDENCE
        assert issues[0].severity == IssueSeverity.S0

    def test_linter_lint_receives_context(
        self, lint_context: "LintContext"
    ) -> None:
        """Linter.lint() receives the full LintContext."""
        from procedurewriter.evals.linter import Linter, LintContext

        received_context: list[LintContext] = []

        class ContextCapturingLinter(Linter):
            @property
            def name(self) -> str:
                return "context_capturer"

            def _do_lint(self, context: LintContext) -> list[Issue]:
                received_context.append(context)
                return []

        linter = ContextCapturingLinter()
        linter.lint(lint_context)

        assert len(received_context) == 1
        assert received_context[0].run_id == lint_context.run_id
        assert received_context[0].claims == lint_context.claims


# ---------------------------------------------------------------------------
# LINTER SEVERITY HELPER TESTS
# ---------------------------------------------------------------------------


class TestLinterSeverityHelpers:
    """Tests for Linter severity helper methods."""

    def test_linter_has_create_issue_helper(
        self, lint_context: "LintContext"
    ) -> None:
        """Linter provides create_issue() helper method."""
        from procedurewriter.evals.linter import Linter, LintContext

        class HelperUsingLinter(Linter):
            @property
            def name(self) -> str:
                return "helper_user"

            def _do_lint(self, context: LintContext) -> list[Issue]:
                return [
                    self.create_issue(
                        context=context,
                        code=IssueCode.ORPHAN_CITATION,
                        message="Citation [CIT-99] not found in sources",
                    )
                ]

        linter = HelperUsingLinter()
        issues = linter.lint(lint_context)

        assert len(issues) == 1
        assert issues[0].run_id == lint_context.run_id
        assert issues[0].code == IssueCode.ORPHAN_CITATION
        # Severity should be derived from issue code
        assert issues[0].severity == IssueSeverity.S0

    def test_create_issue_derives_severity_from_code(
        self, lint_context: "LintContext"
    ) -> None:
        """create_issue() automatically sets severity based on issue code."""
        from procedurewriter.evals.linter import Linter, LintContext

        class SeverityTestLinter(Linter):
            @property
            def name(self) -> str:
                return "severity_test"

            def _do_lint(self, context: LintContext) -> list[Issue]:
                return [
                    # S0 issue
                    self.create_issue(
                        context=context,
                        code=IssueCode.DOSE_WITHOUT_EVIDENCE,
                        message="S0 issue",
                    ),
                    # S1 issue
                    self.create_issue(
                        context=context,
                        code=IssueCode.CLAIM_BINDING_FAILED,
                        message="S1 issue",
                    ),
                    # S2 issue
                    self.create_issue(
                        context=context,
                        code=IssueCode.DANISH_TERM_VARIANT,
                        message="S2 issue",
                    ),
                ]

        linter = SeverityTestLinter()
        issues = linter.lint(lint_context)

        assert issues[0].severity == IssueSeverity.S0
        assert issues[1].severity == IssueSeverity.S1
        assert issues[2].severity == IssueSeverity.S2

    def test_create_issue_accepts_optional_fields(
        self, lint_context: "LintContext"
    ) -> None:
        """create_issue() accepts optional line_number, claim_id, source_id."""
        from procedurewriter.evals.linter import Linter, LintContext

        claim_id = uuid4()

        class OptionalFieldsLinter(Linter):
            @property
            def name(self) -> str:
                return "optional_fields"

            def _do_lint(self, context: LintContext) -> list[Issue]:
                return [
                    self.create_issue(
                        context=context,
                        code=IssueCode.ORPHAN_CITATION,
                        message="Issue with location",
                        line_number=42,
                        claim_id=claim_id,
                        source_id="CIT-99",
                    )
                ]

        linter = OptionalFieldsLinter()
        issues = linter.lint(lint_context)

        assert issues[0].line_number == 42
        assert issues[0].claim_id == claim_id
        assert issues[0].source_id == "CIT-99"


# ---------------------------------------------------------------------------
# LINTER STATISTICS TESTS
# ---------------------------------------------------------------------------


class TestLinterStatistics:
    """Tests for linter run statistics."""

    def test_linter_tracks_issues_found(
        self, lint_context: "LintContext"
    ) -> None:
        """Linter tracks how many issues were found in last run."""
        from procedurewriter.evals.linter import Linter, LintContext

        class CountingLinter(Linter):
            @property
            def name(self) -> str:
                return "counting"

            def _do_lint(self, context: LintContext) -> list[Issue]:
                issues = [
                    self.create_issue(
                        context=context,
                        code=IssueCode.ORPHAN_CITATION,
                        message="Issue 1",
                    ),
                    self.create_issue(
                        context=context,
                        code=IssueCode.DANISH_TERM_VARIANT,
                        message="Issue 2",
                    ),
                ]
                return issues

        linter = CountingLinter()
        linter.lint(lint_context)

        assert linter.last_run_issue_count == 2

    def test_linter_issue_count_resets_on_new_run(
        self, lint_context: "LintContext"
    ) -> None:
        """Issue count is reset on each new lint run."""
        from procedurewriter.evals.linter import Linter, LintContext

        call_count = 0

        class VariableIssuesLinter(Linter):
            @property
            def name(self) -> str:
                return "variable"

            def _do_lint(self, context: LintContext) -> list[Issue]:
                nonlocal call_count
                call_count += 1
                # First call returns 2 issues, second returns 1
                if call_count == 1:
                    return [
                        self.create_issue(
                            context=context,
                            code=IssueCode.ORPHAN_CITATION,
                            message="Issue 1",
                        ),
                        self.create_issue(
                            context=context,
                            code=IssueCode.ORPHAN_CITATION,
                            message="Issue 2",
                        ),
                    ]
                return [
                    self.create_issue(
                        context=context,
                        code=IssueCode.ORPHAN_CITATION,
                        message="Issue 1",
                    )
                ]

        linter = VariableIssuesLinter()

        linter.lint(lint_context)
        assert linter.last_run_issue_count == 2

        linter.lint(lint_context)
        assert linter.last_run_issue_count == 1


# ---------------------------------------------------------------------------
# LINTER DESCRIPTION TESTS
# ---------------------------------------------------------------------------


class TestLinterDescription:
    """Tests for linter description property."""

    def test_linter_has_description_property(self) -> None:
        """Linter has a description property for documentation."""
        from procedurewriter.evals.linter import Linter, LintContext

        class DescribedLinter(Linter):
            @property
            def name(self) -> str:
                return "described"

            @property
            def description(self) -> str:
                return "Checks for proper citation formatting"

            def _do_lint(self, context: LintContext) -> list[Issue]:
                return []

        linter = DescribedLinter()
        assert linter.description == "Checks for proper citation formatting"

    def test_linter_description_defaults_to_empty(self) -> None:
        """Linter description defaults to empty string if not overridden."""
        from procedurewriter.evals.linter import Linter, LintContext

        class UndescribedLinter(Linter):
            @property
            def name(self) -> str:
                return "undescribed"

            def _do_lint(self, context: LintContext) -> list[Issue]:
                return []

        linter = UndescribedLinter()
        assert linter.description == ""
