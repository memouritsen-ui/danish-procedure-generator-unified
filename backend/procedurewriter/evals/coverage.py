"""ClaimCoverageLinter - Checks that all claims are bound to evidence.

This linter verifies that every extracted claim has been successfully
bound to supporting evidence. The severity of unbound claims depends
on their type:

- DOSE, THRESHOLD, CONTRAINDICATION → S0 (safety-critical)
- Other types (RECOMMENDATION, RED_FLAG, ALGORITHM_STEP) → S1 (quality)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from procedurewriter.evals.linter import Linter, LintContext
from procedurewriter.models.claims import ClaimType
from procedurewriter.models.issues import Issue, IssueCode

if TYPE_CHECKING:
    from procedurewriter.models.claims import Claim


# Claim types that require S0 (safety-critical) issues when unbound
# These directly affect patient safety if evidence is missing
_SAFETY_CRITICAL_TYPES = {
    ClaimType.DOSE,
    ClaimType.THRESHOLD,
    ClaimType.CONTRAINDICATION,
}

# Mapping of safety-critical claim types to their specific issue codes
_TYPE_TO_ISSUE_CODE = {
    ClaimType.DOSE: IssueCode.DOSE_WITHOUT_EVIDENCE,
    ClaimType.THRESHOLD: IssueCode.THRESHOLD_WITHOUT_EVIDENCE,
    ClaimType.CONTRAINDICATION: IssueCode.CONTRAINDICATION_UNBOUND,
}


class ClaimCoverageLinter(Linter):
    """Linter that checks all claims are bound to evidence.

    This linter:
    1. Examines the unbound_claims list in the context
    2. Creates S0 issues for safety-critical unbound claims (DOSE, THRESHOLD, CONTRAINDICATION)
    3. Creates S1 issues for other unbound claims (RECOMMENDATION, RED_FLAG, ALGORITHM_STEP)
    """

    @property
    def name(self) -> str:
        """Return the linter name."""
        return "claim_coverage"

    @property
    def description(self) -> str:
        """Return a description of what this linter checks."""
        return "Verifies all extracted claims have been bound to supporting evidence"

    def _do_lint(self, context: LintContext) -> list[Issue]:
        """Check that all claims are bound to evidence.

        Args:
            context: LintContext containing unbound_claims list

        Returns:
            List of issues for unbound claims
        """
        issues: list[Issue] = []

        for claim in context.unbound_claims:
            issue = self._create_issue_for_claim(context, claim)
            issues.append(issue)

        return issues

    def _create_issue_for_claim(self, context: LintContext, claim: Claim) -> Issue:
        """Create an issue for an unbound claim.

        The issue code and severity depend on the claim type.

        Args:
            context: LintContext for creating the issue
            claim: The unbound claim

        Returns:
            Issue with appropriate code and severity
        """
        if claim.claim_type in _SAFETY_CRITICAL_TYPES:
            # Safety-critical claim types have specific issue codes
            code = _TYPE_TO_ISSUE_CODE[claim.claim_type]
        else:
            # Other types use generic CLAIM_BINDING_FAILED
            code = IssueCode.CLAIM_BINDING_FAILED

        # Truncate claim text if too long for message
        claim_text = claim.text
        if len(claim_text) > 50:
            claim_text = claim_text[:47] + "..."

        return self.create_issue(
            context=context,
            code=code,
            message=f"Unbound {claim.claim_type.value} claim: {claim_text}",
            claim_id=claim.id,
            line_number=claim.line_number,
        )
