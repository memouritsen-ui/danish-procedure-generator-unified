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

### Current (v1.0)
- Single procedure → DOCX with citations
- Real PubMed integration (NCBI API)
- PDF/DOCX/URL source ingestion
- Source audit trail (SHA256 hashes)
- Evidence reports (BM25 + embeddings)
- Citation validation (per-sentence)

### Planned (v2.0)
- Multi-agent workflow (5 agents)
- Quality control loop (8/10 threshold)
- LLM provider abstraction (OpenAI/Anthropic/Ollama)
- Cost tracking per operation
- Danish evidence hierarchy (SST→DASEM→ERC→ILCOR)

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/runs` | List all runs |
| `POST /api/write` | Start new procedure generation |
| `GET /api/runs/{id}` | Get run status |
| `GET /api/runs/{id}/manifest` | Get run manifest (audit trail) |
| `GET /api/runs/{id}/bundle` | Download ZIP bundle |

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
