# TASKS.md - Master Task Checklist

**LAST UPDATED**: 2024-12-22 02:00 UTC

---

## TASK COMPLETION RULES

1. **NEVER skip tasks** - Complete in order
2. **NEVER mark complete without tests** - Run verification command
3. **Update STATE.md** after completing any task
4. **Commit after EVERY task** - Not just milestones

---

## ⏱️ SESSION BREAK RULE (CRITICAL)

```
┌─────────────────────────────────────────────────────────────┐
│  CONTEXT EXHAUSTION PREVENTION                              │
├─────────────────────────────────────────────────────────────┤
│  Max tasks per session: 4                                   │
│  Max context usage: 60%                                     │
│  If context > 50%: Finish task, then END SESSION            │
├─────────────────────────────────────────────────────────────┤
│  After 4 tasks OR 60% context → END SESSION                 │
│  Update SESSION TRACKER in STATE.md before ending           │
│  New session reads STATE.md and continues from next task    │
└─────────────────────────────────────────────────────────────┘
```

**WHY**: Long sessions cause context compaction, which loses critical information about completed work. Sessions are disposable; STATE.md is persistent.

---

## MANDATORY TASK COMPLETION SEQUENCE

After completing ANY task, you MUST follow this exact sequence:

```
┌─────────────────────────────────────────────────────────────┐
│  TASK COMPLETION CHECKLIST (DO ALL 6 STEPS)                │
├─────────────────────────────────────────────────────────────┤
│  1. Run test command for the task                          │
│  2. Verify ALL tests pass (not just new ones)              │
│  3. Mark task [x] in this file with test count             │
│  4. Update STATE.md (current task, recent completions)     │
│  5. git add . && git commit -m "feat: P#-###: description" │
│  6. RE-READ CLAUDE.md to refresh context                   │
└─────────────────────────────────────────────────────────────┘
```

**Step 6 is CRITICAL**: After every task, re-read the project CLAUDE.md to:
- Refresh your understanding of project rules
- Ensure you haven't drifted from the build plan
- Catch any context loss from long operations

**Commit Message Format**:
```
feat: P1-001: Create Claim and ClaimType models

- Added ClaimType enum with 6 claim types
- Added Claim dataclass with validation
- 17 tests passing

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

---

## 🚨 IMMEDIATE FAIL: ANTI-PATTERNS

The following patterns are **IMMEDIATE FAILURES**. If you catch yourself doing any of these, STOP and fix the design first.

### Anti-Pattern 1: BAND-AID FIXES

```python
# ❌ WRONG: Scattering str() calls to fix type mismatches
(str(claim.id), str(claim.run_id), str(chunk.id), ...)

# ✅ RIGHT: Fix in ONE place with proper conversion layer
class Claim:
    def to_db_row(self) -> tuple:
        return (str(self.id), str(self.run_id), ...)
```

**Detection**: If you're adding the same fix in 5+ places, you're band-aiding.
**Action**: STOP. Design a proper abstraction. Add it in ONE place.

### Anti-Pattern 2: RETROFITTING TESTS

```python
# ❌ WRONG: Change test to match whatever implementation did
# Test originally had: IssueCode.UNBOUND_CLAIM
# Changed to: IssueCode.DOSE_WITHOUT_EVIDENCE (because impl used that)

# ✅ RIGHT: Test defines the interface, implementation matches
# 1. Write test with desired enum value
# 2. Create/modify enum to include that value
# 3. Test passes because impl matches design
```

**Detection**: If you're changing tests to match implementation, you're backwards.
**Action**: STOP. The test is the specification. Fix the implementation.

### Anti-Pattern 3: TRIAL-AND-ERROR DEBUGGING

```python
# ❌ WRONG: Change something, run tests, repeat 13 times
# (Evidence: server log shows file modified 13 times)

# ✅ RIGHT: Use systematic-debugging skill
# 1. Read the error message carefully
# 2. Identify the root cause (not symptom)
# 3. Fix the root cause in ONE change
# 4. Run tests once
```

**Detection**: If you've modified the same file 3+ times for the same test, you're guessing.
**Action**: STOP. Use `Skill(superpowers:systematic-debugging)`.

### Anti-Pattern 4: SKIPPING SKILLS

```
# ❌ WRONG: Plow through tasks without using available skills
# - No systematic-debugging when tests fail
# - No verification-before-completion before marking done
# - No reading model definitions before writing tests

# ✅ RIGHT: Check for applicable skills BEFORE each action
# - Tests failing? → Skill(superpowers:systematic-debugging)
# - About to mark done? → Skill(superpowers:verification-before-completion)
# - Writing tests? → READ the model/enum definitions FIRST
```

**Detection**: You're debugging without skills, or completing without verification.
**Action**: STOP. Run the appropriate skill.

### Enforcement

If you detect ANY of these patterns:
1. **STOP immediately**
2. Document what went wrong in STATE.md under "ISSUES DETECTED"
3. Fix the root cause, not the symptom
4. Only then continue

---

## LEGEND

- `[x]` - COMPLETE (verified with tests)
- `[~]` - IN PROGRESS (currently working)
- `[ ]` - PENDING (not started)
- `[!]` - BLOCKED (see notes)

---

## PHASE 0: VALIDATION ✅ COMPLETE

**Objective**: Prove claim extraction and evidence binding feasibility

| ID | Task | Status | Test Command | Notes |
|----|------|--------|--------------|-------|
| P0-001 | Find 3 completed procedure runs | [x] | `ls data/runs/` | Found: Pneumoni, Akut astma, Thoraxdræn |
| P0-002 | Extract claims from Pneumoni | [x] | `python tests/phase0_validate_procedures.py` | 42 claims extracted |
| P0-003 | Extract claims from Akut astma | [x] | `python tests/phase0_validate_procedures.py` | 19 claims extracted |
| P0-004 | Extract claims from Thoraxdræn | [x] | `python tests/phase0_validate_procedures.py` | 0 claims (surgical) |
| P0-005 | Test evidence binding accuracy | [x] | `python tests/phase0_validate_procedures.py` | 100% binding rate |
| P0-006 | Define S0/S1 issue taxonomy | [x] | Review `tests/phase0_validation_report.md` | 7 S0, 6 S1, 4 S2 |
| P0-007 | Document validation results | [x] | File exists check | Report created |

**Phase 0 Verification**:
```bash
python tests/phase0_validate_procedures.py
# Expected: "VERDICT: Claim extraction is FEASIBLE"
```

---

## PHASE 1: DATA MODELS & MIGRATIONS ✅ COMPLETE

**Objective**: Create Pydantic models and SQLite migrations for claim system

| ID | Task | Status | Test Command | Notes |
|----|------|--------|--------------|-------|
| P1-001 | Create Claim and ClaimType models | [x] | `pytest tests/models/test_claims.py -v` | 17 tests pass |
| P1-002 | Create EvidenceChunk model | [x] | `pytest tests/models/test_evidence.py -v` | 11 tests pass |
| P1-003 | Create ClaimEvidenceLink model | [x] | `pytest tests/models/test_evidence.py -v` | 5 tests pass |
| P1-004 | Create Issue and IssueSeverity models | [x] | `pytest tests/models/test_issues.py -v` | 19 tests pass |
| P1-005 | Create Gate and GateStatus models | [x] | `pytest tests/models/test_gates.py -v` | 18 tests pass |
| P1-006 | Write SQLite migration for claims table | [x] | `pytest tests/test_db_claims.py -v` | 5 tests pass |
| P1-007 | Write SQLite migration for evidence_chunks | [x] | `pytest tests/test_db_claims.py -v` | 3 tests pass |
| P1-008 | Write SQLite migration for claim_evidence_links | [x] | `pytest tests/test_db_claims.py -v` | 3 tests pass |
| P1-009 | Write SQLite migration for issues table | [x] | `pytest tests/test_db_claims.py -v` | 5 tests pass |
| P1-010 | Write SQLite migration for gates table | [x] | `pytest tests/test_db_claims.py -v` | 5 tests pass |
| P1-011 | Write migration rollback scripts | [x] | `pytest tests/test_db_rollback.py -v` | 13 tests pass |
| P1-012 | Integration test: create/read all models | [x] | `pytest tests/integration/test_models.py -v` | 9 tests pass |

**Phase 1 Verification**:
```bash
pytest tests/models/ -v && pytest tests/integration/test_models.py -v
# Expected: All tests pass, tables exist in DB
```

---

## 🔧 PHASE 1 HOTFIX: ARCHITECTURAL DEBT ⚠️ BLOCKING

**Priority**: MUST complete before Phase 2
**Reason**: Phase 1 was completed with band-aid fixes that will cause ongoing problems

| ID | Task | Status | Test Command | Notes |
|----|------|--------|--------------|-------|
| P1-HF1 | Add `to_db_row()` method to Claim model | [x] | `pytest tests/models/test_claims.py -v` | 20 tests pass |
| P1-HF2 | Add `to_db_row()` method to EvidenceChunk model | [x] | `pytest tests/models/test_evidence.py -v` | 19 tests pass |
| P1-HF3 | Add `to_db_row()` method to ClaimEvidenceLink model | [x] | `pytest tests/models/test_evidence.py -v` | 22 tests pass |
| P1-HF4 | Add `to_db_row()` method to Issue model | [x] | `pytest tests/models/test_issues.py -v` | 22 tests pass |
| P1-HF5 | Add `to_db_row()` method to Gate model | [x] | `pytest tests/models/test_gates.py -v` | 21 tests pass |
| P1-HF6 | Add `from_db_row()` classmethod to all models | [x] | `pytest tests/models/ -v` | 100 tests pass |
| P1-HF7 | Remove all scattered `str()` calls from tests | [x] | `pytest tests/ -v` | 929 tests pass |
| P1-HF8 | Add factory functions for test data | [x] | `pytest tests/ -v` | 947 tests pass |

**Design Decision (MAKE BEFORE STARTING)**:
```python
# Each model will have:
class Claim:
    def to_db_row(self) -> tuple:
        """Convert model to database row tuple."""
        return (
            str(self.id),  # UUID → TEXT
            str(self.run_id),
            self.claim_type.value,  # Enum → string
            ...
        )

    @classmethod
    def from_db_row(cls, row: sqlite3.Row) -> "Claim":
        """Reconstruct model from database row."""
        return cls(
            id=uuid.UUID(row["id"]),
            run_id=uuid.UUID(row["run_id"]),
            claim_type=ClaimType(row["claim_type"]),
            ...
        )
```

**Verification**:
```bash
# After hotfix complete, there should be ZERO str() calls in tests for UUIDs
grep -r "str(claim\|str(chunk\|str(link\|str(issue\|str(gate" tests/
# Expected: No matches
```

---

## PHASE 2: PIPELINE STAGES ⏳ PENDING

**Objective**: Implement 11-stage pipeline with gates

| ID | Task | Status | Test Command | Notes |
|----|------|--------|--------------|-------|
| P2-001 | Create Stage 00: Bootstrap | [x] | `pytest tests/stages/test_00_bootstrap.py` | 12 tests pass |
| P2-002 | Create Stage 01: TermExpand | [x] | `pytest tests/stages/test_01_termexpand.py` | 12 tests pass |
| P2-003 | Create Stage 02: Retrieve | [x] | `pytest tests/stages/test_02_retrieve.py` | 12 tests pass |
| P2-004 | Create Stage 03: Chunk | [x] | `pytest tests/stages/test_03_chunk.py` | 13 tests pass |
| P2-005 | Create Stage 04: EvidenceNotes | [x] | `pytest tests/stages/test_04_evidencenotes.py` | 13 tests pass |
| P2-006 | Create Stage 05: Draft | [x] | `pytest tests/stages/test_05_draft.py` | 13 tests pass |
| P2-007 | Create Stage 06: ClaimExtract | [x] | `pytest tests/stages/test_06_claimextract.py` | 14 tests pass |
| P2-008 | Create Stage 07: Bind | [x] | `pytest tests/stages/test_07_bind.py` | 15 tests pass |
| P2-009 | Create Stage 08: Evals | [x] | `pytest tests/stages/test_08_evals.py` | 16 tests pass |
| P2-010 | Create Stage 09: ReviseLoop | [x] | `pytest tests/stages/test_09_reviseloop.py` | 13 tests pass |
| P2-011 | Create Stage 10: PackageRelease | [x] | `pytest tests/stages/test_10_package.py` | 14 tests pass |
| P2-012 | Wire stages into main pipeline | [x] | `pytest tests/test_pipeline.py -v` | 15 tests pass |

**Phase 2 Verification**:
```bash
pytest tests/stages/ -v && pytest tests/test_pipeline.py -v
# Expected: All stage tests pass, pipeline runs end-to-end
```

---

## PHASE 3: CLAIM SYSTEM ⏳ PENDING

**Objective**: Implement claim extraction, normalization, and binding

| ID | Task | Status | Test Command | Notes |
|----|------|--------|--------------|-------|
| P3-001 | Create ClaimExtractor class | [x] | `pytest tests/claims/test_extractor.py` | 27 tests pass |
| P3-002 | Implement DOSE extraction | [x] | `pytest tests/claims/test_dose.py` | 35 tests pass |
| P3-003 | Implement THRESHOLD extraction | [x] | `pytest tests/claims/test_threshold.py` | 35 tests pass |
| P3-004 | Implement RECOMMENDATION extraction | [x] | `pytest tests/claims/test_recommendation.py` | 36 tests pass |
| P3-005 | Implement CONTRAINDICATION extraction | [x] | `pytest tests/claims/test_contraindication.py` | 37 tests pass |
| P3-006 | Implement RED_FLAG extraction | [x] | `pytest tests/claims/test_redflag.py` | 37 tests pass |
| P3-007 | Implement ALGORITHM_STEP extraction | [x] | `pytest tests/claims/test_algorithmstep.py` | 33 tests pass |
| P3-008 | Create unit normalizer | [x] | `pytest tests/claims/test_normalizer.py` | 49 tests pass |
| P3-009 | Create EvidenceBinder class | [x] | `pytest tests/claims/test_binder.py` | 29 tests pass |
| P3-010 | Implement keyword binding | [x] | `pytest tests/claims/test_binder.py` | 29 tests pass (done in P3-009) |
| P3-011 | Implement semantic binding | [x] | `pytest tests/claims/test_binder.py` | 37 tests pass (8 new semantic) |
| P3-012 | Integration: extract + bind workflow | [x] | `pytest tests/claims/test_integration.py` | 16 tests pass (PHASE 3 COMPLETE) |

**Phase 3 Verification**:
```bash
pytest tests/claims/ -v
# Expected: All claim tests pass, 80%+ binding accuracy
```

---

## PHASE 4: EVAL SUITE ⏳ PENDING

**Objective**: Implement lints, gates, and issue tracking

| ID | Task | Status | Test Command | Notes |
|----|------|--------|--------------|-------|
| P4-001 | Create Linter base class | [x] | `pytest tests/evals/test_linter.py` | 18 tests pass |
| P4-002 | Implement citation_integrity lint | [ ] | `pytest tests/evals/test_citation.py` | [CIT-X] resolves |
| P4-003 | Implement template_compliance lint | [ ] | `pytest tests/evals/test_template.py` | 14 sections |
| P4-004 | Implement claim_coverage lint | [ ] | `pytest tests/evals/test_coverage.py` | All claims bound |
| P4-005 | Implement unit_check lint | [ ] | `pytest tests/evals/test_units.py` | Valid SI units |
| P4-006 | Implement overconfidence lint | [ ] | `pytest tests/evals/test_overconfidence.py` | Strong language check |
| P4-007 | Implement conflict_detection lint | [ ] | `pytest tests/evals/test_conflict.py` | Same topic conflicts |
| P4-008 | Implement recency_check lint | [ ] | `pytest tests/evals/test_recency.py` | >5 years flagged |
| P4-009 | Create GateEvaluator class | [ ] | `pytest tests/evals/test_gates.py` | Pass/fail logic |
| P4-010 | Implement S0 gate (safety) | [ ] | `pytest tests/evals/test_gates.py` | S0=0 required |
| P4-011 | Implement S1 gate (quality) | [ ] | `pytest tests/evals/test_gates.py` | S1=0 required |
| P4-012 | Create IssueCollector class | [ ] | `pytest tests/evals/test_issues.py` | Aggregate issues |

**Phase 4 Verification**:
```bash
pytest tests/evals/ -v
# Expected: All eval tests pass, gates block on S0/S1
```

---

## PHASE 5: API & BUNDLE ⏳ PENDING

**Objective**: Create new API endpoints and release bundle

| ID | Task | Status | Test Command | Notes |
|----|------|--------|--------------|-------|
| P5-001 | Create GET /api/runs/{id}/claims | [ ] | `pytest tests/api/test_claims_endpoint.py` | Return claims |
| P5-002 | Create GET /api/runs/{id}/issues | [ ] | `pytest tests/api/test_issues_endpoint.py` | Return issues |
| P5-003 | Create GET /api/runs/{id}/gates | [ ] | `pytest tests/api/test_gates_endpoint.py` | Return gate status |
| P5-004 | Create GET /api/runs/{id}/bundle | [ ] | `pytest tests/api/test_bundle_endpoint.py` | ZIP download |
| P5-005 | Create GET /api/runs/{id}/manifest | [ ] | `pytest tests/api/test_manifest_endpoint.py` | Checksums |
| P5-006 | Create GET /api/runs/{id}/evidence-notes | [ ] | `pytest tests/api/test_notes_endpoint.py` | LLM summaries |
| P5-007 | Create GET /api/runs/{id}/chunks | [ ] | `pytest tests/api/test_chunks_endpoint.py` | Evidence chunks |
| P5-008 | Implement ZipBuilder class | [ ] | `pytest tests/bundle/test_builder.py` | Create ZIP |
| P5-009 | Implement ManifestBuilder class | [ ] | `pytest tests/bundle/test_manifest.py` | Checksums, versions |
| P5-010 | Integration test: full bundle | [ ] | `pytest tests/integration/test_bundle.py` | End-to-end |
| P5-011 | Demo: "Anafylaksi behandling" | [ ] | Manual verification | Produces valid ZIP |
| P5-012 | Documentation: Danish audit guide | [ ] | File exists check | README.md |

**Phase 5 Verification**:
```bash
pytest tests/api/ tests/bundle/ -v
# Expected: All endpoint tests pass, demo ZIP valid
```

---

## FINAL VERIFICATION

After all phases complete:
```bash
# Run all tests
pytest tests/ -v

# Verify demo procedure
curl -X POST http://localhost:8000/api/write \
  -H "Content-Type: application/json" \
  -d '{"procedure_name": "Anafylaksi behandling"}'

# Download bundle
curl http://localhost:8000/api/runs/{run_id}/bundle -o release.zip

# Verify bundle contents
unzip -l release.zip
```

---

## TASK COUNT SUMMARY

| Phase | Total | Complete | Remaining |
|-------|-------|----------|-----------|
| P0: Validation | 7 | 7 | 0 |
| P1: Data Models | 12 | 12 | 0 |
| P2: Pipeline Stages | 12 | 12 | 0 |
| P3: Claim System | 12 | 12 | 0 |
| P4: Eval Suite | 12 | 1 | 11 |
| P5: API & Bundle | 12 | 0 | 12 |
| **TOTAL** | **67** | **44** | **23** |

---

**Next Task**: P4-002 - Implement citation_integrity lint
