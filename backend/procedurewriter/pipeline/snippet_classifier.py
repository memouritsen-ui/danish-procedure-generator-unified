"""Snippet classification for content type filtering.

Phase 1: Source Diversification - Content Type Classification
Classifies snippets as technique, workflow, evidence, safety, etc.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Pattern


class SnippetType(Enum):
    """Classification types for medical procedure content."""

    TECHNIQUE = "technique"  # HOW to do it (anatomy, steps, depth)
    WORKFLOW = "workflow"  # WHO does it, WHEN to call
    EVIDENCE = "evidence"  # WHY it works (studies, outcomes)
    SAFETY = "safety"  # Complications, contraindications
    EQUIPMENT = "equipment"  # What you need
    LOCAL_PROTOCOL = "local_protocol"  # Hospital-specific


@dataclass
class ClassifiedSnippet:
    """A snippet with its classification result."""

    text: str
    snippet_type: SnippetType
    confidence: float
    source_id: str | None = None


# Pattern definitions for classification
TECHNIQUE_PATTERNS: list[Pattern[str]] = [
    # Anatomical landmarks (Danish)
    re.compile(r"\b(interkostalrum|midtaksillær|anterior|lateral|medial)\b", re.I),
    re.compile(r"\b(nervus|musculus|vena|arteria|n\.|m\.|v\.|a\.)\b", re.I),
    # Angles and measurements
    re.compile(r"\b\d+\s*(grader?|°|cm|mm)\b", re.I),
    re.compile(r"\b(vinkel|dybde|afstand|længde)\b", re.I),
    # Procedural actions
    re.compile(r"\b(indsæt|avancér|punktér|aspirér|introducer)\b", re.I),
    re.compile(r"\b(palpér|identificér|marker|desinficér)\b", re.I),
    # Technique verbs
    re.compile(r"\b(rotér|træk|skub|hold|fiksér)\b", re.I),
]

WORKFLOW_PATTERNS: list[Pattern[str]] = [
    # Phone/contact
    re.compile(r"\b(ring|tlf|telefon|kontakt)\b", re.I),
    re.compile(r"\b(bagvagt|forvagt|anæstesi.*tilkald)\b", re.I),
    # Role/team
    re.compile(r"\b(rollefordeling|teamleder|assistent)\b", re.I),
    re.compile(r"\b(aftal|koordinér|delegér)\b", re.I),
    # Local protocol references
    re.compile(r"\b(lokal\s*(retningslinje|instruks|protokol))\b", re.I),
    re.compile(r"\b(afdelingens|hospitalets|afsnittets)\b", re.I),
    # Time/scheduling
    re.compile(r"\b(dagtid|vagttid|weekend)\b", re.I),
]

SAFETY_PATTERNS: list[Pattern[str]] = [
    # Complications
    re.compile(r"\b(komplikation|pneumothorax|blødning|infektion)\b", re.I),
    re.compile(r"\b(risiko|fare|skade)\b", re.I),
    # Warnings
    re.compile(r"\b(advarsel|obs|pas på|undgå)\b", re.I),
    re.compile(r"\b(kontraindikation|forsigtighed)\b", re.I),
    # Stop criteria
    re.compile(r"\b(stop|afbryd|eskalér)\b", re.I),
]

EQUIPMENT_PATTERNS: list[Pattern[str]] = [
    # Equipment lists
    re.compile(r"\b(udstyr|materiale|instrument)\b", re.I),
    # Specific items
    re.compile(r"\b(kanyle|kateter|nål|sprøjte|handske)\b", re.I),
    re.compile(r"\b(\d+G|\d+\s*gauge|french)\b", re.I),
    # Sterile
    re.compile(r"\b(steril|desinfekt|aseptisk)\b", re.I),
]

EVIDENCE_PATTERNS: list[Pattern[str]] = [
    # Study references
    re.compile(r"\b(studie|forskning|evidens|meta-analyse)\b", re.I),
    re.compile(r"\b(randomiseret|RCT|kohort)\b", re.I),
    # Author/year patterns
    re.compile(r"\b[A-Z][a-z]+\s+et\s+al\.\s*\(\d{4}\)", re.I),
    # Guidelines
    re.compile(r"\b(guideline|anbefaling|retningslinje)\b", re.I),
    re.compile(r"\b(British|European|American|World)\s+\w+\s+(Society|Association|Organization)", re.I),
    # Statistics
    re.compile(r"\b(signifikant|p\s*[<>=]|OR|RR|HR)\b", re.I),
]


class SnippetClassifier:
    """Classifies medical procedure snippets by content type."""

    def __init__(self) -> None:
        self._pattern_map: dict[SnippetType, list[Pattern[str]]] = {
            SnippetType.TECHNIQUE: TECHNIQUE_PATTERNS,
            SnippetType.WORKFLOW: WORKFLOW_PATTERNS,
            SnippetType.SAFETY: SAFETY_PATTERNS,
            SnippetType.EQUIPMENT: EQUIPMENT_PATTERNS,
            SnippetType.EVIDENCE: EVIDENCE_PATTERNS,
        }

    def classify(self, text: str, source_id: str | None = None) -> ClassifiedSnippet:
        """Classify a single snippet.

        Args:
            text: The snippet text to classify
            source_id: Optional source identifier

        Returns:
            ClassifiedSnippet with type and confidence
        """
        scores: dict[SnippetType, int] = {}

        for snippet_type, patterns in self._pattern_map.items():
            score = 0
            for pattern in patterns:
                matches = pattern.findall(text)
                score += len(matches)
            scores[snippet_type] = score

        # Find the type with highest score
        total_matches = sum(scores.values())
        if total_matches == 0:
            # Default to TECHNIQUE if no patterns match
            return ClassifiedSnippet(
                text=text,
                snippet_type=SnippetType.TECHNIQUE,
                confidence=0.5,
                source_id=source_id,
            )

        best_type = max(scores, key=lambda t: scores[t])
        confidence = scores[best_type] / max(total_matches, 1)

        # Boost confidence for strong matches
        if scores[best_type] >= 3:
            confidence = min(confidence + 0.2, 0.99)

        return ClassifiedSnippet(
            text=text,
            snippet_type=best_type,
            confidence=confidence,
            source_id=source_id,
        )

    def classify_batch(
        self, texts: list[str], source_ids: list[str] | None = None
    ) -> list[ClassifiedSnippet]:
        """Classify multiple snippets.

        Args:
            texts: List of snippet texts
            source_ids: Optional list of source identifiers (must match texts length)

        Returns:
            List of ClassifiedSnippet objects
        """
        if source_ids is None:
            source_ids = [None] * len(texts)

        return [
            self.classify(text, source_id)
            for text, source_id in zip(texts, source_ids)
        ]

    def filter_by_type(
        self, snippets: list[ClassifiedSnippet], snippet_type: SnippetType
    ) -> list[ClassifiedSnippet]:
        """Filter snippets by type.

        Args:
            snippets: List of classified snippets
            snippet_type: Type to filter for

        Returns:
            List of snippets matching the type
        """
        return [s for s in snippets if s.snippet_type == snippet_type]
