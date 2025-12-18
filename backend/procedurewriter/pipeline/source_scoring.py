"""
Source quality scoring system.

Combines evidence level, recency, content quality, and relevance
to produce a composite trust score.

Multi-signal scoring approach:
- Provenance (evidence hierarchy): 35%
- Content quality (structure, refs): 25%
- Recency: 20%
- Relevance (to procedure topic): 20%

NO MOCKS - All scoring uses real source metadata.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
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


def assess_content_quality(content: str | None) -> tuple[float, list[str]]:
    """
    Assess content quality based on structural signals.

    Looks for indicators of professional, well-structured content:
    - Has methodology/methods section
    - Has references/bibliography
    - Professional length (not too short)
    - Contains clinical/medical terminology
    - Has numbered lists or tables

    Returns (score 0-1, list of reasoning strings)
    """
    if not content:
        return 0.5, ["No content available (default score)"]

    score = 0.0
    reasons: list[str] = []
    content_lower = content.lower()

    # Has structured sections (methods, background, etc.)
    structure_keywords = [
        "methods", "metode", "metodologi",
        "baggrund", "background", "introduction", "indledning",
        "results", "resultater", "diskussion", "discussion",
        "konklusion", "conclusion",
    ]
    if any(kw in content_lower for kw in structure_keywords):
        score += 0.2
        reasons.append("Has structured sections (+0.2)")

    # Has references/bibliography
    reference_keywords = ["references", "litteratur", "kilder", "bibliography", "citations"]
    if any(kw in content_lower for kw in reference_keywords):
        score += 0.2
        reasons.append("Has references (+0.2)")

    # Professional length (not too short, not just a paragraph)
    if 500 < len(content) < 100000:
        score += 0.2
        reasons.append("Appropriate length (+0.2)")
    elif len(content) >= 100000:
        score += 0.15
        reasons.append("Very long document (+0.15)")
    else:
        reasons.append("Short content (no bonus)")

    # Contains clinical/medical terminology
    medical_terms = [
        "behandling", "diagnose", "patient", "dosis", "mg", "ml",
        "indikation", "kontraindikation", "bivirkninger", "symptom",
        "klinisk", "evidens", "anbefaling", "guideline", "retningslinje",
    ]
    term_count = sum(1 for t in medical_terms if t in content_lower)
    if term_count >= 5:
        score += 0.2
        reasons.append(f"Rich medical terminology ({term_count} terms, +0.2)")
    elif term_count >= 3:
        score += 0.1
        reasons.append(f"Some medical terminology ({term_count} terms, +0.1)")

    # Has numbered lists or tables (suggests structured content)
    if re.search(r'\d+\.\s+\w+', content) or '|' in content or re.search(r'^\s*[-•]\s+', content, re.MULTILINE):
        score += 0.2
        reasons.append("Has lists/tables (+0.2)")

    # Cap at 1.0
    return min(1.0, score), reasons


def assess_relevance(
    source: dict[str, Any],
    procedure_topic: str | None,
    content: str | None = None,
) -> tuple[float, list[str]]:
    """
    Assess how relevant the source is to the procedure topic.

    Uses keyword overlap between topic and source title/content.

    Returns (score 0-1, list of reasoning strings)
    """
    if not procedure_topic:
        return 0.5, ["No topic provided (default score)"]

    topic_words = set(procedure_topic.lower().split())
    # Remove common Danish stop words
    stop_words = {"og", "i", "på", "til", "med", "af", "for", "ved", "en", "et", "den", "det"}
    topic_words = topic_words - stop_words

    if not topic_words:
        return 0.5, ["No significant topic words (default score)"]

    score = 0.0
    reasons: list[str] = []

    # Check title match
    title = (source.get("title") or "").lower()
    title_matches = sum(1 for w in topic_words if w in title)
    if title_matches > 0:
        title_score = min(0.5, title_matches / len(topic_words) * 0.5)
        score += title_score
        reasons.append(f"Title matches ({title_matches} words, +{title_score:.2f})")

    # Check content match (if available)
    if content:
        content_lower = content.lower()
        content_matches = sum(1 for w in topic_words if w in content_lower)
        if content_matches > 0:
            content_score = min(0.5, content_matches / len(topic_words) * 0.5)
            score += content_score
            reasons.append(f"Content matches ({content_matches} words, +{content_score:.2f})")

    if not reasons:
        reasons.append("No topic matches found")

    return min(1.0, score), reasons


def read_source_content(normalized_path: str | None) -> str | None:
    """Read source content from file if available."""
    if not normalized_path:
        return None
    try:
        path = Path(normalized_path)
        if path.exists() and path.is_file():
            return path.read_text(encoding="utf-8", errors="replace")[:50000]  # Limit to 50KB
    except (OSError, UnicodeDecodeError):
        pass
    return None


def score_source(
    source: dict[str, Any],
    evidence_level: EvidenceLevel | None = None,
    procedure_topic: str | None = None,
) -> SourceScore:
    """
    Calculate composite trust score for a source.

    Multi-signal weighting:
    - Provenance (evidence hierarchy): 35%
    - Content quality: 25%
    - Recency: 20%
    - Relevance to topic: 20%

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

    # Try to read source content for content analysis
    normalized_path = source.get("normalized_path")
    content = read_source_content(normalized_path)

    # Calculate components
    recency_score, recency_reason = calculate_recency_score(year)
    metadata_quality, metadata_reasons = calculate_quality_indicators(source)
    content_quality, content_reasons = assess_content_quality(content)
    relevance_score, relevance_reasons = assess_relevance(source, procedure_topic, content)

    # Combined quality score (average of metadata and content quality)
    combined_quality = (metadata_quality + content_quality) / 2

    # Normalize evidence priority to 0-1 scale (1000 max)
    provenance = min(1.0, evidence_level.priority / 1000.0)

    # Calculate composite score (0-100) with new balanced weights
    composite = (
        provenance * 35 +          # Provenance from evidence hierarchy
        combined_quality * 25 +     # Content + metadata quality
        recency_score * 20 +        # Recency
        relevance_score * 20        # Relevance to topic
    )

    # Build reasoning
    reasoning = [
        f"Provenance: {evidence_level.badge} (priority {evidence_level.priority}, {provenance*35:.1f} pts)",
        f"Recency: {recency_reason} ({recency_score*20:.1f} pts)",
    ]
    for mr in metadata_reasons:
        reasoning.append(f"Metadata: {mr}")
    for cr in content_reasons:
        reasoning.append(f"Content: {cr}")
    reasoning.append(f"Combined quality: {combined_quality:.2f} ({combined_quality*25:.1f} pts)")
    for rr in relevance_reasons:
        reasoning.append(f"Relevance: {rr}")
    reasoning.append(f"Relevance score: {relevance_score:.2f} ({relevance_score*20:.1f} pts)")
    reasoning.append(f"Total: {composite:.1f}/100")

    return SourceScore(
        source_id=source_id,
        evidence_level=evidence_level.level_id,
        evidence_priority=evidence_level.priority,
        recency_score=recency_score,
        recency_year=year,
        quality_score=combined_quality,
        composite_score=round(composite, 1),
        reasoning=reasoning,
    )


def rank_sources(
    sources: list[dict[str, Any]],
    procedure_topic: str | None = None,
) -> list[SourceScore]:
    """
    Score and rank all sources by composite trust score.

    Args:
        sources: List of source dictionaries
        procedure_topic: Optional procedure name for relevance scoring

    Returns list of SourceScore sorted by composite_score descending.
    """
    scored = [score_source(s, procedure_topic=procedure_topic) for s in sources]
    return sorted(scored, key=lambda x: x.composite_score, reverse=True)


def get_trust_level(score: float) -> str:
    """
    Map composite score to Danish trust level label.

    Thresholds:
    - >= 70: Høj tillid (High trust)
    - >= 45: Middel tillid (Medium trust)
    - < 45: Lav tillid (Low trust)
    """
    if score >= 70:
        return "Høj tillid"
    elif score >= 45:
        return "Middel tillid"
    else:
        return "Lav tillid"


def get_trust_color(score: float) -> str:
    """
    Map composite score to CSS color for UI display.
    """
    if score >= 70:
        return "#22c55e"  # green
    elif score >= 45:
        return "#f59e0b"  # amber
    else:
        return "#ef4444"  # red


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
            "normalized_path": getattr(source, "normalized_path", None),
        }

    return {}
