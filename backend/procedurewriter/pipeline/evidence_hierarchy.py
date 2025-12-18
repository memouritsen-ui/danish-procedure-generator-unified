"""
Evidence Hierarchy Module

Classifies sources according to the Danish evidence hierarchy,
prioritizing Danish and Nordic sources for clinical relevance.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from procedurewriter.config_store import load_yaml


@dataclass(frozen=True)
class EvidenceLevel:
    """Classification result for a source."""

    level_id: str
    priority: int
    badge: str
    badge_color: str
    description: str


# Default evidence levels (used if config file is missing)
_DEFAULT_LEVELS: dict[str, dict[str, Any]] = {
    "danish_guideline": {
        "priority": 1000,
        "badge": "DK Guideline",
        "badge_color": "#22c55e",
        "description": "Dansk national retningslinje",
    },
    "nordic_guideline": {
        "priority": 900,
        "badge": "Nordic",
        "badge_color": "#3b82f6",
        "description": "Nordisk retningslinje",
    },
    "international_guideline": {
        "priority": 800,
        "badge": "Intl Guideline",
        "badge_color": "#06b6d4",
        "description": "International retningslinje",
    },
    "systematic_review": {
        "priority": 700,
        "badge": "Syst Review",
        "badge_color": "#f59e0b",
        "description": "Systematisk review",
    },
    "practice_guideline": {
        "priority": 650,
        "badge": "Practice GL",
        "badge_color": "#84cc16",
        "description": "Practice guideline",
    },
    "rct": {
        "priority": 500,
        "badge": "RCT",
        "badge_color": "#ec4899",
        "description": "Randomiseret kontrolleret forsøg",
    },
    "unclassified": {
        "priority": 50,
        "badge": "Kilde",
        "badge_color": "#d1d5db",
        "description": "Uklassificeret kilde",
    },
}


class EvidenceHierarchy:
    """
    Classifies sources according to evidence hierarchy.

    Usage:
        hierarchy = EvidenceHierarchy.from_config(config_path)
        level = hierarchy.classify_source(url="https://sst.dk/...", kind="guideline_url")
        print(f"Priority: {level.priority}, Badge: {level.badge}")
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = config or {}
        self._levels = self._config.get("evidence_levels", _DEFAULT_LEVELS)
        self._library_rules = self._config.get("library_source_rules", {})

    @classmethod
    def from_config(cls, config_path: Path | str | None) -> EvidenceHierarchy:
        """Load hierarchy from YAML config file."""
        if config_path is None:
            return cls(None)
        path = Path(config_path) if isinstance(config_path, str) else config_path
        if not path.exists():
            return cls(None)
        config = load_yaml(path)
        return cls(config if isinstance(config, dict) else None)

    def classify_source(
        self,
        *,
        url: str | None = None,
        kind: str | None = None,
        title: str | None = None,
        publication_types: list[str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> EvidenceLevel:
        """
        Classify a source and return its evidence level.

        Args:
            url: Source URL (for URL-based classification)
            kind: Source kind (e.g., "pubmed", "guideline_url", "library")
            title: Source title (for keyword-based classification)
            publication_types: PubMed publication types
            extra: Additional metadata

        Returns:
            EvidenceLevel with priority, badge, and description
        """
        # Try URL-based classification first
        if url:
            level = self._classify_by_url(url)
            if level:
                return level

        # Try PubMed publication types
        if publication_types:
            level = self._classify_by_pubmed_types(publication_types)
            if level:
                return level

        # Try library source rules (title/keyword matching)
        if title and kind == "library":
            level = self._classify_library_source(title)
            if level:
                return level

        # Default to unclassified
        return self._make_level("unclassified")

    def _classify_by_url(self, url: str) -> EvidenceLevel | None:
        """Classify source by URL pattern matching."""
        url_lower = url.lower()
        for level_id, level_config in self._levels.items():
            if not isinstance(level_config, dict):
                continue
            patterns = level_config.get("url_patterns", [])
            if not patterns:
                continue
            for pattern in patterns:
                if pattern.lower() in url_lower:
                    return self._make_level(level_id)
        return None

    def _classify_by_pubmed_types(self, publication_types: list[str]) -> EvidenceLevel | None:
        """Classify source by PubMed publication types."""
        types_lower = {t.strip().lower() for t in publication_types if t and t.strip()}
        if not types_lower:
            return None

        # Check each level for matching pubmed_types
        for level_id, level_config in self._levels.items():
            if not isinstance(level_config, dict):
                continue
            pubmed_types = level_config.get("pubmed_types", [])
            if not pubmed_types:
                continue
            for pt in pubmed_types:
                if pt.lower() in types_lower:
                    return self._make_level(level_id)

        return None

    def _classify_library_source(self, title: str) -> EvidenceLevel | None:
        """Classify library source by title keywords."""
        title_lower = title.lower()

        # Check for Danish keywords
        danish_keywords = self._library_rules.get("danish_keywords", [])
        for kw in danish_keywords:
            if kw.lower() in title_lower:
                return self._make_level("danish_guideline")

        # Check for Nordic keywords
        nordic_keywords = self._library_rules.get("nordic_keywords", [])
        for kw in nordic_keywords:
            if kw.lower() in title_lower:
                return self._make_level("nordic_guideline")

        return None

    def _make_level(self, level_id: str) -> EvidenceLevel:
        """Create an EvidenceLevel from level ID."""
        config = self._levels.get(level_id, _DEFAULT_LEVELS.get(level_id, _DEFAULT_LEVELS["unclassified"]))
        return EvidenceLevel(
            level_id=level_id,
            priority=config.get("priority", 50),
            badge=config.get("badge", "Kilde"),
            badge_color=config.get("badge_color", "#d1d5db"),
            description=config.get("description", "Uklassificeret kilde"),
        )

    def get_priority_boost(
        self,
        *,
        url: str | None = None,
        kind: str | None = None,
        title: str | None = None,
        publication_types: list[str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> int:
        """
        Get priority boost score for a source.

        This can be added to existing relevance scores to prioritize
        Danish/Nordic sources in search results.
        """
        level = self.classify_source(
            url=url,
            kind=kind,
            title=title,
            publication_types=publication_types,
            extra=extra,
        )
        return level.priority

    def get_all_levels(self) -> list[EvidenceLevel]:
        """Get all configured evidence levels, sorted by priority (highest first)."""
        levels = []
        for level_id in self._levels:
            levels.append(self._make_level(level_id))
        levels.sort(key=lambda x: x.priority, reverse=True)
        return levels


# Global instance (lazy loaded)
_hierarchy: EvidenceHierarchy | None = None


def get_evidence_hierarchy(config_path: Path | str | None = None) -> EvidenceHierarchy:
    """Get or create the global evidence hierarchy instance."""
    global _hierarchy
    if _hierarchy is None:
        _hierarchy = EvidenceHierarchy.from_config(config_path)
    return _hierarchy


def classify_source(
    *,
    url: str | None = None,
    kind: str | None = None,
    title: str | None = None,
    publication_types: list[str] | None = None,
    extra: dict[str, Any] | None = None,
    config_path: Path | str | None = None,
) -> EvidenceLevel:
    """
    Convenience function to classify a source.

    Args:
        url: Source URL
        kind: Source kind
        title: Source title
        publication_types: PubMed publication types
        extra: Additional metadata
        config_path: Path to evidence_hierarchy.yaml

    Returns:
        EvidenceLevel with classification result
    """
    hierarchy = get_evidence_hierarchy(config_path)
    return hierarchy.classify_source(
        url=url,
        kind=kind,
        title=title,
        publication_types=publication_types,
        extra=extra,
    )
