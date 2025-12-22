# STATE.md - Current Project State

**LAST UPDATED**: 2024-12-22 13:00 UTC
**UPDATED BY**: Claude (P3-003 complete, THRESHOLD extraction with 35 tests)

---

## CURRENT PHASE

```
╔════════════════════════════════════════════════════════════╗
║  PHASE 0: VALIDATION                         ✅ COMPLETE   ║
║  PHASE 1: DATA MODELS & MIGRATIONS           ✅ COMPLETE   ║
║  PHASE 1 HOTFIX: ARCHITECTURAL DEBT          ✅ COMPLETE   ║
║  PHASE 2: PIPELINE STAGES                    ✅ COMPLETE   ║
║  PHASE 3: CLAIM SYSTEM                       ⏳ PENDING    ║
║  PHASE 4: EVAL SUITE                         ⏳ PENDING    ║
║  PHASE 5: API & BUNDLE                       ⏳ PENDING    ║
╚════════════════════════════════════════════════════════════╝
```

**✅ COMPLETE**: Phase 2 - Pipeline Stages (12/12 tasks).
All 11 stages wired into PipelineOrchestrator with full integration.

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
TASK: P3-007 - Implement ALGORITHM_STEP extraction
STATUS: NOT STARTED
BLOCKED BY: None
NEXT ACTION: Create ALGORITHM_STEP tests for numbered step patterns

✅ P3-006 complete - RED_FLAG extraction validated with 37 tests
✅ P3-005 complete - CONTRAINDICATION extraction validated with 37 tests
✅ P3-004 complete - RECOMMENDATION extraction validated with 36 tests
✅ P3-003 complete - THRESHOLD extraction validated with 35 tests
✅ P3-002 complete - DOSE extraction validated with 35 tests
✅ P3-001 complete - ClaimExtractor class created with 27 tests (PHASE 3 START)
✅ P2-012 complete - PipelineOrchestrator created with 15 tests (PHASE 2 COMPLETE)
✅ P2-011 complete - PackageRelease stage created with 14 tests
✅ P2-010 complete - ReviseLoop stage created with 13 tests
✅ P2-009 complete - Evals stage created with 16 tests
✅ P2-008 complete - Bind stage created with 15 tests
✅ P2-007 complete - ClaimExtract stage created with 14 tests
✅ P2-006 complete - Draft stage created with 13 tests
✅ P2-005 complete - EvidenceNotes stage created with 13 tests
✅ P2-004 complete - Chunk stage created with 13 tests
✅ P2-003 complete - Retrieve stage created with 12 tests
✅ P2-002 complete - TermExpand stage created with 12 tests
✅ P2-001 complete - Bootstrap stage created with 12 tests
```

---

## ISSUES DETECTED

| Date | Issue | Severity | Status |
|------|-------|----------|--------|
| 2024-12-22 | UUID/string type mismatch - 30+ scattered str() calls | HIGH | ✅ FIXED (P1-HF7) |
| 2024-12-22 | No model-to-DB conversion layer | HIGH | ✅ FIXED (P1-HF1-HF6) |
| 2024-12-22 | Tests retrofitted to match impl (backwards TDD) | MEDIUM | Documented |
| 2024-12-22 | Skills not used (systematic-debugging skipped) | MEDIUM | Documented |

---

## RECENT COMPLETIONS

| Date | Task | Verification |
|------|------|--------------|
| 2024-12-22 | **P3-006: Implement RED_FLAG extraction** | 37 tests pass (1316 total) |
| 2024-12-22 | **P3-005: Implement CONTRAINDICATION extraction** | 37 tests pass (1279 total) |
| 2024-12-22 | **P3-004: Implement RECOMMENDATION extraction** | 36 tests pass (1242 total) |
| 2024-12-22 | **P3-003: Implement THRESHOLD extraction** | 35 tests pass (1206 total) |
| 2024-12-22 | **P3-002: Implement DOSE extraction** | 35 tests pass (1171 total) |
| 2024-12-22 | **P3-001: Create ClaimExtractor class (PHASE 3 START)** | 27 tests pass (1136 total) |
| 2024-12-22 | **P2-012: Wire stages into pipeline (PHASE 2 COMPLETE)** | 15 tests pass (1109 total) |
| 2024-12-22 | P2-011: Create Stage 10: PackageRelease | 14 tests pass (1094 total) |
| 2024-12-22 | P2-010: Create Stage 09: ReviseLoop | 13 tests pass (1080 total) |
| 2024-12-22 | P2-009: Create Stage 08: Evals | 16 tests pass (1067 total) |
| 2024-12-22 | P2-008: Create Stage 07: Bind | 15 tests pass (1051 total) |
| 2024-12-22 | P2-007: Create Stage 06: ClaimExtract | 14 tests pass (1036 total) |
| 2024-12-22 | P2-006: Create Stage 05: Draft | 13 tests pass (1022 total) |
| 2024-12-22 | P2-005: Create Stage 04: EvidenceNotes | 13 tests pass (1009 total) |
| 2024-12-22 | P2-004: Create Stage 03: Chunk | 13 tests pass (996 total) |
| 2024-12-22 | P2-003: Create Stage 02: Retrieve | 12 tests pass (983 total) |
| 2024-12-22 | P2-002: Create Stage 01: TermExpand | 12 tests pass (971 total) |
| 2024-12-22 | P2-001: Create Stage 00: Bootstrap | 12 tests pass (959 total) |
| 2024-12-22 | **P1-HOTFIX COMPLETE** (8/8 tasks) | Phase 2 UNBLOCKED |
| 2024-12-22 | P1-HF8: Add factory functions for test data | 947 tests pass |
| 2024-12-22 | P1-HF7: Remove scattered str() calls from tests | 929 tests pass |
| 2024-12-22 | P1-HF6: Add from_db_row() to all 5 models | 100 model tests pass |
| 2024-12-22 | P1-HF5: Add to_db_row() to Gate model | 21 tests pass |
| 2024-12-22 | P1-HF4: Add to_db_row() to Issue model | 22 tests pass |
| 2024-12-22 | P1-HF3: Add to_db_row() to ClaimEvidenceLink model | 22 tests pass |
| 2024-12-22 | P1-HF2: Add to_db_row() to EvidenceChunk model | 19 tests pass |
| 2024-12-22 | P1-HF1: Add to_db_row() to Claim model | 20 tests pass |
| 2024-12-22 | P1-012: Integration test for all models | 9 tests pass |
| 2024-12-22 | P1-011: Migration rollback scripts | 13 tests pass |
| 2024-12-22 | P1-006 to P1-010: All SQLite migrations | 21 tests pass |
| 2024-12-22 | P1-005: Gate, GateStatus, GateType models | 18 tests pass |
| 2024-12-22 | P1-004: Issue, IssueCode, IssueSeverity models | 19 tests pass |
| 2024-12-21 | P1-002 + P1-003: EvidenceChunk + ClaimEvidenceLink | 16 tests pass |
| 2024-12-21 | P1-001: Create Claim/ClaimType models | 17 tests pass |
| 2024-12-21 | P0-001 to P0-007: Phase 0 validation complete | Feasibility proven |

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

**Last Run**: 2024-12-22 (P3-006 complete)
**Result**: 1316 tests passed, 1 skipped

**Verification**:
```bash
cd backend && source .venv/bin/activate && pytest tests/ -x -q
```

---

## GIT STATUS

**Branch**: main
**Last Commit**: `e7b23d3 feat: complete Phase 1 - Data Models & Migrations`
**Uncommitted Changes**: None (clean working tree)

---

## UNCOMMITTED CHANGES TRACKER

⚠️ **BEFORE STARTING ANY NEW TASK**, run this check:

```bash
git status --short
```

**If output is NOT empty**, you have uncommitted work. COMMIT IT FIRST:
```bash
git add . && git commit -m "feat: P#-###: [description]"
```

**Current Status**: ✅ Clean (verified 2024-12-22)

| File | Status | Action Required |
|------|--------|-----------------|
| (none) | - | - |

**Rule**: Never start a new task with uncommitted changes. If you see uncommitted files here, the previous session failed to commit. Commit them before proceeding.

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

### Models
| File | Status | Purpose |
|------|--------|---------|
| models/claims.py | DONE | Claim, ClaimType (17 tests) |
| models/evidence.py | DONE | EvidenceChunk, ClaimEvidenceLink, BindingType (16 tests) |
| models/issues.py | DONE | Issue, IssueCode, IssueSeverity (19 tests) |
| models/gates.py | DONE | Gate, GateStatus, GateType (18 tests) |

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

## SESSION TRACKER

**PURPOSE**: Prevent context exhaustion by enforcing session breaks.

| Session | Started At | Ended At | Tasks Completed | Context % |
|---------|------------|----------|-----------------|-----------|
| (current) | 2024-12-22 | - | 3 | ~35% |

**RULES** (from CLAUDE.md):
- Max 4 tasks per session
- End session if context > 60%
- Update this tracker when ending session

**BEFORE ENDING THIS SESSION**:
```bash
# 1. Commit and push
git add . && git commit -m "..." && git push

# 2. Update this section:
#    - Move (current) to completed row
#    - Add tasks completed count
#    - Note context % at end

# 3. Verify clean
git status
```

---

**State Version**: 1.7
**Next Update Required After**: Completing P2-002 or next task
