# Danish Procedure Generator - Architecture

## Overview

This project consolidates 4 medical textbook generator projects into a unified system:

| Source Project | Contribution | Status |
|----------------|--------------|--------|
| akut-procedure-writer | Foundation, pipeline, DOCX export | ✅ Integrated |
| memouritsen/claudegithub | Multi-agent workflow, cost tracking | 🔄 Sprint 1-4 |
| copilot-cli/danish_emergency_textbook | Quality loop, evidence hierarchy | 🔄 Sprint 3,5 |
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
│  │  - Task queue with Redis                              │   │
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
│  │  ┌─────────┐ ┌─────────┐ ┌─────────────────────┐     │   │
│  │  │ SQLite  │ │  Redis  │ │ Source Library      │     │   │
│  │  │ (runs)  │ │ (tasks) │ │ (SHA256 audit)      │     │   │
│  │  └─────────┘ └─────────┘ └─────────────────────┘     │   │
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

## Planned Features (v2.0)

| # | Feature | Sprint | Source |
|---|---------|--------|--------|
| 1 | LLM Provider Abstraction | Sprint 1 | claudegithub |
| 2 | Multi-Agent Workflow | Sprint 2 | claudegithub |
| 3 | Quality Control Loop | Sprint 3 | copilot-cli |
| 4 | Cost Tracking | Sprint 4 | claudegithub |
| 5 | Danish Evidence Hierarchy | Sprint 5 | copilot-cli |

## Implementation Sprints

### Sprint 0: Setup (Complete) ✅
- [x] Create new git repo
- [x] Copy akut-procedure-writer as base
- [x] Remove old branding
- [x] Add ARCHITECTURE.md
- [x] Archive danish-medical-platform

### Sprint 1: LLM Provider Abstraction (3 days)
- [ ] Create provider interface (OpenAI, Anthropic, Ollama)
- [ ] Add environment variable configuration
- [ ] Update pipeline to use abstraction
- [ ] Write tests for provider switching

### Sprint 2: Multi-Agent Workflow (5 days)
- [ ] Port agent base class from claudegithub
- [ ] Implement 5 agents (Researcher, Validator, Writer, Editor, Quality)
- [ ] Integrate CrewAI orchestration
- [ ] Update pipeline to use agents

### Sprint 3: Quality Control Loop (2 days)
- [ ] Add iteration logic (max 3)
- [ ] Extract quality score from agent output
- [ ] Re-run if score < 8
- [ ] Store iteration count in DB

### Sprint 4: Cost Tracking (2 days)
- [x] Port cost tracker from claudegithub
- [x] Add token counting to providers
- [x] Create cost API endpoint
- [x] Display in UI

### Sprint 5: Danish Evidence Hierarchy (1 day)
- [ ] Create evidence_hierarchy.yaml
- [ ] Implement priority search order
- [ ] Add evidence badges to output
- [ ] Write tests

### Sprint 6: Integration & Polish (3 days)
- [ ] End-to-end testing
- [ ] Performance profiling
- [ ] Documentation update
- [ ] Security review

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

### Current (v1.0)
- API keys stored in SQLite (local only)
- URL allowlist validation
- Path traversal protection
- No authentication (local use assumed)

### Planned (v2.0+)
- Connection pooling
- Rate limiting
- Request logging
- Secrets encryption at rest

## Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| Single procedure generation | <5 min | ~3-5 min |
| DOCX export | <10 sec | ~2-3 sec |
| PubMed search | <30 sec | ~10-20 sec |
| Quality score | ≥8/10 | N/A (v2.0) |

## Contributing

1. Check sprint plan for current tasks
2. Follow existing code patterns
3. Add tests for new features
4. Update this document for architectural changes
