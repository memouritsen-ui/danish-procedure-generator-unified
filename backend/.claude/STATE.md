# STATE.md - Current Project State

**LAST UPDATED**: 2024-12-21 22:30 UTC
**UPDATED BY**: Claude (Phase 0 validation session)

---

## CURRENT PHASE

```
╔════════════════════════════════════════════════════════════╗
║  PHASE 0: VALIDATION                         ✅ COMPLETE   ║
║  PHASE 1: DATA MODELS & MIGRATIONS           🔄 READY      ║
║  PHASE 2: PIPELINE STAGES                    ⏳ PENDING    ║
║  PHASE 3: CLAIM SYSTEM                       ⏳ PENDING    ║
║  PHASE 4: EVAL SUITE                         ⏳ PENDING    ║
║  PHASE 5: API & BUNDLE                       ⏳ PENDING    ║
╚════════════════════════════════════════════════════════════╝
```

---

## PHASE 0 VALIDATION RESULTS

**Status**: COMPLETE
**Verdict**: Claim extraction is FEASIBLE - proceed to Phase 1

**Test Results**:
| Procedure | Claims | Binding Rate |
|-----------|--------|--------------|
| Pneumoni behandling | 42 (25 threshold, 17 dose) | 100% |
| Akut astma | 19 (19 threshold) | 100% |
| Thoraxdræn | 0 (surgical - no doses) | N/A |

**Key Files Created**:
- `tests/phase0_claim_extraction_test.py` - Claim extraction PoC
- `tests/phase0_validate_procedures.py` - Validation runner
- `tests/phase0_validation_report.md` - Full report with S0/S1 taxonomy

**S0/S1 Issue Taxonomy Defined**:
- S0 (ship-blocking, safety): 7 issue types
- S1 (ship-blocking, quality): 6 issue types
- S2 (warnings): 4 issue types

---

## CURRENT TASK

```
TASK: P1-001 - Define Pydantic models for Claim, EvidenceChunk, Issue, Gate
STATUS: NOT STARTED
BLOCKED BY: None
NEXT ACTION: Create backend/procedurewriter/models/claims.py
```

---

## RECENT COMPLETIONS

| Date | Task | Verification |
|------|------|--------------|
| 2024-12-21 | P0-001: Find 3 procedure runs | 3 runs found |
| 2024-12-21 | P0-002: Extract claims Pneumoni | 42 claims |
| 2024-12-21 | P0-003: Extract claims Akut astma | 19 claims |
| 2024-12-21 | P0-004: Extract claims Thoraxdræn | 0 (surgical) |
| 2024-12-21 | P0-005: Test evidence binding | 100% accuracy |
| 2024-12-21 | P0-006: Define S0/S1 taxonomy | Documented |
| 2024-12-21 | P0-007: Document validation | Report created |

---

## BLOCKED TASKS

None currently blocked.

---

## INFRASTRUCTURE STATUS

**Backend Server**:
- Status: RUNNING (background task bef8554)
- Port: 8000
- Command: `uvicorn procedurewriter.main:app --reload --port 8000`

**Database**:
- Path: `backend/data/procedurewriter.db`
- Status: OPERATIONAL
- Encryption: ENABLED (PROCEDUREWRITER_SECRET_KEY set)

**Frontend**:
- Status: NOT RUNNING
- Port: 5173 (default Vite)
- Command: `cd frontend && npm run dev`

---

## LLM PROVIDER STATUS

| Provider | API Key | Status |
|----------|---------|--------|
| OpenAI | SET | WORKING |
| Anthropic | SET | WORKING |
| Ollama | N/A | AVAILABLE |

**Active Provider**: OpenAI (gpt-5.2)

---

## TEST STATUS

**Last Run**: 2024-12-21
**Result**: 77 test files, all passing

**Verification**:
```bash
cd backend && source .venv/bin/activate && pytest tests/ -x -q
```

---

## GIT STATUS

**Branch**: main
**Last Commit**: `05e5bc6 feat: add EMBASE/Scholar search via SerpAPI with Danish→English translation`
**Uncommitted Changes**: Phase 0 validation files (should be committed)

**To Commit**:
```bash
git add tests/phase0_*.py tests/phase0_*.md .claude/
git commit -m "feat: add Phase 0 validation and session-persistent documentation"
```

---

## FILE INVENTORY (Key Files)

### Pipeline Core
| File | Size | Purpose | Last Modified |
|------|------|---------|---------------|
| pipeline/run.py | 118KB | Main orchestrator | 2024-12-21 |
| pipeline/evidence.py | 12KB | Evidence processing | 2024-12-21 |
| pipeline/docx_writer.py | 42KB | Document generation | 2024-12-20 |
| pipeline/writer.py | 27KB | Procedure writing | 2024-12-21 |

### Agents
| File | Size | Purpose |
|------|------|---------|
| agents/orchestrator.py | 21KB | Agent coordination |
| agents/researcher.py | 24KB | Source research |
| agents/quality.py | 12KB | Quality scoring |
| agents/writer.py | 6KB | Draft writing |

### Models (TO BE CREATED)
| File | Status | Purpose |
|------|--------|---------|
| models/claims.py | PLANNED | Claim, ClaimType |
| models/evidence.py | PLANNED | EvidenceChunk, ClaimEvidenceLink |
| models/issues.py | PLANNED | Issue, IssueSeverity |
| models/gates.py | PLANNED | Gate, GateStatus |

---

## DATA RUNS

**Total Runs**: Multiple in `data/runs/`

**Test Procedures Used**:
| Run ID | Procedure | Claims |
|--------|-----------|--------|
| 5e5bbba1790a48d5ae1cf7cc270cfc6f | Pneumoni behandling | 42 |
| b51eaa3158604f53a71f1e66993fc402 | Akut astma | 19 |
| eca3718653d14a5680ba12ea628b4c65 | Thoraxdræn | 0 |

---

## NEXT SESSION CHECKLIST

When starting a new session:
1. [ ] Read this STATE.md
2. [ ] Read TASKS.md for current task
3. [ ] Run `pytest tests/ -x -q` to verify test status
4. [ ] Check git status for uncommitted changes
5. [ ] Continue from current task

---

**State Version**: 1.0
**Next Update Required After**: Completing P1-001
