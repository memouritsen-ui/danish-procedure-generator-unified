# Danish Procedure Generator - Project Instructions

---

## ⚠️ CRITICAL: SESSION START PROTOCOL

**BEFORE DOING ANY WORK, YOU MUST:**

1. **READ BUILD CONTROL DOCUMENTS** (in order):
   ```
   Read: backend/.claude/STATE.md   → Current project state
   Read: backend/.claude/TASKS.md   → Find next task
   Read: backend/.claude/BUILD.md   → Project context (if needed)
   ```

2. **VERIFY TEST STATUS**:
   ```bash
   cd backend && source .venv/bin/activate && pytest tests/ -x -q
   ```

3. **CHECK GIT STATUS**:
   ```bash
   git status && git log --oneline -3
   ```

4. **FIND CURRENT TASK** in TASKS.md and continue from there

**DO NOT:**
- Skip ahead in the task sequence
- Mark tasks complete without running tests
- Make changes without reading STATE.md first
- Forget to update STATE.md after completing tasks
- Start new tasks with uncommitted changes
- Apply band-aid fixes (see ANTI-PATTERNS in TASKS.md)
- Retrofit tests to match implementation (TDD means tests define interface)

---

## 🛑 DESIGN BEFORE FIX

**When tests fail, DO NOT immediately fix the symptom.**

```
┌─────────────────────────────────────────────────────────────┐
│  WHEN TESTS FAIL - FOLLOW THIS SEQUENCE                    │
├─────────────────────────────────────────────────────────────┤
│  1. STOP - Don't change anything yet                       │
│  2. READ the error message completely                      │
│  3. ASK: Is this a design problem or implementation bug?   │
│  4. If DESIGN: Fix in ONE place (add abstraction/method)   │
│  5. If IMPLEMENTATION: Fix the specific bug                │
│  6. Run tests ONCE                                         │
│  7. If still failing, use systematic-debugging skill       │
└─────────────────────────────────────────────────────────────┘
```

**Red Flags (STOP if you see these):**
- Adding the same fix in 5+ places → Need abstraction
- Changing test to match implementation → TDD is backwards
- Modified same file 3+ times → Guessing, not understanding
- Using `str()` or type conversions scattered everywhere → Need conversion layer

**Correct Response:**
```bash
# Use the skill
Skill(superpowers:systematic-debugging)
```

---

## 🔁 MANDATORY: TASK COMPLETION PROTOCOL

After completing EVERY task, you MUST execute this 6-step sequence:

```
┌─────────────────────────────────────────────────────────────┐
│  AFTER EVERY TASK (NO EXCEPTIONS)                          │
├─────────────────────────────────────────────────────────────┤
│  1. pytest tests/ -x -q                    # All tests pass │
│  2. Mark [x] in TASKS.md with test count                   │
│  3. Update STATE.md (current task → next task)             │
│  4. git add . && git commit -m "feat: P#-###: desc"        │
│  5. git push                                               │
│  6. RE-READ THIS FILE (CLAUDE.md)          # CRITICAL!     │
└─────────────────────────────────────────────────────────────┘
```

**Why Step 6 (Re-read CLAUDE.md)?**
- Long tasks cause context drift
- Rules get forgotten mid-session
- Re-reading resets your understanding of project constraints
- This is how session-persistent memory works

**Verification**: After re-reading, you should be able to state:
- Current phase and task number
- What the next task is
- That git status is clean

---

## 🔄 ACTIVE REFACTORING: Auditable Medical Build System

**Current Phase**: Phase 1 HOTFIX - Architectural Debt (BLOCKING)
**Phase 0 Status**: COMPLETE (Claim extraction feasibility proven)
**Phase 1 Status**: COMPLETE but with debt (12/12 tasks, 113 tests, 3646 lines)
**Phase 1 HOTFIX**: 8 tasks to fix UUID handling and add conversion layer
**Phase 2 Status**: BLOCKED until hotfix complete

**Target Architecture**: 11-stage pipeline with claim traceability
```
00 Bootstrap → 01 TermExpand → 02 Retrieve → 03 Chunk →
04 EvidenceNotes → 05 Draft → 06 ClaimExtract → 07 Bind →
08 Evals → 09 ReviseLoop → 10 PackageRelease
```

**Control Documents**:
| Document | Purpose |
|----------|---------|
| `backend/.claude/BUILD.md` | Master build context, API inventory, LLM config |
| `backend/.claude/STATE.md` | Current state, recent completions, blocked tasks |
| `backend/.claude/TASKS.md` | Numbered task checklist with test commands |

---

## 🛠️ TOOL USAGE REMINDERS

**For Code Search** (not grep/find):
```
Task(subagent_type="Explore", prompt="Find X in codebase")
```

**For Symbolic Navigation**:
```
mcp__plugin_serena_serena__find_symbol(name_path="ClassName/method")
mcp__plugin_serena_serena__get_symbols_overview(relative_path="file.py")
```

**For File Operations** (not cat/sed/echo):
```
Read(file_path="/absolute/path")
Edit(file_path, old_string, new_string)
Write(file_path, content)
```

**For Testing**:
```bash
pytest tests/ -x -q           # All tests, stop on first failure
pytest tests/file.py -v       # Single file
pytest -k "test_name" -v      # By name pattern
```

---

## Overview

Evidence-based Danish medical emergency procedure generator using a 5-agent LLM pipeline with meta-analysis capabilities.

## Critical Functionality (NEVER BREAK)

1. **5-Agent Pipeline:** Researcher → Writer → Validator → Editor → Quality
2. **Evidence Hierarchy:** 10 tiers, Danish guidelines priority 1000
3. **Quality Loop:** Score threshold 8/10, max 3 iterations
4. **Source Fetching:** PubMed, NICE, WHO, Danish guidelines
5. **DOCX Generation:** With citations and proper formatting

## Architecture

```
frontend/ (React 18 + TypeScript + Vite)
backend/
├── procedurewriter/
│   ├── main.py           # FastAPI app
│   ├── routers/          # API endpoint modules
│   ├── agents/           # 5 core + meta-analysis agents
│   ├── pipeline/         # Orchestration
│   │   ├── stages/       # Pipeline stages
│   │   └── context.py    # Shared state
│   ├── llm/              # Provider abstraction
│   └── db.py             # SQLite + encryption
├── tests/                # 77 test files
└── config/               # YAML configurations
```

## Development Rules

### Testing
- TDD required: Write test first, watch it fail, implement, verify pass
- Run before commit: `cd backend && pytest tests/ -x -q`
- Integration test after major changes: Generate "Anafylaksi behandling" procedure

### Security
- API keys MUST be encrypted (use crypto.py)
- Set PROCEDUREWRITER_SECRET_KEY environment variable
- Never log or print API keys

### Code Quality
- No bare `except Exception:` - use specific exceptions
- Each file under 500 lines (split if larger)
- Type hints required

### Git
- Commit after each task completes
- Format: `<type>: <description>`
- Types: feat, fix, refactor, test, docs

## Commands

```bash
# Activate environment
cd backend && source .venv/bin/activate

# Run tests
pytest tests/ -v

# Run single test file
pytest tests/test_agents.py -v

# Start backend
uvicorn procedurewriter.main:app --reload --port 8000

# Start frontend
cd frontend && npm run dev

# Generate encryption key
python -c "import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
```

## Key Files

| File | Purpose | Max Lines |
|------|---------|-----------|
| main.py | App setup, routers | 300 |
| pipeline/run.py | Stage orchestration | 200 |
| agents/orchestrator.py | Agent coordination | 500 |
| db.py | Database operations | 1000 |

## Evidence Hierarchy

| Tier | Source Type | Priority |
|------|-------------|----------|
| 1 | Danish Guidelines | 1000 |
| 2 | Nordic Guidelines | 900 |
| 3 | European Guidelines | 850 |
| 4 | International (NICE/WHO) | 800 |
| 5 | Systematic Reviews | 700 |
| 6 | Practice Guidelines | 650 |
| 7 | RCTs | 500 |
| 8 | Observational | 300 |
| 9 | Case Reports | 150 |
| 10 | Unclassified | 100 |

## Configuration Files

- `config/author_guide.yaml` - Writing style, Danish language
- `config/evidence_hierarchy.yaml` - Source tier definitions
- `config/source_allowlist.yaml` - Allowed URL prefixes
- `config/docx_template.yaml` - Document formatting
- `config/procedure_types.yaml` - Anatomical requirements

## Refactoring Plan

See: `docs/plans/2025-06-21-full-remediation-plan.md`

### Phase 1: Security (P0)
- Encrypt API keys in database

### Phase 2: Router Split (P1)
- Split main.py into 8 routers

### Phase 3: Pipeline Split (P1)
- Split run.py into 6 stages

### Phase 4: Exception Handling (P2)
- Replace blind exception handlers

## Troubleshooting

### Tests fail with "No module named"
```bash
cd backend && pip install -e .
```

### API key not working
```bash
# Check if key is set
python -c "from procedurewriter.db import get_secret; from procedurewriter.settings import settings; print(get_secret(settings.db_path, name='openai_api_key'))"
```

### Database errors
```bash
# Reinitialize database
rm backend/data/procedurewriter.db
python -c "from procedurewriter.db import init_db; from procedurewriter.settings import settings; init_db(settings.db_path)"
```
