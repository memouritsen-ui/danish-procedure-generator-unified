# Danish Procedure Generator - Project Instructions

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
├── tests/                # 66 test files
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
