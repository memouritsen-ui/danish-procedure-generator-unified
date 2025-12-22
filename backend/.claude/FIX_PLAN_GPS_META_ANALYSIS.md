# FIX PLAN: Evidence Policy Failure on Non-GPS Sentences

## Root Cause Summary
- GPS classification IS working (13 sentences exempt, version 3)
- 11 non-GPS sentences remain unsupported and trigger `EvidencePolicyError` under STRICT policy
- These fall into two categories:
  1. **Sentence fragments**: "at afklare øjeblikkeligt behandlingsbehov", "B3)", "amb."
  2. **Meta-analysis section statements**: "Evidensen baseres på 15 systematiske reviews...", "Formel meta-analyse kunne ikke gennemføres..."

## Proposed Fix: Expand GPS Detection for Meta-Analysis Section

### Why this approach:
- The meta-analysis section contains self-referential statements about the evidence synthesis methodology itself
- These are inherently non-citable because they describe THIS document's process, not external evidence
- They fit the GPS concept: consensus-based procedural statements that cannot have citations

## Changes Required

### 1. Add META_ANALYSIS GPS Pattern in `gps.py`

Add new pattern category to detect meta-analysis section statements:
```python
# New patterns to add:
- r"(?i)^evidensen baseres på"  # "Evidence is based on..."
- r"(?i)^formel meta-analyse"   # "Formal meta-analysis..."
- r"(?i)systematiske reviews"   # Mentions systematic reviews
- r"(?i)meta-analyse.*gennemføres"  # Meta-analysis execution statements
```

### 2. Improve Fragment Detection in `gps.py`

Add heuristics to mark very short/incomplete sentences as exempt:
```python
# Fragment detection criteria:
- Length < 20 characters AND no verb
- Starts with lowercase (continuation fragments)
- Single parenthetical references like "B3)", "A1)"
- Abbreviation-only like "amb.", "kons."
```

### 3. Update `is_gps_statement()` Function

Modify to check fragment heuristics BEFORE full pattern matching for efficiency.

## Files to Modify
1. `procedurewriter/pipeline/gps.py` - Add META_ANALYSIS patterns and fragment detection
2. `procedurewriter/pipeline/test_gps.py` - Add test cases for new patterns

## Estimated Test Coverage
- Add ~15-20 new test cases for:
  - Meta-analysis section statements
  - Fragment detection edge cases
  - False positive prevention (ensure real claims aren't marked as GPS)

## Risks
- **Over-classification**: New patterns might exempt sentences that SHOULD require citations
- **Mitigation**: Strict pattern matching with anchors (^) and explicit phrase detection

## Status
- [x] Root cause identified
- [x] Plan documented
- [ ] Tests written (TDD RED phase)
- [ ] Implementation (TDD GREEN phase)
- [ ] Refactor if needed
