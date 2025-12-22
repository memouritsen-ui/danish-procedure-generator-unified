"""UnitNormalizer - Standardize medical units to canonical forms.

This module normalizes medical units found in claim text to ensure
consistent representation for comparison, validation, and display.

Key normalizations:
- mcg/ug → μg (microgram to Greek mu)
- IE → IU (Danish to international units)
- ml/mL → ml (standardize milliliter)
- mg/kg/dag → mg/kg/d (Danish day to abbreviation)
- Spacing normalization (e.g., "50mg" → "50 mg")
"""

from __future__ import annotations

import re


class UnitNormalizer:
    """Normalizer for medical units in Danish and international formats.

    Converts various unit representations to canonical forms for
    consistent comparison and display. Handles both simple units
    (mg, g, ml) and compound units (mg/kg/d, μg/kg/min).
    """

    # Simple unit mappings (lowercase key → canonical value)
    UNIT_MAP: dict[str, str] = {
        # Microgram variations → μg
        "mcg": "μg",
        "ug": "μg",
        "μg": "μg",
        "mikrogram": "μg",
        # Milligram variations → mg
        "mg": "mg",
        "milligram": "mg",
        # Gram variations → g
        "g": "g",
        "gram": "g",
        # Milliliter variations → ml
        "ml": "ml",
        "milliliter": "ml",
        # International units (Danish IE → IU)
        "ie": "IU",
        "iu": "IU",
        # Generic units
        "u": "U",
        "units": "U",
        "enheder": "U",  # Danish
        # Percentage
        "%": "%",
        "procent": "%",
        # Time units
        "min": "min",
        "h": "h",
        "t": "h",  # Danish 'time' (hour) abbreviation
        "time": "h",  # Danish full word
        # Day units
        "d": "d",
        "dag": "d",  # Danish
        "døgn": "d",  # Danish (24 hours)
        # Weight
        "kg": "kg",
        # Volume rate
        "l/min": "L/min",
        # Liter (preserve uppercase for SI convention)
        "l": "L",
    }

    # Pattern to match number-unit without space (e.g., "500mg")
    NO_SPACE_PATTERN = re.compile(r"(\d+(?:[.,]\d+)?)\s*([a-zA-Zμ]+(?:/[a-zA-Zμ]+)*)")

    def __init__(self) -> None:
        """Initialize the unit normalizer."""
        pass

    def normalize_unit(self, unit: str | None) -> str | None:
        """Normalize a single unit to its canonical form.

        Args:
            unit: Unit string to normalize (e.g., "mcg", "IE", "mg/kg/dag").

        Returns:
            Normalized unit string, or original if not recognized.
            Returns None if input is None, empty string if input is empty.
        """
        if unit is None:
            return None

        if not unit:
            return ""

        # Strip whitespace
        unit = unit.strip()

        if not unit:
            return ""

        # Check if compound unit (contains /)
        if "/" in unit:
            return self._normalize_compound_unit(unit)

        # Simple unit lookup (case-insensitive)
        lower_unit = unit.lower()
        if lower_unit in self.UNIT_MAP:
            return self.UNIT_MAP[lower_unit]

        # Return original if not found
        return unit

    def _normalize_compound_unit(self, unit: str) -> str:
        """Normalize a compound unit like mg/kg/d.

        Args:
            unit: Compound unit string with / separators.

        Returns:
            Normalized compound unit.
        """
        parts = unit.split("/")
        normalized_parts = []

        for part in parts:
            lower_part = part.lower().strip()
            if lower_part in self.UNIT_MAP:
                normalized_parts.append(self.UNIT_MAP[lower_part])
            else:
                # Keep original case for unrecognized parts
                normalized_parts.append(part.lower() if part.isalpha() else part)

        return "/".join(normalized_parts)

    def normalize_dose_text(self, text: str) -> str:
        """Normalize units within a complete dose text string.

        Finds and normalizes all units in the text, also adding
        proper spacing between numbers and units if missing.

        Args:
            text: Full dose text (e.g., "amoxicillin 50mg/kg/dag").

        Returns:
            Text with normalized units (e.g., "amoxicillin 50 mg/kg/d").
        """
        if not text:
            return text

        result = text

        # First, add spacing between numbers and units if missing
        def add_space(match: re.Match[str]) -> str:
            number = match.group(1)
            unit = match.group(2)
            normalized_unit = self.normalize_unit(unit)
            return f"{number} {normalized_unit}"

        # Find all number+unit patterns and normalize
        result = self.NO_SPACE_PATTERN.sub(add_space, result)

        return result
