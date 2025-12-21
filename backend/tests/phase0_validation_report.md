# Phase 0 Validation Report: Claim Extraction Feasibility

**Date**: 2024-12-21
**Status**: PASSED - Proceed to Phase 1

## Executive Summary

Tested claim extraction on 3 real procedures to validate feasibility of the auditable medical build system. Results show claim extraction is viable for pharmacological/threshold-based procedures.

## Test Results

| Procedure | Claims Extracted | By Type | Source Refs | Binding Rate |
|-----------|------------------|---------|-------------|--------------|
| Pneumoni behandling | 42 | 25 threshold, 17 dose | 100% | 100% |
| Akut astma | 19 | 19 threshold | 100% | 100% |
| Thoraxdræn | 0 | N/A (surgical) | N/A | N/A |

**Aggregate Results**:
- Total claims: 61
- Claims with source refs: 61 (100%)
- Resolvable to sources.jsonl: 98 refs (100%)
- Unresolvable refs: 0

## Key Findings

### 1. Claim Types Successfully Extracted

**DOSE patterns** (17 claims):
- `amoxicillin 50 mg/kg/d fordelt på 2-3 doser`
- `benzyl-penicillin 100 mg/kg/d`
- Drug name + value + unit + frequency

**THRESHOLD patterns** (44 claims):
- Clinical scores: `CURB-65 score 2-4`, `CRB-65 ≥3`
- Saturation: `sat <92%`, `SaO2 <90%`
- Temperature: `temperatur >38°C`
- Age: `≥18 år`, `0-17 år`, `børn <2 år`
- Respiratory: `RF >30/min`
- Blood pressure: `BT <90/60`

### 2. Procedure Type Dependency

**Pharmacological procedures** (Pneumoni, Akut astma):
- High claim density
- Doses and thresholds prevalent
- Evidence binding straightforward

**Surgical/procedural procedures** (Thoraxdræn):
- No doses or clinical thresholds
- Contains algorithm steps, contraindications, equipment
- Requires different claim patterns

### 3. Evidence Binding Accuracy

100% of extracted claims with source references resolved to valid entries in sources.jsonl. This validates:
- The `[SRC####]` format is consistent
- Source IDs in procedure text match stored sources
- Evidence chain is intact

## S0/S1 Issue Taxonomy

### S0: Ship-Blocking (Safety Critical)

| Code | Name | Description | Auto-detectable |
|------|------|-------------|-----------------|
| S0-001 | orphan_citation | Citation [CIT-X] not in sources | Yes |
| S0-002 | hallucinated_source | Source ID doesn't exist | Yes |
| S0-003 | dose_without_evidence | DOSE claim has no source ref | Yes |
| S0-004 | threshold_without_evidence | THRESHOLD claim has no source ref | Yes |
| S0-005 | contraindication_unbound | CONTRAINDICATION without evidence | Yes |
| S0-006 | conflicting_doses | Same drug, different doses, same tier | Manual review |
| S0-007 | missing_mandatory_section | Required section empty/missing | Yes |

### S1: Ship-Blocking (Quality Critical)

| Code | Name | Description | Auto-detectable |
|------|------|-------------|-----------------|
| S1-001 | claim_binding_failed | Claim couldn't be matched to evidence | Yes |
| S1-002 | weak_evidence_for_strong_claim | Tier 7+ evidence for definitive statement | Yes |
| S1-003 | outdated_guideline | Source >5 years old | Yes |
| S1-004 | template_incomplete | Section present but <100 characters | Yes |
| S1-005 | unit_mismatch | Inconsistent units in same section | Yes |
| S1-006 | age_group_conflict | Contradictory age recommendations | Manual review |

### S2: Warning (Non-blocking)

| Code | Name | Description | Auto-detectable |
|------|------|-------------|-----------------|
| S2-001 | danish_term_variant | Multiple spellings of same term | Yes |
| S2-002 | evidence_redundancy | Same claim bound to >3 sources | Yes |
| S2-003 | informal_language | Non-clinical phrasing detected | Yes |
| S2-004 | missing_duration | Treatment without duration specified | Yes |

## Claim Type Coverage

| Claim Type | Implemented | Coverage |
|------------|-------------|----------|
| DOSE | Yes | High |
| THRESHOLD | Yes | High |
| RECOMMENDATION | Partial | Needs expansion |
| CONTRAINDICATION | Partial | Needs expansion |
| RED_FLAG | No | TODO |
| ALGORITHM_STEP | No | TODO (for surgical) |

## Regex Patterns (Final)

```python
DOSE_PATTERNS = [
    r'([a-zA-ZæøåÆØÅ\-]+)\s+(\d+(?:[.,]\d+)?)\s*(mg|g|mcg|μg|ml|IE|U)(?:/kg)?(?:/d(?:ag|øgn)?)?',
    r'(\d+(?:[.,]\d+)?)\s*(mg|g|mcg|μg|ml)\s+(?:hver|x)\s+(\d+)\.?\s*(?:time|dag)',
]

THRESHOLD_PATTERNS = [
    r'(CURB-65|CRB-65|CURB65|CRB65)\s*(?:score)?\s*([≥≤><]?\s*\d+(?:-\d+)?)',
    r'(?:sat(?:uration)?|SpO2|SaO2)\s*([<>≤≥])\s*(\d+)\s*%',
    r'(?:temperatur|feber|temp)\s*([<>≤≥])\s*(\d+(?:[.,]\d+)?)\s*°?C?',
    r'alder\s*([<>≤≥])\s*(\d+)\s*(år|måneder|mdr|uger)?',
    r'([≥≤><])\s*(\d+)\s*år',
    r'(\d+)[-–](\d+)\s*år',
    r'børn\s*([<>≤≥])\s*(\d+)\s*år',
    r'(?:RF|respirationsfrekvens)\s*([<>≤≥])\s*(\d+)(?:/min)?',
    r'(?:BT|blodtryk)\s*([<>≤≥])\s*(\d+)/(\d+)',
    r'(?:urea|karbamid)\s*([<>≤≥])\s*(\d+(?:[.,]\d+)?)\s*mmol/l',
    r'kapillærrespons\s*([<>≤≥])\s*(\d+)\s*sek',
    r'(?:PEF|peak\s*flow|PF)\s*([<>≤≥])\s*(\d+)',
]
```

## Recommendations for Phase 1

1. **Proceed with claim extraction implementation** - Proven viable
2. **Add ALGORITHM_STEP patterns** - For surgical procedures
3. **Expand CONTRAINDICATION patterns** - Currently limited
4. **Use structured LLM output** - Supplement regex with LLM extraction
5. **Implement S0 gates first** - Citation integrity is highest priority

## Verdict

**CLAIM EXTRACTION: FEASIBLE**

- Regex patterns successfully extract doses and thresholds
- Evidence binding achieves 100% accuracy on test set
- S0/S1 taxonomy defined with auto-detection capabilities
- Proceed to Phase 1: Data Models & Migrations
