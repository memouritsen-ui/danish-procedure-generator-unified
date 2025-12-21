# Danish Procedure Generator - Architecture

## Overview

This project consolidates 4 medical textbook generator projects into a unified system:

| Source Project | Contribution | Status |
|----------------|--------------|--------|
| akut-procedure-writer | Foundation, pipeline, DOCX export | ✅ Integrated |
| memouritsen/claudegithub | Multi-agent workflow, cost tracking | ✅ Complete |
| copilot-cli/danish_emergency_textbook | Quality loop, evidence hierarchy | ✅ Complete |
| danish-medical-platform | Archived (15 critical failures) | ❌ Not used |

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    UNIFIED SYSTEM v1.0                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Web UI    │  │   Desktop   │  │      REST API       │  │
│  │ React/Vite  │  │   Launcher  │  │      FastAPI        │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
│         │                │                     │             │
│         └────────────────┼─────────────────────┘             │
│                          ▼                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              ORCHESTRATOR (v2.0)                      │   │
│  │  - SQLite-backed job queue + worker                   │   │
│  │  - Quality loop (8/10 threshold)                      │   │
│  │  - Cost tracking per operation                        │   │
│  └───────────────────────┬──────────────────────────────┘   │
│                          ▼                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              AGENT CREW (5 agents) - v2.0             │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐              │   │
│  │  │Researcher│→│Validator │→│  Writer  │              │   │
│  │  └──────────┘ └──────────┘ └────┬─────┘              │   │
│  │                                  ▼                    │   │
│  │              ┌──────────┐ ┌──────────┐               │   │
│  │              │  Editor  │→│ Quality  │               │   │
│  │              └──────────┘ └──────────┘               │   │
│  └───────────────────────┬──────────────────────────────┘   │
│                          ▼                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                    PIPELINE (v1.0)                    │   │
│  │  - PubMed search (NCBI API)                          │   │
│  │  - International sources (SerpAPI Google Scholar)     │   │
│  │  - Source ingestion (PDF, DOCX, URL)                 │   │
│  │  - Citation validation (per-sentence)                │   │
│  │  - Evidence report (BM25 + embeddings)               │   │
│  │  - DOCX export (python-docx)                         │   │
│  └───────────────────────┬──────────────────────────────┘   │
│                          ▼                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              LLM PROVIDER (abstracted) - v2.0         │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐     │   │
│  │  │ OpenAI  │ │Anthropic│ │ Ollama  │ │ Future  │     │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘     │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                    DATA LAYER                         │   │
│  │  ┌─────────┐ ┌─────────────────────┐                  │   │
│  │  │ SQLite  │ │ Source Library      │                  │   │
│  │  │ (runs)  │ │ (SHA256 audit)      │                  │   │
│  │  └─────────┘ └─────────────────────┘                  │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
danish-procedure-generator-unified/
├── backend/
│   ├── procedurewriter/          # Main Python package
│   │   ├── __init__.py
│   │   ├── main.py               # FastAPI application
│   │   ├── db.py                 # SQLite database
│   │   ├── settings.py           # Configuration
│   │   ├── schemas.py            # Pydantic models
│   │   ├── pipeline/             # Generation pipeline
│   │   │   ├── run.py            # Main pipeline orchestration
│   │   │   ├── pubmed.py         # NCBI/PubMed integration
│   │   │   ├── retrieve.py       # Source retrieval (BM25/embeddings)
│   │   │   ├── writer.py         # LLM text generation
│   │   │   ├── citations.py      # Citation validation
│   │   │   ├── evidence.py       # Evidence report generation
│   │   │   ├── docx_writer.py    # DOCX export
│   │   │   └── manifest.py       # Audit trail manifests
│   │   ├── agents/               # Multi-agent system (v2.0)
│   │   │   ├── __init__.py
│   │   │   ├── base.py           # Agent base class
│   │   │   ├── researcher.py     # PubMed research agent
│   │   │   ├── validator.py      # Claim validation agent
│   │   │   ├── writer.py         # Content writing agent
│   │   │   ├── editor.py         # Editorial agent
│   │   │   └── quality.py        # Quality scoring agent
│   │   ├── llm/                  # LLM providers (v2.0)
│   │   │   ├── __init__.py
│   │   │   ├── providers.py      # Provider abstraction
│   │   │   └── cost_tracker.py   # Token/cost tracking
│   │   └── crew.py               # CrewAI orchestration (v2.0)
│   ├── tests/                    # Test suite
│   ├── pyproject.toml            # Python config
│   └── requirements.txt
├── frontend/                     # React/Vite UI
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   └── main.tsx
│   └── package.json
├── config/
│   ├── author_guide.yaml         # Writing style configuration
│   ├── source_allowlist.yaml     # Allowed source URLs
│   └── evidence_hierarchy.yaml   # Danish evidence priority (v2.0)
├── data/                         # Runtime data (gitignored)
│   ├── index/                    # SQLite database
│   └── runs/                     # Generated procedure outputs
├── scripts/
│   ├── bootstrap                 # Install dependencies
│   ├── boot                      # All-in-one launcher
│   └── create_desktop_icon_macos
├── README.md
├── ARCHITECTURE.md               # This file
├── Makefile
└── .gitignore
```

## MVP Features (v1.0)

| # | Feature | Description | Status |
|---|---------|-------------|--------|
| 1 | Generation Pipeline | Single procedure → DOCX with citations | ✅ Working |
| 2 | Source Audit Trail | SHA256 hashes, evidence reports, manifests | ✅ Working |
| 3 | PubMed Integration | Real NCBI API, ranked results | ✅ Working |
| 4 | PDF/DOCX Ingestion | Upload and extract source documents | ✅ Working |
| 5 | Citation Validation | Per-sentence citation checking | ✅ Working |

## v2.0 Features (Complete)

| # | Feature | Status | Source |
|---|---------|--------|--------|
| 1 | LLM Provider Abstraction | ✅ | claudegithub |
| 2 | Multi-Agent Workflow | ✅ | claudegithub |
| 3 | Quality Control Loop | ✅ | copilot-cli |
| 4 | Cost Tracking | ✅ | claudegithub |
| 5 | Danish Evidence Hierarchy | ✅ | copilot-cli |
| 6 | E2E Testing (25 tests) | ✅ | Sprint 6 |
| 7 | Performance Profiling | ✅ | Sprint 6 |

## Implementation Sprints

### Sprint 0: Setup (Complete) ✅
- [x] Create new git repo
- [x] Copy akut-procedure-writer as base
- [x] Remove old branding
- [x] Add ARCHITECTURE.md
- [x] Archive danish-medical-platform

### Sprint 1: LLM Provider Abstraction ✅
- [x] Create provider interface (OpenAI, Anthropic, Ollama)
- [x] Add environment variable configuration
- [x] Update pipeline to use abstraction
- [x] Write tests for provider switching

### Sprint 2: Multi-Agent Workflow ✅
- [x] Port agent base class from claudegithub
- [x] Implement 5 agents (Researcher, Validator, Writer, Editor, Quality)
- [x] Integrate CrewAI orchestration
- [x] Update pipeline to use agents

### Sprint 3: Quality Control Loop ✅
- [x] Add iteration logic (max 3)
- [x] Extract quality score from agent output
- [x] Re-run if score < 8
- [x] Store iteration count in DB

### Sprint 4: Cost Tracking ✅
- [x] Port cost tracker from claudegithub
- [x] Add token counting to providers
- [x] Create cost API endpoint
- [x] Display in UI

### Sprint 5: Danish Evidence Hierarchy ✅
- [x] Create evidence_hierarchy.yaml
- [x] Implement priority search order
- [x] Add evidence badges to output
- [x] Write tests

### Sprint 6: Integration & Polish ✅
- [x] End-to-end testing (25 tests)
- [x] Performance profiling (pipeline profiler)
- [x] Documentation update
- [x] Security review

## Tech Stack

### Backend
- **Framework:** FastAPI 0.115+
- **Database:** SQLite3
- **LLM:** OpenAI (configurable)
- **Document:** python-docx, pypdf
- **Search:** NCBI E-utilities (PubMed)
- **Testing:** pytest

### Frontend
- **Framework:** React 18.3
- **Build:** Vite 5.4
- **Language:** TypeScript
- **Router:** React Router 6

### Agents (v2.0)
- **Framework:** CrewAI
- **Workflow:** Sequential (research→validate→write→edit→quality)
- **Quality:** 8/10 threshold, max 3 iterations

## Kill Criteria

Stop and re-evaluate if:
- Sprint fails acceptance criteria 2x in a row
- Total effort exceeds 6 weeks
- Integration creates >5 new bugs

## Project Decisions

### Why akut-procedure-writer as foundation?
- Clean, focused codebase (~3,500 lines)
- Actually works with zero critical bugs
- Good patterns: SHA256 audit, evidence reports
- Simple SQLite, no complex infrastructure

### Why not salvage danish-medical-platform?
- 15+ critical failures documented
- Syntax error blocks startup
- Over-engineered (5 systems in one)
- Root cause: abandoned mid-execution

### Why port agents from claudegithub?
- Well-designed 7-agent system
- Real PubMed integration
- LangGraph workflow tested
- Cost tracking implemented

### Why not use Ollama by default?
- Quality ceiling: 8-9/10 (vs 9-9.5/10 with cloud)
- Requires 50GB+ disk, 16GB+ RAM
- Cloud APIs more accessible for most users
- Ollama kept as option via provider abstraction

## Security Considerations

### Implemented (v2.0)
| Protection | Implementation | File |
|------------|---------------|------|
| SQL Injection | Parameterized queries (?) | db.py |
| Path Traversal | safe_path_within() validation | file_utils.py, main.py |
| URL Allowlist | Prefix validation before fetch | main.py:api_ingest_url |
| API Key Storage | Local SQLite only | db.py:secrets table |
| API Key Display | Masked output (sk-…1234) | db.py:mask_secret |
| YAML Injection | safe_load() only | config_store.py |
| CORS | Localhost origins only | main.py |
| XSS | No user HTML rendering | N/A |

### Design Decisions
- **No auth**: Local-only application, assumes trusted user
- **Plaintext keys**: SQLite file permissions are sufficient for local use
- **No rate limiting**: Local use doesn't require it

### Planned (v3.0+)
- Connection pooling
- Request logging
- Secrets encryption at rest (for cloud deployment)

## Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| Single procedure generation | <5 min | ~3-5 min |
| DOCX export | <10 sec | ~2-3 sec |
| PubMed search | <30 sec | ~10-20 sec |
| Quality score | ≥8/10 | ✅ Implemented |
| Pipeline (dummy mode) | <100ms | ~33-59ms |
| HTTP client init | <50ms | ~35ms |
| Test suite (136 tests) | <30s | ~15s |

## Contributing

1. Check sprint plan for current tasks
2. Follow existing code patterns
3. Add tests for new features
4. Update this document for architectural changes
