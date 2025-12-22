"""Abstract Linter base class for evaluation rules.

Each linter inherits from Linter and implements:
- name: A string identifier for logging and reporting
- lint(): The main lint logic returning a list of Issues
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

from procedurewriter.models.claims import Claim
from procedurewriter.models.evidence import ClaimEvidenceLink, EvidenceChunk
from procedurewriter.models.issues import Issue, IssueCode, IssueSeverity

# Mapping of issue codes to their severity (from issues.py)
_CODE_TO_SEVERITY = {
    # S0: Safety-critical
    IssueCode.ORPHAN_CITATION: IssueSeverity.S0,
    IssueCode.HALLUCINATED_SOURCE: IssueSeverity.S0,
    IssueCode.DOSE_WITHOUT_EVIDENCE: IssueSeverity.S0,
    IssueCode.THRESHOLD_WITHOUT_EVIDENCE: IssueSeverity.S0,
    IssueCode.CONTRAINDICATION_UNBOUND: IssueSeverity.S0,
    IssueCode.CONFLICTING_DOSES: IssueSeverity.S0,
    IssueCode.MISSING_MANDATORY_SECTION: IssueSeverity.S0,
    # S1: Quality-critical
    IssueCode.CLAIM_BINDING_FAILED: IssueSeverity.S1,
    IssueCode.WEAK_EVIDENCE_FOR_STRONG_CLAIM: IssueSeverity.S1,
    IssueCode.OUTDATED_GUIDELINE: IssueSeverity.S1,
    IssueCode.TEMPLATE_INCOMPLETE: IssueSeverity.S1,
    IssueCode.UNIT_MISMATCH: IssueSeverity.S1,
    IssueCode.AGE_GROUP_CONFLICT: IssueSeverity.S1,
    # S2: Warnings
    IssueCode.DANISH_TERM_VARIANT: IssueSeverity.S2,
    IssueCode.EVIDENCE_REDUNDANCY: IssueSeverity.S2,
    IssueCode.INFORMAL_LANGUAGE: IssueSeverity.S2,
    IssueCode.MISSING_DURATION: IssueSeverity.S2,
}


@dataclass
class LintContext:
    """Context data provided to linters for evaluation.

    Contains all the information a linter needs to check for issues:
    - Procedure metadata (run_id, title, run_dir)
    - The draft text being evaluated
    - Extracted claims and their evidence bindings
    - Source metadata for verification

    Attributes:
        run_id: The pipeline run identifier.
        run_dir: Directory containing run artifacts.
        procedure_title: Title of the procedure being evaluated.
        draft_text: The full text of the procedure draft.
        claims: List of extracted claims.
        chunks: List of evidence chunks.
        links: List of claim-evidence links.
        unbound_claims: Claims that couldn't be bound to evidence.
        sources: List of source metadata dicts.
    """

    run_id: str
    run_dir: Path
    procedure_title: str
    draft_text: str
    claims: list[Claim] = field(default_factory=list)
    chunks: list[EvidenceChunk] = field(default_factory=list)
    links: list[ClaimEvidenceLink] = field(default_factory=list)
    unbound_claims: list[Claim] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)


class Linter(ABC):
    """Abstract base class for all lint checks.

    Each linter checks for a specific type of issue in the procedure.
    Subclasses must implement:
    - name: Property returning the linter identifier
    - lint(): Method returning a list of detected Issues

    The base class provides:
    - create_issue(): Helper to create properly formatted Issues
    - description: Optional property for documentation
    - last_run_issue_count: Tracks issues found in last run

    Example:
        class CitationIntegrityLinter(Linter):
            @property
            def name(self) -> str:
                return "citation_integrity"

            def _do_lint(self, context: LintContext) -> list[Issue]:
                issues = []
                for citation in find_citations(context.draft_text):
                    if not citation_exists(citation, context.sources):
                        issues.append(self.create_issue(
                            context=context,
                            code=IssueCode.ORPHAN_CITATION,
                            message=f"Citation {citation} not found",
                        ))
                return issues
    """

    def __init__(self) -> None:
        """Initialize linter with statistics tracking."""
        self._last_run_issue_count: int = 0

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the linter name for logging and reporting."""
        ...

    @property
    def description(self) -> str:
        """Return a description of what this linter checks.

        Subclasses can override this to provide documentation.
        """
        return ""

    @property
    def last_run_issue_count(self) -> int:
        """Return the number of issues found in the last run."""
        return self._last_run_issue_count

    @abstractmethod
    def _do_lint(self, context: LintContext) -> list[Issue]:
        """Execute the lint check and return detected issues.

        Subclasses implement this method with their actual lint logic.

        Args:
            context: LintContext containing all procedure data

        Returns:
            List of Issue objects for detected problems
        """
        ...

    def lint(self, context: LintContext) -> list[Issue]:
        """Execute the lint check, track stats, and return detected issues.

        This is the public method that wraps _do_lint() and tracks statistics.

        Args:
            context: LintContext containing all procedure data

        Returns:
            List of Issue objects for detected problems
        """
        issues = self._do_lint(context)
        self._last_run_issue_count = len(issues)
        return issues

    def __call__(self, context: LintContext) -> list[Issue]:
        """Allow linter to be called as a function.

        This delegates to lint() which tracks statistics.

        Args:
            context: LintContext containing all procedure data

        Returns:
            List of Issue objects for detected problems
        """
        return self.lint(context)

    def create_issue(
        self,
        context: LintContext,
        code: IssueCode,
        message: str,
        line_number: int | None = None,
        claim_id: UUID | None = None,
        source_id: str | None = None,
    ) -> Issue:
        """Create an Issue with automatic severity derivation.

        This helper method creates properly formatted Issue objects
        with severity automatically derived from the issue code.

        Args:
            context: LintContext for run_id
            code: The specific IssueCode
            message: Human-readable issue description
            line_number: Optional line number in the procedure
            claim_id: Optional related claim UUID
            source_id: Optional related source ID

        Returns:
            Issue object with all fields populated
        """
        severity = _CODE_TO_SEVERITY.get(code, IssueSeverity.S2)

        return Issue(
            run_id=context.run_id,
            code=code,
            severity=severity,
            message=message,
            line_number=line_number,
            claim_id=claim_id,
            source_id=source_id,
        )
