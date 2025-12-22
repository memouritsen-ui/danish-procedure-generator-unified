"""UnitCheckLinter - Validates that all claim units are valid SI units.

This linter checks each claim's unit field against the known valid units
defined in UnitNormalizer.UNIT_MAP. Invalid or unrecognized units produce
S1 (quality-critical) UNIT_MISMATCH issues.
"""

from __future__ import annotations

from procedurewriter.claims.normalizer import UnitNormalizer
from procedurewriter.evals.linter import Linter, LintContext
from procedurewriter.models.issues import Issue, IssueCode


class UnitCheckLinter(Linter):
    """Linter that validates all claim units are recognized SI units.

    This linter:
    1. Iterates through all claims in the context
    2. For claims with a unit field set, validates against UNIT_MAP
    3. For compound units (mg/kg/d), validates each component
    4. Creates S1 UNIT_MISMATCH issues for unrecognized units

    Invalid units are quality-critical because they may indicate
    data extraction errors or non-standard terminology that could
    cause confusion.
    """

    def __init__(self) -> None:
        """Initialize the linter with a UnitNormalizer."""
        super().__init__()
        self._normalizer = UnitNormalizer()

    @property
    def name(self) -> str:
        """Return the linter name."""
        return "unit_check"

    @property
    def description(self) -> str:
        """Return a description of what this linter checks."""
        return "Validates that all claim units are recognized SI units from the UNIT_MAP"

    def _do_lint(self, context: LintContext) -> list[Issue]:
        """Check that all claim units are valid SI units.

        Args:
            context: LintContext containing claims to check

        Returns:
            List of UNIT_MISMATCH issues for unrecognized units
        """
        issues: list[Issue] = []

        for claim in context.claims:
            # Skip claims without units
            if not claim.unit:
                continue

            # Check if the unit is valid
            invalid_parts = self._find_invalid_unit_parts(claim.unit)

            if invalid_parts:
                issue = self.create_issue(
                    context=context,
                    code=IssueCode.UNIT_MISMATCH,
                    message=f"Unrecognized unit: '{claim.unit}' (invalid part: {', '.join(invalid_parts)})",
                    line_number=claim.line_number,
                    claim_id=claim.id,
                )
                issues.append(issue)

        return issues

    def _find_invalid_unit_parts(self, unit: str) -> list[str]:
        """Find parts of a unit that are not in the UNIT_MAP.

        For simple units, returns empty list if valid or [unit] if invalid.
        For compound units (mg/kg/d), returns list of invalid parts.

        Args:
            unit: Unit string to validate (simple or compound)

        Returns:
            List of invalid unit parts (empty if all valid)
        """
        if not unit or not unit.strip():
            return []

        unit = unit.strip()

        # Check if compound unit (contains /)
        if "/" in unit:
            return self._validate_compound_unit(unit)

        # Simple unit validation
        if self._is_valid_unit(unit):
            return []

        return [unit]

    def _validate_compound_unit(self, unit: str) -> list[str]:
        """Validate a compound unit like mg/kg/d.

        Args:
            unit: Compound unit string with / separators

        Returns:
            List of invalid parts (empty if all valid)
        """
        parts = unit.split("/")
        invalid_parts: list[str] = []

        for part in parts:
            part = part.strip()
            if part and not self._is_valid_unit(part):
                invalid_parts.append(part)

        return invalid_parts

    def _is_valid_unit(self, unit: str) -> bool:
        """Check if a simple unit is in the UNIT_MAP.

        Args:
            unit: Simple unit string (not compound)

        Returns:
            True if unit is recognized, False otherwise
        """
        # Check case-insensitive against UNIT_MAP
        return unit.lower() in self._normalizer.UNIT_MAP
