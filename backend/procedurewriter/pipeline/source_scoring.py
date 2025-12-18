"""
Source quality scoring system.

Combines evidence level, recency, and optional quality indicators
to produce a composite trust score.

NO MOCKS - All scoring uses real source metadata.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from procedurewriter.pipeline.evidence_hierarchy import EvidenceLevel, classify_source


@dataclass
class SourceScore:
    """Composite source quality score."""

    source_id: str
    evidence_level: str
    evidence_priority: int
    recency_score: float  # 0-1
    recency_year: int | None
    quality_score: float  # 0-1 (optional factors)
    composite_score: float  # 0-100
    reasoning: list[str]  # Human-readable explanations


def calculate_recency_score(
    year: int | None, reference_year: int | None = None
) -> tuple[float, str]:
    """
    Calculate recency score based on publication year.

    Scoring:
    - Current year: 1.0
    - 1 year old: 0.95
    - 2 years old: 0.90
    - 5 years old: 0.75
    - 10 years old: 0.50
    - 20+ years old: 0.25

    Returns (score, reasoning)
    """
    if year is None:
        return 0.5, "Year unknown (default score)"

    ref_year = reference_year or datetime.now().year
    age = ref_year - year

    if age <= 0:
        return 1.0, f"Current year ({year})"
    elif age <= 1:
        return 0.95, f"Recent ({year}, {age} year old)"
    elif age <= 2:
        return 0.90, f"Recent ({year}, {age} years old)"
    elif age <= 5:
        score = 0.90 - (age - 2) * 0.05
        return score, f"Moderately recent ({year}, {age} years old)"
    elif age <= 10:
        score = 0.75 - (age - 5) * 0.05
        return score, f"Older source ({year}, {age} years old)"
    else:
        score = max(0.25, 0.50 - (age - 10) * 0.025)
        return score, f"Historical source ({year}, {age} years old)"


def calculate_quality_indicators(source: dict[str, Any]) -> tuple[float, list[str]]:
    """
    Calculate quality indicators from source metadata.

    Factors considered:
    - Journal/publisher reputation (from known list)
    - DOI presence (indicates formal publication)
    - Abstract presence (indicates indexed source)
    - Full text availability

    Returns (score 0-1, list of reasoning strings)
    """
    score = 0.5  # Base score
    reasons: list[str] = []

    # DOI presence
    if source.get("doi"):
        score += 0.1
        reasons.append("Has DOI (+0.1)")

    # Abstract presence (check in extra or direct)
    abstract = source.get("abstract") or (source.get("extra") or {}).get("abstract")
    if abstract:
        score += 0.05
        reasons.append("Has abstract (+0.05)")

    # Known reputable publishers
    url = (source.get("url") or "").lower()
    reputable_domains = {
        "sst.dk": 0.2,  # Danish Health Authority
        "sundhed.dk": 0.15,  # Danish health portal
        "dsam.dk": 0.15,  # Danish College of GPs
        "nice.org.uk": 0.15,  # UK NICE
        "who.int": 0.15,  # WHO
        "cochrane.org": 0.2,  # Cochrane Reviews
        "nejm.org": 0.15,  # NEJM
        "thelancet.com": 0.15,  # Lancet
        "bmj.com": 0.1,  # BMJ
        "regionh.dk": 0.15,  # Region Hovedstaden
        "regionsjaelland.dk": 0.15,  # Region Sjælland
        "rm.dk": 0.15,  # Region Midtjylland
        "rsyd.dk": 0.15,  # Region Syddanmark
        "rn.dk": 0.15,  # Region Nordjylland
    }

    for domain, bonus in reputable_domains.items():
        if domain in url:
            score += bonus
            reasons.append(f"Reputable source: {domain} (+{bonus})")
            break

    # Source kind bonuses
    kind = source.get("kind", "").lower()
    if kind == "danish_guideline":
        score += 0.1
        reasons.append("Danish guideline source (+0.1)")
    elif kind == "pubmed" and source.get("pmid"):
        score += 0.05
        reasons.append("PubMed indexed (+0.05)")

    # Cap at 1.0
    return min(1.0, score), reasons


def score_source(
    source: dict[str, Any],
    evidence_level: EvidenceLevel | None = None,
) -> SourceScore:
    """
    Calculate composite trust score for a source.

    Weighting:
    - Evidence level: 60%
    - Recency: 25%
    - Quality indicators: 15%

    Returns SourceScore with full breakdown.
    """
    source_id = source.get("source_id", "unknown")
    year = source.get("year")

    # Get evidence classification if not provided
    if evidence_level is None:
        # Get publication_types from extra if present
        extra = source.get("extra") or {}
        publication_types = extra.get("publication_types") or source.get(
            "publication_types", []
        )

        evidence_level = classify_source(
            url=source.get("url"),
            publication_types=publication_types,
            title=source.get("title", ""),
            kind=source.get("kind"),
        )

    # Calculate components
    recency_score, recency_reason = calculate_recency_score(year)
    quality_score, quality_reasons = calculate_quality_indicators(source)

    # Normalize evidence priority to 0-1 scale (1000 max)
    evidence_normalized = min(1.0, evidence_level.priority / 1000.0)

    # Calculate composite score (0-100)
    composite = (
        evidence_normalized * 60 + recency_score * 25 + quality_score * 15
    )

    # Build reasoning
    reasoning = [
        f"Evidence level: {evidence_level.badge} (priority {evidence_level.priority}, {evidence_normalized*60:.1f} pts)",
        f"Recency: {recency_reason} ({recency_score*25:.1f} pts)",
    ]
    for qr in quality_reasons:
        reasoning.append(f"Quality: {qr}")
    reasoning.append(f"Total: {composite:.1f}/100")

    return SourceScore(
        source_id=source_id,
        evidence_level=evidence_level.level_id,
        evidence_priority=evidence_level.priority,
        recency_score=recency_score,
        recency_year=year,
        quality_score=quality_score,
        composite_score=round(composite, 1),
        reasoning=reasoning,
    )


def rank_sources(sources: list[dict[str, Any]]) -> list[SourceScore]:
    """
    Score and rank all sources by composite trust score.

    Returns list of SourceScore sorted by composite_score descending.
    """
    scored = [score_source(s) for s in sources]
    return sorted(scored, key=lambda x: x.composite_score, reverse=True)


def source_to_dict(source: Any) -> dict[str, Any]:
    """
    Convert a SourceRecord (dataclass) to dict for scoring.

    Handles both dict inputs and dataclass inputs.
    """
    if isinstance(source, dict):
        return source

    # Assume it's a dataclass with __dict__ or asdict
    if hasattr(source, "__dict__"):
        return {
            "source_id": getattr(source, "source_id", "unknown"),
            "kind": getattr(source, "kind", ""),
            "title": getattr(source, "title", ""),
            "year": getattr(source, "year", None),
            "url": getattr(source, "url", ""),
            "doi": getattr(source, "doi", None),
            "pmid": getattr(source, "pmid", None),
            "extra": getattr(source, "extra", {}),
        }

    return {}
