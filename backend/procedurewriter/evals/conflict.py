"""ConflictDetectionLinter - Detects conflicting claims on the same topic.

This linter scans for internal contradictions in the procedure:
1. DOSE claims: Same drug with different doses (S0 - safety critical)
2. THRESHOLD claims: Same parameter with different values (S1 - quality critical)

Medical procedures MUST be internally consistent. Conflicting doses for the
same drug can cause serious patient harm, hence S0 (safety-critical) severity.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import TYPE_CHECKING

from procedurewriter.evals.linter import Linter, LintContext
from procedurewriter.models.claims import Claim, ClaimType
from procedurewriter.models.issues import Issue, IssueCode

if TYPE_CHECKING:
    pass


# Common drug name patterns (first word typically is the drug)
# This regex captures the first word from the claim text
_DRUG_NAME_PATTERN = re.compile(r"^([a-zA-ZæøåÆØÅ]+)", re.IGNORECASE)

# Common threshold parameter patterns
_THRESHOLD_PARAM_PATTERNS = [
    (re.compile(r"\b(SpO2|spo2|saturation|sat)\b", re.IGNORECASE), "SpO2"),
    (re.compile(r"\b(temperatur|temp|temperature)\b", re.IGNORECASE), "temperatur"),
    (re.compile(r"\b(puls|heart\s*rate|HR)\b", re.IGNORECASE), "puls"),
    (re.compile(r"\b(blodtryk|BP|blood\s*pressure)\b", re.IGNORECASE), "blodtryk"),
    (re.compile(r"\b(respirationsfrekvens|RR|resp\s*rate)\b", re.IGNORECASE), "respirationsfrekvens"),
    (re.compile(r"\b(GCS|Glasgow)\b", re.IGNORECASE), "GCS"),
    (re.compile(r"\b(CURB|curb-65)\b", re.IGNORECASE), "CURB-65"),
]


def _extract_drug_name(text: str) -> str | None:
    """Extract drug name from claim text.

    Assumes drug name is the first word in the claim text.
    Returns lowercase for case-insensitive comparison.

    Args:
        text: Claim text (e.g., "Adrenalin 0.5 mg i.m.")

    Returns:
        Drug name in lowercase, or None if not found.
    """
    match = _DRUG_NAME_PATTERN.match(text.strip())
    if match:
        return match.group(1).lower()
    return None


def _extract_threshold_param(text: str) -> str | None:
    """Extract threshold parameter from claim text.

    Looks for known parameter names like SpO2, temperatur, puls, etc.

    Args:
        text: Claim text (e.g., "SpO2 < 92%")

    Returns:
        Normalized parameter name, or None if not found.
    """
    for pattern, param_name in _THRESHOLD_PARAM_PATTERNS:
        if pattern.search(text):
            return param_name.lower()
    return None


class ConflictDetectionLinter(Linter):
    """Linter that detects conflicting claims on the same topic.

    This linter:
    1. Groups DOSE claims by drug name
    2. Groups THRESHOLD claims by parameter name
    3. Detects when claims in the same group have different values
    4. Creates issues with appropriate severity (S0 for doses, S1 for thresholds)

    Conflicting doses are S0 (safety-critical) because giving the wrong dose
    can cause serious patient harm or death.
    """

    def __init__(self) -> None:
        """Initialize the linter."""
        super().__init__()

    @property
    def name(self) -> str:
        """Return the linter name."""
        return "conflict_detection"

    @property
    def description(self) -> str:
        """Return a description of what this linter checks."""
        return (
            "Detects conflicting claims on the same topic, such as different "
            "doses for the same drug or different thresholds for the same parameter"
        )

    def _do_lint(self, context: LintContext) -> list[Issue]:
        """Scan claims for conflicts.

        Args:
            context: LintContext containing claims to check

        Returns:
            List of CONFLICTING_DOSES or AGE_GROUP_CONFLICT issues
        """
        issues: list[Issue] = []

        if not context.claims:
            return issues

        # Check DOSE conflicts
        issues.extend(self._check_dose_conflicts(context))

        # Check THRESHOLD conflicts
        issues.extend(self._check_threshold_conflicts(context))

        return issues

    def _check_dose_conflicts(self, context: LintContext) -> list[Issue]:
        """Check for conflicting DOSE claims.

        Groups claims by drug name and flags when the same drug has
        different normalized_value entries.

        Args:
            context: LintContext with claims

        Returns:
            List of CONFLICTING_DOSES issues
        """
        issues: list[Issue] = []

        # Group DOSE claims by drug name
        dose_claims = [c for c in context.claims if c.claim_type == ClaimType.DOSE]
        drug_groups: dict[str, list[Claim]] = defaultdict(list)

        for claim in dose_claims:
            drug_name = _extract_drug_name(claim.text)
            if drug_name and claim.normalized_value:
                drug_groups[drug_name].append(claim)

        # Check each drug group for conflicts
        for drug_name, claims in drug_groups.items():
            if len(claims) < 2:
                continue

            # Collect unique normalized values
            values_seen: dict[str, Claim] = {}
            for claim in claims:
                val = claim.normalized_value
                if val not in values_seen:
                    values_seen[val] = claim

            # If more than one unique value, we have a conflict
            if len(values_seen) > 1:
                values_list = list(values_seen.keys())
                first_claim = values_seen[values_list[0]]

                # Create issue for the conflict
                issue = self.create_issue(
                    context=context,
                    code=IssueCode.CONFLICTING_DOSES,
                    message=(
                        f"Conflicting doses for '{drug_name}': "
                        f"found values {', '.join(sorted(values_list))} "
                        f"in different parts of the procedure"
                    ),
                    line_number=first_claim.line_number,
                    claim_id=first_claim.id,
                )
                issues.append(issue)

        return issues

    def _check_threshold_conflicts(self, context: LintContext) -> list[Issue]:
        """Check for conflicting THRESHOLD claims.

        Groups claims by parameter name and flags when the same parameter
        has different threshold values.

        Args:
            context: LintContext with claims

        Returns:
            List of AGE_GROUP_CONFLICT issues (used for threshold conflicts)
        """
        issues: list[Issue] = []

        # Group THRESHOLD claims by parameter
        threshold_claims = [c for c in context.claims if c.claim_type == ClaimType.THRESHOLD]
        param_groups: dict[str, list[Claim]] = defaultdict(list)

        for claim in threshold_claims:
            param_name = _extract_threshold_param(claim.text)
            if param_name and claim.normalized_value:
                param_groups[param_name].append(claim)

        # Check each parameter group for conflicts
        for param_name, claims in param_groups.items():
            if len(claims) < 2:
                continue

            # Collect unique normalized values
            values_seen: dict[str, Claim] = {}
            for claim in claims:
                val = claim.normalized_value
                if val not in values_seen:
                    values_seen[val] = claim

            # If more than one unique value, we have a conflict
            if len(values_seen) > 1:
                values_list = list(values_seen.keys())
                first_claim = values_seen[values_list[0]]

                # Use AGE_GROUP_CONFLICT for threshold conflicts
                # (could also add a specific threshold conflict code)
                issue = self.create_issue(
                    context=context,
                    code=IssueCode.AGE_GROUP_CONFLICT,
                    message=(
                        f"Conflicting thresholds for '{param_name}': "
                        f"found values {', '.join(sorted(values_list))} "
                        f"in different parts of the procedure"
                    ),
                    line_number=first_claim.line_number,
                    claim_id=first_claim.id,
                )
                issues.append(issue)

        return issues
