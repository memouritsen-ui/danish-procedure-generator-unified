---
name: guideline-integration-checklist
enabled: true
event: stop
pattern: .*
action: warn
---

## GUIDELINE LIBRARY INTEGRATION CHECKLIST

Before finishing work on the guideline integration (GUIDELINE_LIBRARY_INTEGRATION_PLAN.md), verify:

**Phase Completion:**
- [ ] Phase 1: Index health check script created and run?
- [ ] Phase 2: LibrarySearchProvider complete (library_search.py)?
- [ ] Phase 3: run_pipeline() updated for selective source loading?
- [ ] Phase 4: 2-tier retrieval (FTS→BM25→embeddings) implemented?
- [ ] Phase 5: UI shows library status and search results?
- [ ] Phase 6: Tests written for integration points?

**Critical Constraints (from plan):**
- Run folder must stay <50-200 MB
- Only K=10-30 guideline sources per run (NOT all 53k)
- Candidate search must be <2 seconds
- Citation validation must still pass

**Integration Points to Verify:**
- `run_pipeline()` calls `LibrarySearchProvider.search()`?
- Selected docs converted to `SourceRecord`?
- `sources.jsonl` includes guideline sources with correct format?
- Evidence hierarchy assigns priority 1000 to library sources?

**Don't claim "integration complete" if any of above are missing.**
