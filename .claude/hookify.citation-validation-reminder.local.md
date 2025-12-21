---
name: citation-validation-reminder
enabled: true
event: file
pattern: (sources\.jsonl|citations\.py|writer\.py|run\.py)
action: warn
---

## CITATION VALIDATION - CRITICAL SAFETY CHECK

You're modifying files related to the citation/source system.

**Non-negotiable requirements (from BUILD_SPEC.md):**

1. **No hallucinated sources**: Writer may ONLY cite `source_id` from `sources.jsonl`
2. **Per-sentence citation**: Every factual statement needs `[S:<source_id>]`
3. **Audit trail**: Each source must have SHA256 hashes for raw + normalized
4. **Validation must fail run if**:
   - A sentence lacks `[S:...]` citation
   - A `source_id` doesn't exist in `sources.jsonl`

**Before completing this change:**
- [ ] Run `pytest backend/tests/test_citations.py`
- [ ] Verify citation validator still rejects invalid citations
- [ ] Check that `sources.jsonl` format unchanged

**If adding new source types (e.g., guideline library):**
- Must convert to standard `SourceRecord` format
- Must include all required fields (raw_sha256, normalized_sha256, etc.)
- Must be written to run folder before citation validation runs
