"""Workflow content filtering for medical procedures.

Phase 2: Workflow Content Filter
Separates organizational/workflow content from clinical/technique content.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Pattern


# Workflow patterns that indicate organizational (non-clinical) content
WORKFLOW_PATTERNS: list[tuple[str, Pattern[str]]] = [
    # Contact/call patterns
    ("ring_til_bagvagt", re.compile(r"ring\s+til\s+bagvagt", re.I)),
    ("kontakt_bagvagt", re.compile(r"kontakt\s+bagvagt", re.I)),
    ("kontakt_forvagt", re.compile(r"kontakt\s+forvagt", re.I)),
    ("tilkald_anaestesi", re.compile(r"tilkald\s+an(?:æ|ae?)stesi", re.I)),
    ("ring_til_anaestesi", re.compile(r"ring\s+til\s+an(?:æ|ae?)stesi", re.I)),
    ("kontakt_anaestesi", re.compile(r"kontakt\s+an(?:æ|ae?)stesi", re.I)),

    # Phone numbers and contact with phone
    ("telefon", re.compile(r"tlf\.?\s*\d+", re.I)),
    ("telefonnummer", re.compile(r"telefon\s*:?\s*\d+", re.I)),
    ("kontakt_paa_tlf", re.compile(r"kontakt\s+.*\s+p[åa]\s+tlf", re.I)),
    ("paa_tlf", re.compile(r"p[åa]\s+tlf\.?\s*\d*", re.I)),

    # Local protocol references
    ("lokal_retningslinje", re.compile(r"f[øo]lg\s+lokal\s+retningslinje", re.I)),
    ("lokal_instruks", re.compile(r"lokal\s+instruks", re.I)),
    ("lokal_protokol", re.compile(r"lokal\s+protokol", re.I)),

    # Role/team organization
    ("rollefordeling", re.compile(r"aftal\s+rollefordeling", re.I)),
    ("rollefordeling_alt", re.compile(r"rollefordeling", re.I)),
    ("aftal_med_teamet", re.compile(r"aftal\s+(med\s+)?teamet", re.I)),
    ("teamleder", re.compile(r"teamleder", re.I)),

    # Colleague/assistance
    ("spoerg_kollega", re.compile(r"sp[øo]rg\s+.*kollega", re.I)),
    ("erfaren_kollega", re.compile(r"erfaren\s+kollega", re.I)),

    # Department-specific
    ("afdelingens", re.compile(r"tjek\s+afdelingens", re.I)),
    ("afdelingens_protokol", re.compile(r"afdelingens\s+protokol", re.I)),
    ("hospitalets", re.compile(r"hospitalets\s+(retningslinje|protokol|instruks)", re.I)),

    # Time-based workflow
    ("dagtid", re.compile(r"(i\s+)?dagtid", re.I)),
    ("vagttid", re.compile(r"(i\s+)?vagttid", re.I)),
    ("weekend", re.compile(r"(i\s+)?weekend", re.I)),
]


@dataclass
class FilterStats:
    """Statistics from workflow filtering."""

    total_chars: int = 0
    clinical_chars: int = 0
    workflow_chars: int = 0
    pattern_matches: dict[str, int] = field(default_factory=dict)

    @property
    def workflow_percentage(self) -> float:
        """Percentage of content that is workflow."""
        if self.total_chars == 0:
            return 0.0
        return (self.workflow_chars / self.total_chars) * 100


class WorkflowFilter:
    """Filters workflow content from clinical content in medical procedures.

    Separates organizational content (phone numbers, who to call, local protocols)
    from clinical content (technique, anatomy, equipment, safety).
    """

    def __init__(self) -> None:
        self._patterns = WORKFLOW_PATTERNS
        self._last_stats: FilterStats | None = None

    def filter_workflow_content(self, text: str) -> tuple[str, str]:
        """Separate workflow content from clinical content.

        Args:
            text: Input text containing mixed content

        Returns:
            Tuple of (clinical_content, workflow_content)
        """
        if not text or not text.strip():
            self._last_stats = FilterStats()
            return "", ""

        # Split text into sentences/lines for processing
        lines = self._split_into_segments(text)

        clinical_lines: list[str] = []
        workflow_lines: list[str] = []
        pattern_counts: dict[str, int] = {}

        for line in lines:
            matched_pattern = self._match_workflow_pattern(line)
            if matched_pattern:
                workflow_lines.append(line)
                pattern_counts[matched_pattern] = pattern_counts.get(matched_pattern, 0) + 1
            else:
                clinical_lines.append(line)

        clinical_text = self._join_segments(clinical_lines)
        workflow_text = self._join_segments(workflow_lines)

        # Calculate stats
        self._last_stats = FilterStats(
            total_chars=len(text),
            clinical_chars=len(clinical_text),
            workflow_chars=len(workflow_text),
            pattern_matches=pattern_counts,
        )

        return clinical_text, workflow_text

    def filter_batch(self, texts: list[str]) -> list[tuple[str, str]]:
        """Filter multiple texts.

        Args:
            texts: List of texts to filter

        Returns:
            List of (clinical, workflow) tuples
        """
        return [self.filter_workflow_content(text) for text in texts]

    def get_filter_stats(self) -> dict:
        """Get statistics from the last filter operation.

        Returns:
            Dictionary with workflow_percentage and pattern_matches
        """
        if self._last_stats is None:
            return {
                "workflow_percentage": 0.0,
                "pattern_matches": {},
            }

        return {
            "workflow_percentage": self._last_stats.workflow_percentage,
            "pattern_matches": self._last_stats.pattern_matches,
            "total_chars": self._last_stats.total_chars,
            "clinical_chars": self._last_stats.clinical_chars,
            "workflow_chars": self._last_stats.workflow_chars,
        }

    def _split_into_segments(self, text: str) -> list[str]:
        """Split text into processable segments (sentences/lines).

        Handles:
        - Numbered lists (1. 2. 3.)
        - Bullet points
        - Newline-separated content
        - Period-separated sentences
        """
        # First split by newlines
        lines = text.split("\n")

        segments: list[str] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if it's a numbered or bulleted item
            if re.match(r"^\d+\.\s+", line) or re.match(r"^[-•]\s+", line):
                segments.append(line)
            else:
                # Split by sentence-ending punctuation, but not abbreviations
                # Don't split on periods followed by digits (e.g., "tlf. 12345")
                # Don't split after digit+period (e.g., "5. interkostalrum")
                # Don't split on lowercase letters followed by period (likely abbreviation)
                sentence_parts = re.split(
                    r"(?<=[.!?])(?<!\d\.)(?!\s*\d)\s+",
                    line
                )
                segments.extend([s.strip() for s in sentence_parts if s.strip()])

        return segments

    def _join_segments(self, segments: list[str]) -> str:
        """Join segments back into coherent text, preserving structure."""
        if not segments:
            return ""

        # Preserve original structure by joining with newlines
        # This maintains document formatting and readability
        return "\n".join(seg.strip() for seg in segments if seg.strip())

    def _match_workflow_pattern(self, text: str) -> str | None:
        """Check if text matches any workflow pattern.

        Args:
            text: Text segment to check

        Returns:
            Pattern name if matched, None otherwise
        """
        for pattern_name, pattern in self._patterns:
            if pattern.search(text):
                return pattern_name
        return None
