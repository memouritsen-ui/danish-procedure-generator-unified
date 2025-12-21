# Hookify Rules Evaluation Report

**Date:** 2025-12-18
**Project:** Danish Procedure Generator Unified
**Evaluator:** Claude Code (Opus 4.5)

---

## Executive Summary

Evaluated 8 generic hookify rules against this codebase. Most rules work well. The `warn-mock-dummy` rule generates excessive false positives due to legitimate `dummy_mode` feature and test mocking patterns. Created 3 project-specific rules to address gaps.

---

## 1. Generic Hookify Rules Evaluation

Located in `~/.claude/hookify.*.local.md`

| Rule | False Positive Risk | Verdict |
|------|---------------------|---------|
| `warn-dangerous-rm` | Low | ✅ Keep as-is |
| `warn-force-push` | Low | ✅ Keep as-is |
| `warn-mock-dummy` | **HIGH** | ⚠️ Use project-specific version |
| `warn-quick-fix` | None (0 matches) | ✅ Keep as-is |
| `require-skills-check` | Low | ✅ Keep as-is |
| `require-mcp-check` | Low | ✅ Keep as-is |
| `verify-integration` | Low | ✅ Keep as-is |
| `context-anchor` | Low | ✅ Keep as-is |

### False Positive Analysis: `warn-mock-dummy`

120+ pattern matches found, but most are legitimate:

| Pattern | Location | Legitimate? |
|---------|----------|-------------|
| `dummy_mode` | `settings.py`, `run.py`, `writer.py` | ✅ Feature for API-free testing |
| `MockLLMProvider` | `backend/tests/test_agents.py` | ✅ Proper test isolation |
| `@respx.mock` | `backend/tests/test_*.py` | ✅ HTTP mocking in tests |
| `placeholders` | `library_search.py:145,216` | ✅ SQL parameterized queries |
| `placeholder` | `IngestPage.tsx`, `WritePage.tsx` | ✅ HTML input attributes |
| `Placeholder for pipeline` | `researcher.py:161` | ⚠️ DI comment (acceptable) |

---

## 2. Code Quality Assessment

### Backend: A- (Strong)

| Module | Lines | Quality | Notes |
|--------|-------|---------|-------|
| `pipeline/run.py` | 760 | Good | Complete orchestration |
| `pipeline/writer.py` | 569 | Good | Full LLM integration |
| `pipeline/docx_writer.py` | 457 | Good | Complete DOCX generation |
| `pipeline/library_search.py` | 263 | Excellent | Clean FTS5 implementation |
| `agents/orchestrator.py` | 278 | Excellent | 5-agent workflow with quality loop |
| `llm/providers.py` | 386 | Excellent | 3-provider abstraction |

**Key Findings:**
- Zero TODO/FIXME/HACK comments in production code
- Complete agent implementations (no stubs)
- Proper error handling throughout
- 136 tests across 20 test files
- Type hints everywhere

### Frontend: B+ (Good)

| File | Quality | Notes |
|------|---------|-------|
| `api.ts` | Excellent | Fully typed API client |
| `WritePage.tsx` | Good | Proper state management |
| `SettingsPage.tsx` | Good | Multi-provider support |

---

## 3. Integration Plan Risk Assessment

Based on `GUIDELINE_LIBRARY_INTEGRATION_PLAN.md`:

| Phase | Risk | Reason |
|-------|------|--------|
| **Phase 3** | 🔴 HIGH | Core pipeline modification - citation validation at risk |
| Phase 4 | 🟡 Medium | Retrieval complexity - over-engineering risk |
| Phase 5 | 🟡 Medium | UI scope creep potential |
| Phase 1 | 🟢 Low | Standalone script |
| Phase 2 | 🟢 Low | Already complete |
| Phase 6 | 🟢 Low | Well-defined QA scope |

### Phase 3 Critical Risks

1. **Memory explosion** - Copying all 53k docs to run folder
2. **Citation validation failure** - Sources not in `sources.jsonl`
3. **Evidence hierarchy break** - Wrong priority assignment
4. **Audit trail corruption** - Missing SHA256 hashes

---

## 4. Project-Specific Hookify Rules Created

Located in `.claude/` directory:

### `hookify.project-mock-filter.local.md`
Tuned mock/placeholder detection that excludes:
- `dummy_mode` feature
- SQL `placeholders`
- Test files
- HTML placeholder attributes

### `hookify.guideline-integration-checklist.local.md`
Stop-event checklist for integration work:
- Phase completion verification
- Critical constraint reminders
- Integration point verification

### `hookify.citation-validation-reminder.local.md`
Triggers when modifying citation-related files:
- `sources.jsonl`
- `citations.py`
- `writer.py`
- `run.py`

Reminds about non-negotiable citation requirements.

---

## 5. Recommendations

### For Daily Development
1. Keep generic hookify rules in `~/.claude/`
2. Project-specific rules in `.claude/` will auto-load
3. Run `pytest backend/tests/test_citations.py` after pipeline changes

### For Integration Work (Phase 3-6)
1. Read `GUIDELINE_LIBRARY_INTEGRATION_PLAN.md` before starting
2. Understand `library_search.py` (Phase 2 is done)
3. Focus on `run.py` for Phase 3 changes
4. Test with dummy_mode first: `PROCEDUREWRITER_DUMMY_MODE=1 make dev`
5. Check run folder sizes: `du -sh data/runs/*/`

### Critical Safety Checks
```bash
# Always run before committing pipeline changes
pytest backend/tests/test_citations.py backend/tests/test_e2e.py

# Verify run folder size after integration changes
du -sh data/runs/*/
```

---

## 6. Files Reference

### Critical Files (Don't Break)
- `backend/procedurewriter/pipeline/citations.py` - Citation validator
- `backend/procedurewriter/pipeline/sources.py` - SourceRecord format
- `backend/procedurewriter/pipeline/run.py` - Main pipeline

### Integration Files
- `backend/procedurewriter/pipeline/library_search.py` - Phase 2 (done)
- `docs/GUIDELINE_LIBRARY_INTEGRATION_PLAN.md` - Master plan

### Configuration
- `config/author_guide.yaml` - Writing style
- `config/source_allowlist.yaml` - Allowed source URLs
- `config/evidence_hierarchy.yaml` - Source priority ranking

---

## Appendix: Test Commands

```bash
# Full test suite
make check

# Citation-specific tests
pytest backend/tests/test_citations.py -v

# E2E tests
pytest backend/tests/test_e2e.py -v

# Agent tests
pytest backend/tests/test_agents.py -v

# Quick dev mode
PROCEDUREWRITER_DUMMY_MODE=1 make dev
```
