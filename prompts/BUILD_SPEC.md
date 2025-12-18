# BUILD SPEC — Akutmedicinsk procedureskriver (DK) + fuldt funktionelt UI (lokal webapp)

## 1) Formål
Givet et procedure-navn (prompt), skal systemet:
1) finde/hente reelle kilder (guidelines + systematiske reviews først),
2) gemme rådata + metadata lokalt med hashes (audit trail),
3) skrive et dansk procedure-afsnit efter en redigerbar forfattervejledning,
4) eksportere som .docx med sporbare citations-id’er,
5) tilbyde et fuldt funktionelt UI (lokal browser) til at køre, styre, inspicere og downloade resultaterne.

## 2) Ikke-forhandlingsbare krav (sandhed & sporbarhed)
- Ingen hallucinerede kilder: Writer må KUN citere `source_id` fra lokalt registrerede kilder (sources.jsonl i run-folder).
- Hver sætning i den genererede proceduretekst skal have mindst én citations-tag: `[S:<source_id>]`.
- For hver kilde gemmes:
  - hentetidspunkt (UTC), url/doi/pmid hvis tilgængeligt
  - raw_content SHA-256 + normalized_text SHA-256
  - lokal filsti til raw + normalized
  - extraction-notes + “terms/licence note” (kort tekstfelt)
- Hvis evidens mangler/er svag: skriv det eksplicit i output.

## 3) Arkitektur (monorepo)
/backend  (Python: FastAPI + pipeline + audit + docx)
/frontend (React/Vite UI)
/config   (author_guide.yaml, source_allowlist.yaml)
/data     (gitignored: runs, cache, index, uploads)
/scripts  (check/dev/build)
/docs

## 4) Backend (Python)
### 4.1 API (FastAPI)
Endpoints (minimum):
- POST /api/write
  input: { procedure: str, context?: str }
  output: { run_id: str }
- GET /api/runs
- GET /api/runs/{run_id}
- GET /api/runs/{run_id}/docx   (download)
- GET /api/runs/{run_id}/sources (liste)
- POST /api/ingest/pdf          (upload pdf)
- POST /api/ingest/url          (fetch url -> raw)

Jobmodel:
- /api/write starter en background-job (async) og opdaterer run-status i SQLite.
- UI poller /api/runs/{run_id} til DONE/FAILED.

### 4.2 Kilde-indsamling (runtime)
Tier 1:
- PubMed via NCBI E-utilities (ESearch + EFetch) til abstracts/metadata.
- Guideline-URL’er kun fra allowlist (config/source_allowlist.yaml).
- Bruger-uploadede PDF’er/URL’er (ingest).

Tier 2 (valgfrit):
- Crossref metadata via DOI (hvis DOI findes).

Politik:
- Ingen login/paywall scraping.
- Respektér robots/terms i praksis (ingen aggressiv crawling).
- Cache alle fetches lokalt pr. URL.

### 4.3 Normalisering
- HTML -> tekst (fjern nav, scripts; behold headings/lister så godt som muligt).
- PDF -> tekst (udtræk sidevis; gem også sideinddeling hvis muligt).
- Producer “normalized.txt” pr. kilde.

### 4.4 Indeksering / retrieval
- Primær: embeddings-baseret indeks hvis OPENAI_API_KEY findes (brug OpenAI embeddings).
- Fallback: lexical retrieval (BM25/TF-IDF) uden eksterne keys.
- Retrieval skal returnere “snippets” med source_id og (hvis muligt) side/sektion.

### 4.5 Writer
- Input: procedure-navn + author_guide.yaml + top-k retrieval snippets.
- Output: dansk proceduretekst med citations-tags [S:...] per sætning.
- En “citation validator” skal fejle run’et hvis:
  - en sætning mangler [S:...]
  - et source_id ikke findes i sources.jsonl
- Output gemmes som:
  - procedure.md
  - procedure.docx (via python-docx)
  - run_manifest.json (hashes, config snapshot, timestamps)

## 5) DOCX
- Generér Procedure.docx med:
  - Titel, indhold
  - “Referencer” sektion: mapping fra source_id -> metadata (titel/år/url/doi/pmid)
  - Audit footer: run_id + timestamp + manifest-hash

## 6) UI (fuldt funktionelt, minimalistisk)
Teknologi: React + Vite + router.

Sider:
1) “Skriv procedure”
   - Input: procedure-navn + valgfri kontekst
   - Knap: Generér
   - Status (spinner) + preview af resultat (render markdown)
   - Knap: Download DOCX
   - Kildeliste (klik -> metadata)
2) “Runs”
   - Liste over runs (tid, procedure, status) + åbning af audit + docx download
3) “Kilder”
   - Browse sources fra et valgt run (metadata + hashes + lokale paths)
4) “Indstillinger”
   - Redigér `config/author_guide.yaml` og `config/source_allowlist.yaml` i UI (textarea + save via API)
5) “Ingest”
   - Upload PDF eller indtast URL og ingest den

## 7) Dev UX + kvalitet
- Makefile eller scripts:
  - make dev  (backend + frontend hot reload)
  - make check (python lint/type/test + frontend lint/build)
  - make build (frontend build -> backend static)
- Backend tests (minimum):
  - PubMed client (mock HTTP)
  - normalizer (fixture)
  - citation validator
  - docx writer smoke
- Frontend:
  - mindst `npm run build` skal passere (lint/test hvis let).

## 8) Done-definition (må ikke afleveres uden dette)
- `make check` passerer.
- `make dev` starter og UI kan generere en docx i “dummy mode” (uden API keys).
- Sidste svar fra Codex skal slutte med: FINAL_OK
