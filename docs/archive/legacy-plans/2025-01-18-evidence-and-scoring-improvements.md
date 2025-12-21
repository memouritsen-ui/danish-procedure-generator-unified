# Evidence Evaluation & Source Scoring Improvements

**Date:** 2025-01-18
**Status:** Planning Complete, Partially Implemented

## Overview

This document addresses three high-priority issues identified in the exhaustive program review:

1. ✅ **Protocol Validation LLM Parsing Bug** (FIXED)
2. **Evidence Check False Confidence** (PLAN BELOW)
3. **Source Scoring Not Useful** (PLAN BELOW)

---

## Issue 1: Protocol Validation LLM Parsing (FIXED)

### Problem
The protocol validation showed "Validering fejlede - kunne ikke parse LLM-svar" because the JSON parsing logic was fragile and couldn't handle:
- JSON wrapped in markdown code blocks
- JSON preceded by explanatory text
- Various LLM response formatting quirks

### Solution Implemented
Added robust `_extract_json_from_llm_response()` function in `protocols.py` that uses three strategies:
1. Try parsing as pure JSON
2. Extract from markdown code blocks using regex
3. Find balanced JSON object boundaries (handles embedded text)

Also added proper logging of failed responses for debugging.

**Files Modified:** `backend/procedurewriter/protocols.py`

---

## Issue 2: Evidence Check False Confidence

### Problem
The current evidence checking in `citations.py` only validates that:
- Each claim has a citation like `[SRC0001]`
- The citation ID exists in `valid_source_ids`

This produces FALSE POSITIVES because it doesn't verify:
- Whether the cited source actually supports the claim
- Whether the claim accurately represents the source
- Whether the citation is contextually appropriate

**Result:** "Understøttet: 0/58" or similar low scores even when citations look correct.

### Root Cause Analysis

Looking at `citations.py`:
```python
def validate_citations(markdown_text: str, *, valid_source_ids: set[str]) -> None:
    errors: list[str] = []
    for sent in iter_cited_sentences(markdown_text):
        if not sent.citations:
            errors.append(f"Line {sent.line_no}: Missing citation...")
        for cid in sent.citations:
            if cid not in valid_source_ids:
                errors.append(f"Line {sent.line_no}: Unknown source_id {cid!r}...")
```

This only checks syntactic validity, not semantic accuracy.

### Proposed Solution: LLM-Based Evidence Verification

**Architecture:**

```
┌─────────────────────────────────────────────────────────────┐
│                     Evidence Verification                    │
├─────────────────────────────────────────────────────────────┤
│  Input:                                                      │
│    - Claim text (sentence with citation)                    │
│    - Source content (the cited document)                    │
│    - Citation context (surrounding sentences)               │
│                                                              │
│  LLM Prompt:                                                 │
│    "Does this source support this claim?"                   │
│    - FULLY_SUPPORTED: Source directly supports claim        │
│    - PARTIALLY_SUPPORTED: Source partially supports         │
│    - NOT_SUPPORTED: Source doesn't support this claim       │
│    - CONTRADICTED: Source contradicts the claim             │
│                                                              │
│  Output:                                                     │
│    - Support level per citation                              │
│    - Confidence score (0-100)                                │
│    - Explanation (for review)                                │
└─────────────────────────────────────────────────────────────┘
```

### Implementation Plan

#### Step 1: Create New Evidence Verification Module
**File:** `backend/procedurewriter/pipeline/evidence_verifier.py`

```python
@dataclass
class EvidenceVerification:
    claim_text: str
    source_id: str
    support_level: Literal["fully_supported", "partially_supported", "not_supported", "contradicted"]
    confidence: int  # 0-100
    explanation: str  # LLM explanation in Danish
    source_excerpt: str  # Relevant excerpt from source

async def verify_citation(
    claim_text: str,
    source_content: str,
    source_id: str,
    anthropic_client: AsyncAnthropic,
) -> EvidenceVerification:
    """Use LLM to verify if source supports claim."""
    ...

async def verify_all_citations(
    markdown_text: str,
    sources: dict[str, str],  # source_id -> content
    anthropic_client: AsyncAnthropic,
    *,
    max_concurrent: int = 5,
) -> list[EvidenceVerification]:
    """Verify all citations in document concurrently."""
    ...
```

#### Step 2: Integrate Into Pipeline
**File:** `backend/procedurewriter/pipeline/run.py`

Add verification step after writer completes:
```python
# After writer produces markdown with citations
if settings.verify_evidence and anthropic_client:
    verifications = await verify_all_citations(
        procedure_md,
        {s.source_id: s.content for s in sources},
        anthropic_client,
    )
    # Store verification results with run
```

#### Step 3: Add API Endpoint
**File:** `backend/procedurewriter/main.py`

```python
@app.get("/api/runs/{run_id}/evidence-verification")
async def get_evidence_verification(run_id: str):
    """Get detailed evidence verification for a run."""
    ...
```

#### Step 4: Update Frontend
**File:** `frontend/src/pages/RunPage.tsx`

Replace simple "Understøttet: X/Y" with:
- Expandable list of claims
- Color-coded support levels
- Click to see LLM explanation
- Show relevant source excerpt

### Cost Considerations

Using Claude Haiku for verification:
- ~500 tokens per verification (claim + source excerpt + response)
- ~$0.0005 per verification
- For 60 citations: ~$0.03 per run

This is acceptable given the value of accurate evidence scores.

### Fallback Strategy

If LLM verification fails or is too expensive:
1. Use keyword matching as baseline
2. Check if source keywords appear in claim
3. Return "unverified" status rather than false confidence

---

## Issue 3: Source Scoring Not Useful

### Problem
All sources show "Lav tillid" with scores of 27-38/100.

### Root Cause Analysis

Looking at `source_scoring.py`:
```python
def score_source(...) -> SourceScore:
    # Normalize evidence priority to 0-1 scale (1000 max)
    evidence_normalized = min(1.0, evidence_level.priority / 1000.0)
    # Calculate composite score (0-100)
    composite = (
        evidence_normalized * 60 +  # 60% weight
        recency_score * 25 +        # 25% weight
        quality_score * 15          # 15% weight
    )
```

**The Problem:** For "unclassified" sources (priority = 0):
- evidence_normalized = 0/1000 = 0
- Max possible score = 0 + 25 + 15 = 40/100

Even great sources score "Low Trust" if not in the evidence hierarchy.

### Proposed Solution: Multi-Signal Source Scoring

**New Scoring Model:**

```
┌─────────────────────────────────────────────────────────────┐
│                    Source Quality Signals                    │
├─────────────────────────────────────────────────────────────┤
│  1. Provenance (35%)                                        │
│     - Known authoritative source (sst.dk, nice.org.uk)     │
│     - Domain reputation score                               │
│     - Publication type (guideline, RCT, review)            │
│                                                              │
│  2. Content Quality (25%)                                   │
│     - Has abstract/summary                                  │
│     - Contains methodology section                          │
│     - References other sources                              │
│     - Professional formatting                               │
│                                                              │
│  3. Recency (20%)                                           │
│     - Publication year vs today                             │
│     - Update frequency for guidelines                       │
│                                                              │
│  4. Relevance (20%)                                         │
│     - Keyword match to procedure topic                      │
│     - How well source answers the query                     │
│     - Citation frequency in results                         │
└─────────────────────────────────────────────────────────────┘
```

### Implementation Plan

#### Step 1: Expand Evidence Hierarchy
**File:** `config/evidence_hierarchy.yaml`

Add more source patterns and reasonable defaults:
```yaml
evidence_levels:
  danish_guideline:
    priority: 1000
    # ... existing

  # Add new levels
  peer_reviewed_journal:
    priority: 400
    badge: "Journal"
    badge_color: "#8b5cf6"
    description: "Peer-reviewed journal article"
    url_patterns:
      - "pubmed.ncbi.nlm.nih.gov"
      - "doi.org"
      - "sciencedirect.com"
      - "bmj.com"
      - "lancet.com"

  hospital_document:
    priority: 350
    badge: "Hospital"
    badge_color: "#f59e0b"
    description: "Hospital/regional procedure"
    url_patterns:
      - "regionh.dk"
      - "rm.dk"
      - "rsyd.dk"

  # Make unclassified less punishing
  unclassified:
    priority: 200  # Was 0! Now reasonable baseline
    badge: "Kilde"
    badge_color: "#d1d5db"
    description: "Ikke-klassificeret kilde"
```

#### Step 2: Add Content Quality Heuristics
**File:** `backend/procedurewriter/pipeline/source_scoring.py`

```python
def assess_content_quality(content: str) -> float:
    """
    Score 0.0-1.0 based on content quality signals.
    """
    score = 0.0

    # Has structured sections
    if any(h in content.lower() for h in ["methods", "metode", "baggrund", "background"]):
        score += 0.2

    # Has references/bibliography
    if any(r in content.lower() for r in ["references", "litteratur", "kilder"]):
        score += 0.2

    # Professional length (not too short, not just a paragraph)
    if 500 < len(content) < 50000:
        score += 0.2

    # Contains clinical/medical terminology
    medical_terms = ["behandling", "diagnose", "patient", "dosis", "mg", "ml"]
    if sum(1 for t in medical_terms if t in content.lower()) >= 3:
        score += 0.2

    # Has numbered lists or tables (suggests structured content)
    if re.search(r'\d+\.\s+\w+', content) or '|' in content:
        score += 0.2

    return min(1.0, score)
```

#### Step 3: Add Relevance Scoring
**File:** `backend/procedurewriter/pipeline/source_scoring.py`

```python
def assess_relevance(content: str, procedure_topic: str) -> float:
    """
    Score 0.0-1.0 based on how relevant source is to the topic.
    """
    # Simple keyword overlap for now
    topic_words = set(procedure_topic.lower().split())
    content_lower = content.lower()

    matches = sum(1 for w in topic_words if w in content_lower)
    return min(1.0, matches / max(len(topic_words), 1))
```

#### Step 4: Update Composite Score Formula
**File:** `backend/procedurewriter/pipeline/source_scoring.py`

```python
def score_source(
    source: SourceRecord,
    evidence_level: EvidenceLevel,
    current_year: int,
    procedure_topic: str = "",  # NEW
) -> SourceScore:
    # Provenance (from evidence hierarchy)
    provenance = min(1.0, evidence_level.priority / 1000.0)

    # Content quality (new)
    content = read_source_content(source.normalized_path)
    quality = assess_content_quality(content)

    # Recency
    recency = calculate_recency_score(source.year, current_year)

    # Relevance (new)
    relevance = assess_relevance(content, procedure_topic) if procedure_topic else 0.5

    # New balanced formula
    composite = (
        provenance * 35 +
        quality * 25 +
        recency * 20 +
        relevance * 20
    )

    return SourceScore(
        source_id=source.source_id,
        composite_score=int(composite),
        evidence_level=evidence_level.level_id,
        ...
    )
```

#### Step 5: Update Trust Level Thresholds
**File:** `backend/procedurewriter/pipeline/source_scoring.py`

```python
def get_trust_level(score: int) -> str:
    """Map composite score to trust level."""
    if score >= 70:
        return "Høj tillid"
    elif score >= 45:
        return "Middel tillid"
    else:
        return "Lav tillid"
```

With the new formula:
- Danish guideline (1000 provenance) + recent + relevant = 80-95
- PubMed journal (400 provenance) + recent + relevant = 55-70
- Unclassified (200 provenance) + poor quality = 30-45
- Unclassified (200 provenance) + good quality + relevant = 50-65

### Expected Outcomes

After implementation:
- Danish guidelines: 75-95 (High Trust) ✓
- Nordic/International guidelines: 65-85 (High Trust) ✓
- PubMed systematic reviews: 60-75 (Medium-High Trust)
- Hospital documents: 50-70 (Medium Trust)
- Unclassified but relevant: 45-60 (Medium Trust)
- Unclassified irrelevant: 25-40 (Low Trust)

---

## Implementation Priority

1. **DONE:** Protocol validation parsing fix
2. **HIGH:** Source scoring improvements (can be done without LLM calls)
3. **MEDIUM:** Evidence verification (requires LLM integration)

## Testing Plan

1. Run existing tests to ensure no regressions
2. Add unit tests for new scoring functions
3. Manual testing on existing runs to compare old vs new scores
4. UI testing to verify frontend displays new data correctly

---

## Appendix: Files to Modify

| File | Changes |
|------|---------|
| `protocols.py` | ✅ JSON parsing fix (DONE) |
| `source_scoring.py` | New scoring formula, content quality, relevance |
| `evidence_hierarchy.yaml` | Add more source patterns, fix unclassified priority |
| `evidence_verifier.py` | NEW: LLM-based evidence verification |
| `run.py` | Integrate evidence verification |
| `main.py` | New API endpoint for evidence details |
| `RunPage.tsx` | Display detailed evidence verification |
