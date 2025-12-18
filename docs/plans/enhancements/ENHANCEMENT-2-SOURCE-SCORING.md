# Enhancement 2: Source Quality Scoring & Trust Indicators

## Status: NOT STARTED

**Priority**: 2
**Estimated Effort**: 2-3 days
**Dependencies**: None

---

## SESSION START CHECKLIST

Before implementing ANY part of this enhancement, execute:

```
Skill(superpowers:using-superpowers)
Skill(superpowers:test-driven-development)
Skill(superpowers:verification-before-completion)
```

**REMINDER**: NO DUMMY/MOCK IMPLEMENTATIONS. All code must be production-ready.

---

## Problem Statement

Current evidence hierarchy classifies sources by type (Danish Guideline > Nordic > RCT, etc.) but:

1. A 2010 systematic review ranks equal to a 2024 systematic review
2. Users don't see WHY a source was ranked a certain way
3. No visibility into recency, journal quality, or citation impact
4. Trust decisions are opaque to clinicians

---

## Solution Overview

Add multi-factor source scoring that combines:

1. **Evidence Level** (existing) - Publication type classification
2. **Recency Score** (new) - Newer sources ranked higher within same level
3. **Quality Indicators** (new) - Journal reputation, citation count (optional)
4. **Composite Trust Score** (new) - Combined weighted score

Display clear reasoning in UI:
```
Source: Dansk Kardiologisk Selskab - Akut MI vejledning
Trust Score: 95/100
  ├── Evidence Level: DK Guideline (1000 base)
  ├── Recency: 2024 (+10)
  ├── Journal: Official guideline body (+5)
  └── Total: 95/100
```

---

## Technical Specification

### Backend Changes

#### File: `backend/procedurewriter/pipeline/source_scoring.py` (NEW)

```python
"""
Source quality scoring system.

Combines evidence level, recency, and optional quality indicators
to produce a composite trust score.

NO MOCKS - All scoring uses real source metadata.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from procedurewriter.pipeline.evidence_hierarchy import classify_evidence, EvidenceClassification

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

def calculate_recency_score(year: int | None, reference_year: int | None = None) -> tuple[float, str]:
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

    # Abstract presence
    if source.get("abstract"):
        score += 0.05
        reasons.append("Has abstract (+0.05)")

    # Known reputable publishers
    url = source.get("url", "").lower()
    reputable_domains = {
        "sst.dk": 0.2,           # Danish Health Authority
        "sundhed.dk": 0.15,      # Danish health portal
        "dsam.dk": 0.15,         # Danish College of GPs
        "nice.org.uk": 0.15,     # UK NICE
        "who.int": 0.15,         # WHO
        "cochrane.org": 0.2,     # Cochrane Reviews
        "nejm.org": 0.15,        # NEJM
        "thelancet.com": 0.15,   # Lancet
        "bmj.com": 0.1,          # BMJ
    }

    for domain, bonus in reputable_domains.items():
        if domain in url:
            score += bonus
            reasons.append(f"Reputable source: {domain} (+{bonus})")
            break

    # Cap at 1.0
    return min(1.0, score), reasons

def score_source(
    source: dict[str, Any],
    evidence_classification: EvidenceClassification | None = None,
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
    if evidence_classification is None:
        evidence_classification = classify_evidence(
            url=source.get("url"),
            publication_types=source.get("publication_types", []),
            title=source.get("title", ""),
        )

    # Calculate components
    recency_score, recency_reason = calculate_recency_score(year)
    quality_score, quality_reasons = calculate_quality_indicators(source)

    # Normalize evidence priority to 0-1 scale (1000 max)
    evidence_normalized = evidence_classification.priority / 1000.0

    # Calculate composite score (0-100)
    composite = (
        evidence_normalized * 60 +
        recency_score * 25 +
        quality_score * 15
    )

    # Build reasoning
    reasoning = [
        f"Evidence level: {evidence_classification.badge} ({evidence_classification.priority} priority, {evidence_normalized*60:.1f} pts)",
        f"Recency: {recency_reason} ({recency_score*25:.1f} pts)",
    ]
    for qr in quality_reasons:
        reasoning.append(f"Quality: {qr}")
    reasoning.append(f"Total: {composite:.1f}/100")

    return SourceScore(
        source_id=source_id,
        evidence_level=evidence_classification.level_id,
        evidence_priority=evidence_classification.priority,
        recency_score=recency_score,
        recency_year=year,
        quality_score=quality_score,
        composite_score=composite,
        reasoning=reasoning,
    )

def rank_sources(sources: list[dict[str, Any]]) -> list[SourceScore]:
    """
    Score and rank all sources by composite trust score.

    Returns list of SourceScore sorted by composite_score descending.
    """
    scored = [score_source(s) for s in sources]
    return sorted(scored, key=lambda x: x.composite_score, reverse=True)
```

#### File: `backend/procedurewriter/pipeline/run.py` (MODIFY)

Add source scoring to pipeline:

```python
from procedurewriter.pipeline.source_scoring import rank_sources, SourceScore

def run_pipeline(...):
    # After collecting sources, score them
    scored_sources = rank_sources(sources)

    # Store scores in manifest
    manifest["source_scores"] = [
        {
            "source_id": s.source_id,
            "composite_score": s.composite_score,
            "evidence_level": s.evidence_level,
            "recency_year": s.recency_year,
            "reasoning": s.reasoning,
        }
        for s in scored_sources
    ]

    # Use ranked order for retrieval preference
    source_priority_order = [s.source_id for s in scored_sources]
```

#### File: `backend/procedurewriter/main.py` (MODIFY)

Add source scores to API response:

```python
@app.get("/api/runs/{run_id}/sources")
def api_sources(run_id: str) -> dict:
    # ... existing code ...

    # Load source scores from manifest
    manifest = load_manifest(run_id)
    score_map = {
        s["source_id"]: s
        for s in manifest.get("source_scores", [])
    }

    # Enrich sources with scores
    for source in sources:
        score_data = score_map.get(source["source_id"], {})
        source["trust_score"] = score_data.get("composite_score")
        source["score_reasoning"] = score_data.get("reasoning", [])

    return {"sources": sources}
```

### Frontend Changes

#### File: `frontend/src/components/SourceCard.tsx` (NEW)

```typescript
interface SourceScore {
  composite_score: number;
  evidence_level: string;
  recency_year: number | null;
  reasoning: string[];
}

interface SourceCardProps {
  source: SourceRecord;
  trustScore?: number;
  scoreReasoning?: string[];
  expanded?: boolean;
  onToggle?: () => void;
}

export function SourceCard({
  source,
  trustScore,
  scoreReasoning,
  expanded,
  onToggle,
}: SourceCardProps) {
  const scoreColor =
    trustScore === undefined ? "#888" :
    trustScore >= 80 ? "#22c55e" :
    trustScore >= 60 ? "#fbbf24" :
    "#f87171";

  return (
    <div className="source-card">
      <div className="source-header" onClick={onToggle}>
        <div className="source-title">
          <strong>{source.source_id}</strong>
          <span className="muted">({source.kind})</span>
        </div>

        {trustScore !== undefined && (
          <div
            className="trust-score"
            style={{ color: scoreColor }}
            title="Trust Score"
          >
            {trustScore.toFixed(0)}/100
          </div>
        )}
      </div>

      <div className="source-meta muted">
        {source.title ?? source.url ?? source.pmid ?? "-"}
      </div>

      {expanded && scoreReasoning && (
        <div className="score-breakdown">
          <strong>Score Breakdown:</strong>
          <ul>
            {scoreReasoning.map((reason, i) => (
              <li key={i}>{reason}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
```

#### File: `frontend/src/pages/RunPage.tsx` (MODIFY)

Display trust scores:

```typescript
// Update source rendering to use SourceCard
{sources.map((s) => (
  <SourceCard
    key={s.source_id}
    source={s}
    trustScore={s.trust_score}
    scoreReasoning={s.score_reasoning}
  />
))}
```

#### File: `frontend/src/api.ts` (MODIFY)

Update type definitions:

```typescript
export interface SourceRecord {
  source_id: string;
  kind: string;
  url?: string;
  title?: string;
  pmid?: string;
  doi?: string;
  year?: number;
  raw_sha256: string;
  normalized_sha256: string;
  extra?: Record<string, unknown>;
  // New fields
  trust_score?: number;
  score_reasoning?: string[];
}
```

---

## Configuration

#### File: `config/source_scoring.yaml` (NEW)

```yaml
# Source scoring configuration
# Weights must sum to 100

weights:
  evidence_level: 60
  recency: 25
  quality_indicators: 15

recency:
  # Years to full decay
  half_life_years: 10
  # Minimum score for very old sources
  minimum_score: 0.25

quality_indicators:
  # Bonus for having DOI
  doi_bonus: 0.1
  # Bonus for having abstract
  abstract_bonus: 0.05

  # Domain reputation bonuses
  reputable_domains:
    sst.dk: 0.2
    sundhed.dk: 0.15
    dsam.dk: 0.15
    nice.org.uk: 0.15
    who.int: 0.15
    cochrane.org: 0.2
    nejm.org: 0.15
    thelancet.com: 0.15
    bmj.com: 0.1
```

---

## Database Changes

**No schema changes required.** Scores are stored in run manifest JSON.

---

## Test Requirements

### Backend Tests

#### File: `backend/tests/test_source_scoring.py` (NEW)

```python
"""
Source Scoring Tests

IMPORTANT: Tests use REAL source metadata.
NO MOCKS for external data - test with actual PubMed records.
"""
import pytest
from datetime import datetime
from procedurewriter.pipeline.source_scoring import (
    calculate_recency_score,
    calculate_quality_indicators,
    score_source,
    rank_sources,
)

class TestRecencyScoring:
    """Test recency score calculation."""

    def test_current_year_gets_max_score(self):
        """Current year sources get 1.0 recency score."""
        current_year = datetime.now().year
        score, reason = calculate_recency_score(current_year)
        assert score == 1.0
        assert "Current year" in reason

    def test_one_year_old_high_score(self):
        """One year old sources get 0.95."""
        score, _ = calculate_recency_score(datetime.now().year - 1)
        assert score == 0.95

    def test_five_year_old_moderate_score(self):
        """Five year old sources get ~0.75."""
        score, _ = calculate_recency_score(datetime.now().year - 5)
        assert 0.7 <= score <= 0.8

    def test_ten_year_old_lower_score(self):
        """Ten year old sources get ~0.50."""
        score, _ = calculate_recency_score(datetime.now().year - 10)
        assert 0.45 <= score <= 0.55

    def test_unknown_year_default(self):
        """Unknown year gets default 0.5."""
        score, reason = calculate_recency_score(None)
        assert score == 0.5
        assert "unknown" in reason.lower()

    def test_very_old_source_minimum(self):
        """Very old sources get minimum score."""
        score, _ = calculate_recency_score(1990)
        assert score >= 0.25


class TestQualityIndicators:
    """Test quality indicator calculation."""

    def test_doi_adds_bonus(self):
        """DOI presence adds score."""
        source_with_doi = {"doi": "10.1234/test"}
        source_without = {}

        score_with, reasons_with = calculate_quality_indicators(source_with_doi)
        score_without, _ = calculate_quality_indicators(source_without)

        assert score_with > score_without
        assert any("DOI" in r for r in reasons_with)

    def test_reputable_domain_bonus(self):
        """Known reputable domains get bonus."""
        source = {"url": "https://sst.dk/guidelines/test"}
        score, reasons = calculate_quality_indicators(source)

        assert score > 0.5  # Base score
        assert any("sst.dk" in r for r in reasons)

    def test_score_capped_at_one(self):
        """Quality score never exceeds 1.0."""
        source = {
            "doi": "10.1234/test",
            "abstract": "Test abstract",
            "url": "https://cochrane.org/review",
        }
        score, _ = calculate_quality_indicators(source)
        assert score <= 1.0


class TestCompositeScoring:
    """Test full source scoring."""

    def test_high_quality_source_high_score(self):
        """High quality recent Danish guideline scores high."""
        source = {
            "source_id": "SRC001",
            "url": "https://sst.dk/guidelines/test",
            "year": datetime.now().year,
            "doi": "10.1234/test",
            "abstract": "Test",
        }
        result = score_source(source)

        assert result.composite_score >= 80
        assert len(result.reasoning) > 0

    def test_old_case_report_low_score(self):
        """Old case report scores lower."""
        source = {
            "source_id": "SRC002",
            "url": "https://unknown-journal.com",
            "year": 2005,
            "publication_types": ["case report"],
        }
        result = score_source(source)

        assert result.composite_score < 50

    def test_ranking_orders_correctly(self):
        """Ranking puts high scores first."""
        sources = [
            {"source_id": "low", "year": 2000},
            {"source_id": "high", "url": "https://sst.dk", "year": 2024},
            {"source_id": "mid", "year": 2020},
        ]
        ranked = rank_sources(sources)

        assert ranked[0].source_id == "high"
        assert ranked[-1].source_id == "low"


class TestIntegrationWithRealPubMed:
    """Integration tests with real PubMed data."""

    @pytest.mark.integration
    def test_score_real_pubmed_article(self):
        """Score a real PubMed article."""
        # This would use a real PubMed fetch in integration test
        # Example: PMID 12345678
        pass  # Implement when running integration tests
```

---

## Implementation Checklist

### Phase 1: Core Scoring Logic (Day 1)

- [ ] Create `backend/procedurewriter/pipeline/source_scoring.py`
- [ ] Implement `calculate_recency_score()`
- [ ] Implement `calculate_quality_indicators()`
- [ ] Implement `score_source()` composite scoring
- [ ] Implement `rank_sources()` ranking function
- [ ] Write unit tests for all functions
- [ ] Run tests: `pytest backend/tests/test_source_scoring.py -v`

### Phase 2: Pipeline Integration (Day 1-2)

- [ ] Modify `backend/procedurewriter/pipeline/run.py`
- [ ] Add source scoring after collection
- [ ] Store scores in manifest
- [ ] Verify scores appear in run output
- [ ] Test with real procedure generation

### Phase 3: API Updates (Day 2)

- [ ] Modify `/api/runs/{run_id}/sources` endpoint
- [ ] Add trust_score and score_reasoning fields
- [ ] Update TypeScript types in `api.ts`
- [ ] Test API response includes scores

### Phase 4: Frontend Display (Day 2-3)

- [ ] Create `frontend/src/components/SourceCard.tsx`
- [ ] Modify `RunPage.tsx` to use SourceCard
- [ ] Add score visualization (color coding)
- [ ] Add expandable reasoning breakdown
- [ ] Style score display

### Phase 5: Configuration & Polish (Day 3)

- [ ] Create `config/source_scoring.yaml`
- [ ] Make weights configurable
- [ ] Add reputable domains to config
- [ ] Documentation for customization
- [ ] Run full test suite
- [ ] Manual E2E testing

---

## Current Status

**Status**: NOT STARTED

**Last Updated**: 2024-12-18

**Checkpoints Completed**:
- [ ] Phase 1: Core Scoring Logic
- [ ] Phase 2: Pipeline Integration
- [ ] Phase 3: API Updates
- [ ] Phase 4: Frontend Display
- [ ] Phase 5: Configuration & Polish

**Blockers**: None

**Notes**: Ready to begin implementation.

---

## Session Handoff Notes

When continuing this enhancement in a new session:

1. Read this document first
2. Check "Current Status" above
3. Load skills: `Skill(superpowers:test-driven-development)`
4. Run existing tests to verify baseline: `pytest`
5. Continue from last incomplete checkbox

**REMEMBER**: No dummy/mock implementations. All scoring uses real source metadata.
