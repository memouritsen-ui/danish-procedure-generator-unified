# BUILD.md - Master Build Control Document

**LAST VERIFIED**: 2024-12-21 22:30 UTC
**CURRENT PHASE**: Phase 1 - Data Models & Migrations
**PHASE 0 STATUS**: COMPLETE (Claim Extraction Feasibility Proven)

---

## CRITICAL: READ THIS FIRST

This document controls the build sequence for the Danish Procedure Generator refactoring project. Before doing ANY work:

1. Read STATE.md to understand current project state
2. Read TASKS.md to find the next uncompleted task
3. NEVER skip ahead - tasks must be completed in order
4. NEVER mark a task complete without passing tests
5. Update STATE.md after completing any task

---

## PROJECT OVERVIEW

**What This System Does**:
Danish Procedure Generator creates evidence-based medical emergency procedures in Danish. It uses a multi-agent LLM pipeline to research, write, validate, and refine clinical procedures.

**Current Architecture** (5-agent pipeline):
```
Researcher → Writer → Validator → Editor → Quality
```

**Target Architecture** (11-stage auditable build):
```
00 Bootstrap → 01 TermExpand → 02 Retrieve → 03 Chunk →
04 EvidenceNotes → 05 Draft → 06 ClaimExtract → 07 Bind →
08 Evals → 09 ReviseLoop → 10 PackageRelease
```

**Why Refactoring**:
Medical procedures require auditability. Every claim (dose, threshold, recommendation) must trace to evidence. Current system cannot prove claims are evidence-backed.

---

## BACKEND STRUCTURE

```
backend/
├── procedurewriter/
│   ├── main.py              # FastAPI app (19KB, 17 endpoints)
│   ├── db.py                # SQLite + encryption (42KB)
│   ├── settings.py          # Configuration
│   ├── schemas.py           # Pydantic models
│   ├── worker.py            # Background task worker
│   ├── routers/             # API route modules
│   │   ├── config.py
│   │   ├── keys.py
│   │   ├── templates.py
│   │   ├── styles.py
│   │   └── runs.py
│   ├── agents/              # LLM agents
│   │   ├── researcher.py    # Source research (24KB)
│   │   ├── writer.py        # Procedure drafting
│   │   ├── validator.py     # Medical validation
│   │   ├── editor.py        # Style editing
│   │   ├── quality.py       # Quality scoring
│   │   ├── orchestrator.py  # Agent coordination (21KB)
│   │   └── meta_analysis/   # Meta-analysis agents (8 files)
│   ├── pipeline/            # Pipeline stages (35 files)
│   │   ├── run.py           # Main orchestrator (118KB) ⚠️ LARGE
│   │   ├── evidence.py      # Evidence processing
│   │   ├── docx_writer.py   # Document generation
│   │   └── ...
│   └── llm/                 # LLM provider abstraction
│       ├── providers.py     # OpenAI, Anthropic, Ollama
│       ├── cost_tracker.py  # Token cost tracking
│       └── cache.py         # Response caching
├── tests/                   # 77 test files
├── config/                  # YAML configurations
└── data/                    # SQLite DB + run outputs
```

---

## API ENDPOINTS (17 total)

| Endpoint | Method | Purpose | Status |
|----------|--------|---------|--------|
| /api/status | GET | App health check | WORKING |
| /api/write | POST | Generate procedure | WORKING |
| /api/costs | GET | LLM cost summary | WORKING |
| /api/ingest/pdf | POST | Ingest PDF document | WORKING |
| /api/ingest/docx | POST | Ingest DOCX document | WORKING |
| /api/ingest/url | POST | Ingest URL content | WORKING |
| /api/library/stats | GET | Library statistics | WORKING |
| /api/library/search | GET | Search library | WORKING |
| /api/protocols | GET | List protocols | WORKING |
| /api/protocols/search | GET | Search protocols | WORKING |
| /api/protocols/{id} | GET | Get protocol | WORKING |
| /api/protocols/upload | POST | Upload protocol | WORKING |
| /api/protocols/{id} | PUT | Update protocol | WORKING |
| /api/protocols/{id} | DELETE | Delete protocol | WORKING |
| /api/procedures | GET | List procedures | WORKING |
| /api/procedures/{name}/versions | GET | Get versions | WORKING |
| /api/runs/{id}/claims | GET | Get claims | **PLANNED** |
| /api/runs/{id}/issues | GET | Get issues | **PLANNED** |
| /api/runs/{id}/gates | GET | Get gate status | **PLANNED** |
| /api/runs/{id}/bundle | GET | Download ZIP | **PLANNED** |

---

## LLM CONFIGURATION

**Configured Providers**:
| Provider | Default Model | Status |
|----------|---------------|--------|
| OpenAI | gpt-5.2 | CONFIGURED |
| Anthropic | claude-opus-4-5-20251101 | CONFIGURED |
| Ollama | (local) | AVAILABLE |

**Environment Variables**:
- `PROCEDUREWRITER_LLM_PROVIDER`: openai | anthropic | ollama
- `OPENAI_API_KEY`: Required for OpenAI
- `ANTHROPIC_API_KEY`: Required for Anthropic
- `PROCEDUREWRITER_SECRET_KEY`: For API key encryption

---

## TEST COVERAGE

**Current**: 77 test files in backend/tests/
**Status**: All passing (verified 2024-12-21)

**Verification Command**:
```bash
cd backend && source .venv/bin/activate && pytest tests/ -x -q
```

**Critical Test Files**:
- `tests/test_agents.py` - Agent functionality
- `tests/test_pipeline.py` - Pipeline stages
- `tests/test_llm_providers.py` - LLM abstraction
- `tests/phase0_*.py` - Claim extraction validation

---

## PHASE OVERVIEW

| Phase | Name | Status | Tasks |
|-------|------|--------|-------|
| P0 | Validation | COMPLETE | Claim extraction feasibility proven |
| P1 | Data Models | IN PROGRESS | Pydantic models, SQLite migrations |
| P2 | Pipeline Stages | PENDING | 11-stage implementation |
| P3 | Claim System | PENDING | Extraction, binding, normalization |
| P4 | Eval Suite | PENDING | Lints, gates, issue tracking |
| P5 | API & Bundle | PENDING | New endpoints, ZIP packaging |

---

## NEXT STEPS

1. Open TASKS.md to find current task
2. Complete task following TDD (test first)
3. Run verification command
4. Update STATE.md with completion
5. Mark task complete in TASKS.md
6. Commit if milestone reached

---

## TOOL USAGE REMINDERS

**For Code Search**:
```
Task(subagent_type="Explore", prompt="Find X in codebase")
```

**For Symbolic Navigation**:
```
mcp__plugin_serena_serena__find_symbol(name_path="ClassName/method")
mcp__plugin_serena_serena__get_symbols_overview(relative_path="file.py")
```

**For File Operations**:
```
Read(file_path="/absolute/path")  # NOT cat
Edit(file_path, old_string, new_string)  # NOT sed
Write(file_path, content)  # NOT echo >
```

**For Testing**:
```bash
pytest tests/ -x -q  # All tests, stop on first failure
pytest tests/specific_test.py -v  # Single file
pytest -k "test_name" -v  # By name pattern
```

---

## ENFORCEMENT RULES

1. **NO SKIPPING TASKS** - Complete tasks in numbered order
2. **NO CLAIMING COMPLETE WITHOUT TESTS** - Run pytest before marking done
3. **NO LARGE REFACTORS WITHOUT APPROVAL** - Ask before changes >200 lines
4. **ALWAYS UPDATE STATE.MD** - After any task completion
5. **COMMIT AT MILESTONES** - After completing a phase or 3+ tasks

---

## EMERGENCY RECOVERY

If project state is unclear:
```bash
# Check test status
cd backend && pytest tests/ -x -q

# Check last commits
git log --oneline -10

# Check run outputs
ls -la data/runs/ | tail -5

# Verify API is working
curl http://localhost:8000/api/status
```

---

**Document Version**: 1.0
**Created**: 2024-12-21
**Author**: Claude (session-persistent documentation system)
