"""
Content Generalizer - Removes department-specific content from procedures.

Transforms hospital-specific instructions into universal guidance that any
Danish emergency medicine doctor can use, regardless of their hospital.

Examples:
    - "tlf. 5804" → "[LOKAL: afdelingens nummer]"
    - "stue 99" → "[LOKAL: relevant behandlingsrum]"
    - "i Skejby" → "" (removed)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class GeneralizationStats:
    """Statistics from content generalization."""
    phone_numbers: int = 0
    room_references: int = 0
    location_references: int = 0
    hospital_references: int = 0
    system_references: int = 0
    role_assignments: int = 0
    total_replacements: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "phone_numbers": self.phone_numbers,
            "room_references": self.room_references,
            "location_references": self.location_references,
            "hospital_references": self.hospital_references,
            "system_references": self.system_references,
            "role_assignments": self.role_assignments,
            "total": self.total_replacements,
        }


@dataclass
class ReplacementPattern:
    """A pattern for detecting and replacing department-specific content."""
    pattern: str
    replacement: str
    category: str
    flags: int = re.IGNORECASE

    def compile(self) -> re.Pattern:
        return re.compile(self.pattern, self.flags)


class ContentGeneralizer:
    """
    Generalizes department-specific content in medical procedures.

    Replaces local phone numbers, room references, hospital names, and
    IT system references with universal placeholders or removes them.
    """

    def __init__(self, use_lokal_markers: bool = True):
        """
        Initialize the generalizer.

        Args:
            use_lokal_markers: If True, use [LOKAL: ...] markers.
                              If False, use plain text replacements.
        """
        self.use_lokal_markers = use_lokal_markers
        self.patterns = self._build_patterns()
        self.stats = GeneralizationStats()

    def _build_patterns(self) -> list[ReplacementPattern]:
        """Build the list of replacement patterns."""
        lokal = "[LOKAL]" if self.use_lokal_markers else ""

        patterns = [
            # === PHONE NUMBERS ===
            # "tlf. 5804", "tlf 5804", "telefon 12345678"
            ReplacementPattern(
                pattern=r'\(?\s*tlf\.?\s*:?\s*\d{4,8}\s*\)?',
                replacement=f' {lokal}' if lokal else '',
                category="phone_numbers",
            ),
            ReplacementPattern(
                pattern=r'\(?\s*telefon\s*:?\s*\d{4,8}\s*\)?',
                replacement=f' {lokal}' if lokal else '',
                category="phone_numbers",
            ),
            # Phone number in parentheses at end of sentence
            ReplacementPattern(
                pattern=r'\s*\(\s*\d{4,8}\s*\)',
                replacement='',
                category="phone_numbers",
            ),

            # === ROOM REFERENCES ===
            # "stue 99", "stue 5", "på stue 12"
            ReplacementPattern(
                pattern=r'(?:på\s+)?stue\s+\d+',
                replacement=f'{lokal}' if lokal else 'behandlingsrum',
                category="room_references",
            ),
            # "overfor stue 99" - remove entirely
            ReplacementPattern(
                pattern=r'\s*\(?overfor\s+stue\s+\d+\)?',
                replacement='',
                category="room_references",
            ),

            # === LOCATION REFERENCES ===
            # "ved medicinsk base (overfor stue 99)"
            ReplacementPattern(
                pattern=r'ved\s+medicinsk\s+base\s*\([^)]*\)',
                replacement='fra afdelingens udstyrsdepot',
                category="location_references",
            ),
            # "ved medicinsk base"
            ReplacementPattern(
                pattern=r'ved\s+medicinsk\s+base',
                replacement='fra afdelingens udstyrsdepot',
                category="location_references",
            ),
            # "pleura-procedurevogn ved medicinsk base"
            ReplacementPattern(
                pattern=r'pleura-procedurevogn\s+ved\s+medicinsk\s+base\s*\([^)]*\)',
                replacement='afdelingens pleura-procedurevogn',
                category="location_references",
            ),
            ReplacementPattern(
                pattern=r'pleura-procedurevogn\s+ved\s+medicinsk\s+base',
                replacement='afdelingens pleura-procedurevogn',
                category="location_references",
            ),

            # === HOSPITAL/DEPARTMENT REFERENCES ===
            # "i Skejby", "i Odense", "i Aalborg" etc.
            ReplacementPattern(
                pattern=r'\s+i\s+(?:Skejby|Odense|Aalborg|Herlev|Rigshospitalet|Bispebjerg|Hvidovre|Gentofte|Hillerød)',
                replacement='',
                category="hospital_references",
            ),
            # "på Herlev Hospital", "på Rigshospitalet"
            ReplacementPattern(
                pattern=r'på\s+(?:Herlev|Bispebjerg|Hvidovre|Gentofte|Hillerød)\s*(?:Hospital|Sygehus)?',
                replacement='på relevant afdeling',
                category="hospital_references",
            ),
            # "HEH", "HGH", "OUH" hospital abbreviations in parentheses
            ReplacementPattern(
                pattern=r'\s*\(?\s*(?:HEH|HGH|OUH|AUH|RH|BBH|HVH)\s*\)?',
                replacement='',
                category="hospital_references",
            ),

            # === IT SYSTEM REFERENCES ===
            # "CASE-bestilling"
            ReplacementPattern(
                pattern=r'CASE-bestilling',
                replacement='elektronisk bestilling',
                category="system_references",
            ),
            # "i EPIC", "via EPIC"
            ReplacementPattern(
                pattern=r'(?:i|via)\s+EPIC',
                replacement='i journalsystemet',
                category="system_references",
            ),
            # "i Sundhedsplatformen"
            ReplacementPattern(
                pattern=r'(?:i|via)\s+Sundhedsplatformen',
                replacement='i journalsystemet',
                category="system_references",
            ),

            # === ROLE CLARIFICATIONS ===
            # These are trickier - we want to keep the role but clarify it's local
            # "lungemedicinsk bagvagt/beredskabsvagt" - keep as is, it's universal
            # But specific assignments like "ortopædkirurgisk vagthavende anlægger"
            # should note this may vary

            # === SPECIFIC DEPARTMENT WORKFLOWS ===
            # "henvis via ultralydsafdeling" - keep, it's universal process
            # But specific room/contact info should be generalized

            # === CLEANUP PATTERNS ===
            # Remove double spaces created by removals
            ReplacementPattern(
                pattern=r'  +',
                replacement=' ',
                category="cleanup",
                flags=0,
            ),
            # Remove space before punctuation
            ReplacementPattern(
                pattern=r'\s+([.,;:])',
                replacement=r'\1',
                category="cleanup",
                flags=0,
            ),
            # Remove empty parentheses
            ReplacementPattern(
                pattern=r'\s*\(\s*\)',
                replacement='',
                category="cleanup",
                flags=0,
            ),
        ]

        return patterns

    def generalize(self, content: str) -> tuple[str, GeneralizationStats]:
        """
        Generalize department-specific content.

        Args:
            content: The procedure markdown content

        Returns:
            Tuple of (generalized_content, stats)
        """
        self.stats = GeneralizationStats()
        result = content

        for pattern_def in self.patterns:
            compiled = pattern_def.compile()

            # Count matches before replacement
            matches = compiled.findall(result)
            match_count = len(matches)

            if match_count > 0 and pattern_def.category != "cleanup":
                # Update stats by category
                if pattern_def.category == "phone_numbers":
                    self.stats.phone_numbers += match_count
                elif pattern_def.category == "room_references":
                    self.stats.room_references += match_count
                elif pattern_def.category == "location_references":
                    self.stats.location_references += match_count
                elif pattern_def.category == "hospital_references":
                    self.stats.hospital_references += match_count
                elif pattern_def.category == "system_references":
                    self.stats.system_references += match_count
                elif pattern_def.category == "role_assignments":
                    self.stats.role_assignments += match_count

                self.stats.total_replacements += match_count

            # Apply replacement
            result = compiled.sub(pattern_def.replacement, result)

        # Final cleanup - remove multiple [LOKAL] in same sentence
        if self.use_lokal_markers:
            result = self._deduplicate_lokal_markers(result)

        return result, self.stats

    def _deduplicate_lokal_markers(self, content: str) -> str:
        """Remove duplicate [LOKAL] markers in the same line."""
        lines = content.split('\n')
        result_lines = []

        for line in lines:
            # Count [LOKAL] occurrences
            lokal_count = line.count('[LOKAL]')
            if lokal_count > 1:
                # Keep only the first one
                first_pos = line.find('[LOKAL]')
                # Replace all, then put back the first
                line_without = line.replace('[LOKAL]', '')
                line = line_without[:first_pos] + '[LOKAL]' + line_without[first_pos:]
            result_lines.append(line)

        return '\n'.join(result_lines)

    def add_pattern(self, pattern: str, replacement: str, category: str) -> None:
        """
        Add a custom replacement pattern.

        Args:
            pattern: Regex pattern to match
            replacement: Replacement string
            category: Category for statistics
        """
        self.patterns.insert(0, ReplacementPattern(
            pattern=pattern,
            replacement=replacement,
            category=category,
        ))


def generalize_procedure_content(content: str, use_lokal_markers: bool = True) -> tuple[str, dict[str, Any]]:
    """
    Convenience function to generalize procedure content.

    Args:
        content: The procedure markdown content
        use_lokal_markers: Whether to use [LOKAL] markers

    Returns:
        Tuple of (generalized_content, stats_dict)
    """
    generalizer = ContentGeneralizer(use_lokal_markers=use_lokal_markers)
    result, stats = generalizer.generalize(content)
    return result, stats.to_dict()
