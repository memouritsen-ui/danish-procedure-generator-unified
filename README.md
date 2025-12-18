# Danish Procedure Generator

Unified system for generating Danish emergency medicine procedures with evidence-based citations, source audit trails, and DOCX export.

## Overview

This project consolidates the best features from multiple Danish medical textbook projects:
- **Foundation:** akut-procedure-writer (clean, working baseline)
- **Agents:** Multi-agent workflow from claudegithub
- **Quality Loop:** Automatic revision from copilot-cli

See `ARCHITECTURE.md` for the full technical design.

## Quick Start

### Prerequisites
- Python 3.11+
- Node 18+

### Installation
```bash
./scripts/bootstrap
```

### Run
```bash
make dev          # Backend + frontend dev server
make check        # Lint/type/test + frontend build
make build        # Build frontend to backend static
./scripts/boot    # All-in-one: bootstrap + check + start UI
```

Backend API: `http://127.0.0.1:8000`
Frontend dev: `http://127.0.0.1:5173`

## Desktop Launcher (macOS)

```bash
./scripts/create_desktop_icon_macos
```

Creates:
- `~/Desktop/Danish Procedure Generator.app`
- `~/Desktop/Danish Procedure Generator.command`

## Configuration

### API Keys
Set in UI under "Settings" → "API keys":
- **OpenAI API key** (required for LLM generation)
- **NCBI API key** (optional, reduces PubMed rate limits)

Keys are stored locally in SQLite database under `data/index` (gitignored).

### Guideline Seed URLs
Add fixed guideline URLs in `config/source_allowlist.yaml` under `seed_urls`.
Only URLs matching `allowed_url_prefixes` are fetched.

### Dummy Mode
```bash
PROCEDUREWRITER_DUMMY_MODE=1 make dev
```
Generates demo procedures without external API keys.

## Features

### Current (v2.0)
- Single procedure → DOCX with citations
- Real PubMed integration (NCBI API)
- PDF/DOCX/URL source ingestion
- Source audit trail (SHA256 hashes)
- Evidence reports (BM25 + embeddings)
- Citation validation (per-sentence)
- **LLM Provider Abstraction:** OpenAI, Anthropic (Claude), Ollama (local)
- **Cost Tracking:** Per-operation token usage and cost tracking
- **Danish Evidence Hierarchy:** Priority ranking (DK Guidelines → Nordic → EU → International)
- **Quality Loop:** Automatic scoring based on evidence coverage
- **Multi-agent Workflow:** Researcher, Writer, Validator, Editor, Quality agents

### Evidence Hierarchy
Sources are automatically classified and prioritized:

| Level | Priority | Badge | Examples |
|-------|----------|-------|----------|
| Danish Guidelines | 1000 | DK Guideline | sst.dk, dsam.dk, sundhed.dk |
| Nordic Guidelines | 900 | Nordic | socialstyrelsen.se, helsedirektoratet.no |
| European Guidelines | 850 | EU Guideline | escardio.org, esmo.org |
| International Guidelines | 800 | Intl Guideline | nice.org.uk, who.int |
| Systematic Reviews | 700 | Syst Review | PubMed systematic reviews |
| Practice Guidelines | 650 | Practice GL | PubMed practice guidelines |
| RCTs | 500 | RCT | PubMed randomized trials |
| Observational | 300 | Observational | Cohort/case-control studies |
| Unclassified | 50 | Kilde | Other sources |

Configure in `config/evidence_hierarchy.yaml`.

## API Endpoints

### Core Endpoints
| Endpoint | Description |
|----------|-------------|
| `GET /api/status` | Application status and configuration |
| `GET /api/runs` | List all runs |
| `POST /api/write` | Start new procedure generation |
| `GET /api/runs/{id}` | Get run status and quality score |
| `GET /api/runs/{id}/manifest` | Get run manifest (audit trail) |
| `GET /api/runs/{id}/bundle` | Download ZIP bundle |
| `GET /api/runs/{id}/sources` | Get source list with evidence badges |
| `GET /api/runs/{id}/evidence` | Get evidence report |
| `GET /api/costs` | Aggregated cost summary |

### Configuration
| Endpoint | Description |
|----------|-------------|
| `GET/PUT /api/config/author_guide` | Author guide YAML |
| `GET/PUT /api/config/source_allowlist` | Source allowlist YAML |

### API Keys
| Endpoint | Description |
|----------|-------------|
| `GET/PUT/DELETE /api/keys/openai` | OpenAI API key |
| `GET/PUT/DELETE /api/keys/anthropic` | Anthropic API key |
| `GET/PUT/DELETE /api/keys/ncbi` | NCBI API key |
| `GET /api/keys/{provider}/status` | Verify key validity |

### Document Ingestion
| Endpoint | Description |
|----------|-------------|
| `POST /api/ingest/pdf` | Upload PDF to library |
| `POST /api/ingest/docx` | Upload DOCX to library |
| `POST /api/ingest/url` | Ingest URL to library |

## Project Structure

```
├── backend/
│   └── procedurewriter/     # Python backend (FastAPI)
│       ├── pipeline/        # Generation pipeline
│       ├── agents/          # Agent definitions (v2.0)
│       └── llm/             # LLM providers (v2.0)
├── frontend/                # React/Vite UI
├── config/                  # YAML configuration
├── data/                    # Runtime data (gitignored)
├── scripts/                 # Build/run scripts
└── ARCHITECTURE.md          # Technical design
```

## License

MIT
