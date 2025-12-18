# Build Plan (maksimalt optimeret): Brug af `guideline_harvester`-bibliotek i Akut Procedure Writer

Denne plan er skrevet til at kunne overtages uden anden kontekst end selve repos (og en lokal guideline-harvester library-folder). Den beskriver:
- Hvordan programmet fungerer i dag (backend, frontend, pipeline, data/DB).
- Hvad `guideline_harvester/library` indeholder, og hvilke faldgruber der er.
- En **optimeret** arkitektur og implementeringsplan for at bruge et stort lokalt guideline-korpus sammen med PubMed og uploads.

Målgruppen er den/de udviklere som skal implementere integrationen.

---

## 0) Executive summary

Du har et lokalt korpus i `~/guideline_harvester/library` (ca. 4,4 GB / ~53k `extracted_text.txt`). Det **kan** bruges som kilder i Akut Procedure Writer, men det kræver en integration, der:
- **ikke** propper hele korpuset ind i hvert run (run-størrelse/runtimes eksploderer),
- laver **hurtig dokument-udvælgelse** (candidate search) + **snippets retrieval** over et lille udsnit,
- og bevarer eksisterende “audit trail” + citations-regler: *kun* citer `[S:<source_id>]` som findes i run’ets `sources.jsonl`, og *hver sætning* skal have mindst én citation.

Anbefalet (hurtigst + mest skalerbar):
1) Behandl `guideline_harvester/library` som et **eksternt corpus** (ingen fuld import til appens DB).
2) Brug en **2-trins retrieval**:
   - Trin A: hurtig “candidate document retrieval” (SQLite FTS hvis muligt, ellers fallback).
   - Trin B: chunk+rank kun på de top-N docs (BM25 lokalt, evt. embeddings refinement hvis OpenAI key findes).
3) Kun de **valgte** documents konverteres til run-`SourceRecord`s og kopieres til run-folder.
4) PubMed forbliver en sekundær kanal (supplerende evidens), men kan kombineres i retrieval.

---

## 1) Ikke-forhandlingsbare krav (fra programmet)

Disse krav er allerede kodet ind i pipeline og må ikke kompromitteres:
- **Ingen hallucinerede kilder**: Writer må kun citere source_id’er, der findes i run’ets `sources.jsonl`.
- **Per-sætning citation**: Citation-validatoren (`backend/akutwriter/pipeline/citations.py`) fejler run’et hvis en “sætning” mangler `[S:...]`.
- **Audit trail**: For hver source i `sources.jsonl` gemmes paths + SHA256 for raw og normalized tekst.
- **Tydelig usikkerhed**: Hvis evidence ikke dækker, skal output sige det eksplicit (writer prompts håndhæver det; evidens-check kan sættes til warn/strict i `config/author_guide.yaml`).

---

## 2) Program-overblik (Akut Procedure Writer)

### 2.1 Repo-struktur

`akut-procedure-writer/`:
- `backend/` (FastAPI + pipeline + SQLite)
- `frontend/` (React/Vite UI)
- `config/` (editable YAML i UI)
- `data/` (gitignored: runs, cache, index DB, uploads)
- `scripts/`, `Makefile`, `README.md`

### 2.2 Lokal kørsel (dev UX)

Fra `akut-procedure-writer/README.md`:
- `./scripts/bootstrap`
- `make dev`
- `make check`
- Backend: `http://127.0.0.1:8000`, frontend dev: `http://127.0.0.1:5173`

### 2.3 Data og DB

`backend/akutwriter/settings.py`:
- DB: `data/index/runs.sqlite3`
- Runs: `data/runs/<run_id>/...`
- Uploads: `data/uploads/`
- Cache: `data/cache/`

DB schema (`backend/akutwriter/db.py`):
- `runs`: status, paths, error
- `library_sources`: bruger-ingestede kilder (pdf/docx/url) + metadata/hashes
- `secrets`: OpenAI/NCBI keys (lokalt)

### 2.4 API (relevant for integration)

Backend (`backend/akutwriter/main.py`, `backend/akutwriter/schemas.py`):
- `POST /api/write` → starter run (background task)
- `GET /api/runs`, `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/sources`
- `POST /api/ingest/pdf|docx|url` → tilføjer rows i `library_sources`
- `GET/PUT /api/config/author_guide`, `GET/PUT /api/config/source_allowlist`
- `GET/PUT/DELETE /api/keys/openai`, `.../ncbi` + `/status`
- `GET /api/runs/{run_id}/bundle`, `/manifest`, `/evidence`, `/docx`

Frontend (`frontend/src/pages/*.tsx`) bruger disse endpoints via `frontend/src/api.ts`.

### 2.5 Pipeline (hvor “kilder” bliver til output)

Core flow:
1) `POST /api/write` opretter run i DB (`create_run`) og starter `_run_background()`.
2) `_run_background()` kalder `list_library_sources()` (alle ingestede sources i appens DB) og giver dem til `run_pipeline()`.
3) `backend/akutwriter/pipeline/run.py:run_pipeline()`:
   - Opretter run-dir: `raw/`, `normalized/`, `index/`.
   - Loader `config/author_guide.yaml` + `config/source_allowlist.yaml`.
   - Kopierer alle `library_sources` ind i run-folder og laver `SourceRecord`s.
   - Henter `seed_urls` (allowlist), hvis sat.
   - Henter PubMed (NCBI E-utilities) og tilføjer ca. op til 12 `SourceRecord`s (title/abstract normaliseret).
   - Skriver `sources.jsonl`.
   - Bygger `Snippet`s (`build_snippets`) ved at chunk’e hver source’s normalized tekst.
   - `retrieve()` finder top snippets til query (BM25 lokalt eller embeddings hvis OpenAI key).
   - `write_procedure_markdown()` genererer markdown med citations-tags pr. sætning.
   - `validate_citations()` stopper run hvis citation-regler brydes.
   - `build_evidence_report()` laver heuristisk evidenscheck og kan stoppe run ved `strict`.
   - DOCX export + `run_manifest.json` + `run_summary.json`.

Konsekvens: Hvis man “indlæser” 50k guideline docs som `library_sources`, vil de *alle* blive kopieret ind i hvert run og chunk’ed → ubrugeligt.

---

## 3) `guideline_harvester/library` (korpus-overblik)

### 3.1 Struktur (som harvester forventer)

Fra `guideline_harvester/README.md`:
```
library/
├── sources/
│   ├── <source_id>/
│   │   ├── <doc_dir>/
│   │   │   ├── original.pdf|original.html
│   │   │   ├── extracted_text.txt
│   │   │   └── metadata.json
├── index.jsonl
└── index.sqlite
```

### 3.2 Metadata- og indeksformat

Eksempel `metadata.json` (forenklet):
- `source_id`, `source_name`, `source_url`
- `title`, `url`, `content_type`, `bytes`
- `sha256` (content hash)
- `procedure_hits` (liste)
- `access` (public / requires_login)
- `retrieved_at`
- `local_path` (relativ sti inde i library)

`guideline_harvester/guideline_harvester/index.py` implementerer:
- `index.jsonl` (append-only)
- `index.sqlite` med:
  - `documents` (metadata)
  - `procedure_hits` (m2m)
  - `documents_fts` (FTS5 over `title` + `extracted_text`)

### 3.3 OBS: indeks kan være ude af sync

I det konkrete miljø vi har set:
- `library/sources/**/extracted_text.txt` ≈ 53k filer
- `library/index.sqlite` har meget få `documents` (fx 10) → tyder på at indekset ikke er genopbygget efter senere crawl scripts.

Planen her inkluderer derfor:
- en eksplicit “Index health check + rebuild” (se fase 1).

### 3.4 Data-kvalitet: “tom extracted_text”

Mange harvested docs kan have meget kort `extracted_text.txt` (fx 9 bytes), typisk ved:
- frames/portal-sider uden indhold,
- extraction fejl,
- login/rights begrænsninger.

Det kræver filtrering (minimum length, content heuristics).

---

## 4) Mål: Integrationsdesign der skalerer

### 4.1 Kravbillede

Funktionelt:
- Brug lokale guidelines som primær evidens (DK praksis).
- Brug PubMed som supplement (nyere evidence / reviews).
- Bevar audit og citations-regler.
- UI skal kunne vise hvilke kilder der blev brugt.

Non-funktionelt (optimering):
- Runs må ikke blive enorme (mål: run-folder < ~50–200 MB i normal brug).
- Candidate search over 50k docs skal være hurtig (mål: < 0,5–2 sekunder lokalt).
- Indlæsning/normalisering må kun ske for et lille udsnit (mål: < 20–50 docs per run).
- Retrieval må ikke lave embeddings på tusindvis af chunks i ét API-kald.

### 4.2 Anbefalet arkitektur (eksternt corpus + selektiv import pr. run)

Introducér et konceptuelt lag: **Corpus Providers**
- `UserLibraryProvider` (det nuværende `library_sources` i app-DB; typisk få docs)
- `GuidelineHarvesterProvider` (peger på `~/guideline_harvester/library`)
- `PubMedProvider` (allerede integreret i pipeline)
- `SeedUrlProvider` (allerede integreret)

Kun Provider-output som er **valgt til run** bliver til `SourceRecord`s og ender i `sources.jsonl`.

### 4.3 Retrieval-strategi (2-trins, max-optimeret)

**Trin A — Candidate document retrieval (hurtig, global):**
- Input: `procedure + context` (evt. udvidet med samme term-expansion logik som PubMed i `pipeline/run.py:_expand_procedure_terms`).
- Brug FTS hvis tilgængelig:
  - Query `documents_fts MATCH ?` i harvester `index.sqlite`.
  - Returnér top `N_docs` (fx 30–80).
- Boost/filer:
  - Boost docs med `procedure_hits` match.
  - Filtrer bort `text_extracted=false` eller `len(extracted_text) < min_chars` (fx 500–1500).
  - Diversificér per `source_id` (undgå at top-N er 80 VIP-sider fra samme portal).

**Trin B — Snippet retrieval (dyb, lokal, på lille udsnit):**
- Load `extracted_text.txt` for de valgte docs.
- Chunk tekst → `Snippet`s (genbrug eksisterende `chunk_text()` strategi).
- Kør retrieval:
  - Først BM25 over chunks for at få top `N_chunks` (fx 150–300).
  - Hvis OpenAI embeddings ønskes: embed kun query + de top `N_chunks` og rerank til `top_k` (fx 80).

Fordel: meget billigere embeddings, men stadig semantisk.

---

## 5) Faseplan (trin-for-trin)

Denne er skrevet som en implementeringsplan med klare “Definition of Done” pr. fase.

### Fase 1 — Index health check + deterministisk indeks-rebuild (harvester)

**Formål:** sikre at `guideline_harvester/library/index.sqlite` afspejler `library/sources/**`.

Tasks:
1) Lav et “health check” script:
   - Tæl antal `metadata.json` vs `documents` i `index.sqlite`.
   - Rapporter mismatch, top sources, andel `text_extracted`.
2) Tilføj en “rebuild index” kommando i guideline_harvester CLI (eller et script der kalder `IndexManager.rebuild_all()`):
   - Input: `--library PATH`
   - Output: genopbyg `index.jsonl` + `index.sqlite` fra storage.
3) Kør rebuild på den store library og mål:
   - runtime
   - `index.sqlite` størrelse
   - FTS query latency (simple benchmark)

DoD:
- `index.sqlite` indeholder alle docs (± dedupe) og FTS søger korrekt.
- Der findes en dokumenteret kommando til rebuild.

### Fase 2 — “Connector” i Akut Procedure Writer (read-only integration)

**Formål:** backend kan læse harvested library uden at kopiere/importere alt.

Design:
- Ny backend-komponent (fx `backend/akutwriter/guideline_library.py`) der:
  - Validerer library path og forventet struktur.
  - Kan lave candidate search (via `index.sqlite` hvis findes).
  - Kan resolve `local_path` → absolut sti til:
    - raw: `original.pdf|original.html|...`
    - normalized: `extracted_text.txt`
    - metadata: `metadata.json`

Konfiguration:
- Tilføj et sted at gemme “library path”:
  - Enten via `AKUTWRITER_...` env var (simpelt),
  - eller i `secrets`/config (UI-styret).

DoD:
- Backend kan returnere en liste af candidate docs (metadata + paths) for en query.
- Ingen ændring i pipeline endnu (kun connector).

### Fase 3 — Selektiv kilde-tilføjelse i pipeline (kritisk ændring)

**Formål:** runs må kun inkludere *valgte* guideline docs, ikke hele korpus.

Tasks:
1) Refaktor `run_pipeline()` så den ikke blindt itererer over *alle* `library_sources` fra app DB.
   - Skeln mellem “user uploads” (lille) og “eksternt corpus”.
2) Indfør en ny pipeline-funktion:
   - `select_guideline_docs(query, settings, guideline_library)` → top docs
   - `materialize_docs_to_sources(run_dir, docs)` → return `SourceRecord`s (kun for valgte)
3) Integrér med PubMed og seed_urls som i dag:
   - Kør PubMed (hvis ikke dummy_mode), men begræns/justér hvis guideline corpus allerede dækker (optional).
4) Sørg for at `sources.jsonl` stadig indeholder alle run sources, og at citation-validatoren fortsat kan fejle (som safety-net).

DoD:
- Et run med guideline library aktiveret producerer et run-dir med kun K (fx 10–30) guideline sources + PubMed/seed/uploads.
- Runtime for “akut astma” er acceptabel, og run-folder bliver ikke enorm.

### Fase 4 — Retrieval tuning (BM25→embeddings refinement)

**Formål:** høj relevans uden embeddings på tusindvis af chunks.

Tasks:
1) Implementér 2-trins retrieval for guidelines:
   - FTS → doc candidates
   - BM25 → chunk candidates
   - Embeddings (optional) → rerank
2) Indfør caching:
   - Cache chunking per doc (key: `sha256`) til fx `data/cache/guidelines/chunks/<sha256>.json`.
   - Cache embeddings per chunk (key: `sha256 + chunk_index + model`) hvis embeddings bruges ofte.
3) Implementér “diversity constraints”:
   - max chunks per source_id
   - min antal guideline docs fra forskellige sources

DoD:
- Samme query gentaget bliver markant hurtigere (pga cache).
- Embeddings input size holdes under kontrollerede grænser.

### Fase 5 — UI/UX: styring og transparens

**Formål:** brugeren kan se/forstå hvilke kilder der er brugt, og styre strategien.

Forslag til UI:
- **Indstillinger**:
  - toggle: “Brug lokal guideline library”
  - felt: path (kan være read-only i UI hvis man foretrækker env-var)
  - valg: inkluder/exkluder sources (fx VIP vs offentlige)
  - retrieval parametre (advanced): max docs, min text length, max chunks
- **Skriv procedure**:
  - vis “kilde-strategi” (Guidelines + PubMed) og hvor mange der vælges
  - (optional) “preview” af top guideline docs og mulighed for at pinne enkelte docs
- **Run side**:
  - vis hvilke guideline docs blev brugt (titel, source, url, hash) + links til raw/norm i run

DoD:
- En ikke-udvikler kan reproducere og forstå et run (kilder + manifest).

### Fase 6 — QA, test, drift

Testtyper (hold dem hurtige og deterministiske):
- Unit tests for connector path-resolution + filter heuristics.
- Unit tests for “select N docs” logik (med lille fixture library i `tmp_path`).
- Integration test: kør `run_pipeline()` med fake guideline library (3–5 docs) + dummy_mode og assert:
  - `sources.jsonl` indeholder forventede docs
  - `procedure.md` passerer citation-validatoren
  - `run_manifest.json` har korrekt runtime/config snapshot

Drift:
- Dokumentér hvordan man opdaterer korpus:
  - `guideline-harvester crawl ...`
  - rebuild index
  - (optional) purge caches

---

## 6) Data-model: mapping fra harvested doc → run SourceRecord

Mål: En harvested doc skal blive til en `SourceRecord` som ser ud som de andre (PubMed/seed/ingest).

Foreslået mapping:
- `SourceRecord.kind`: `"guideline_harvested"`
- `title`: `metadata.title`
- `url`: `metadata.url`
- `year`: parse `published_date` eller `last_modified` hvis muligt (ellers `None`)
- `raw_path`: kopieret fil i run `raw/` (fx `.pdf` eller `.html`)
- `normalized_path`: run `normalized/SRCxxxx.txt` (indhold fra `extracted_text.txt`)
- `raw_sha256`: brug `metadata.sha256` hvis den refererer til raw content (verificér!), ellers beregn fra fil.
- `normalized_sha256`: beregn fra `extracted_text.txt` (eller brug precomputed hvis harvester har det).
- `extra`: gem hele `metadata.json` (eller et udsnit) inkl.:
  - `harvester_source_id` (fx `vip_regionh`)
  - `harvester_local_path`
  - `harvester_sha256`
  - `access`, `retrieved_at`

Vigtigt:
- Run’ets `source_id` skal stadig være `SRC0001`… fordi writer/citation-validator forventer det format (men det kan ændres, hvis man vil, uden at bryde `[S:...]`-regexen).

---

## 7) Hvordan det harmonerer med PubMed (arkitektur- og retrievalmæssigt)

PubMed i dag:
- pipeline henter op til ~12 PubMed sources (abstracts + metadata) og normaliserer dem til tekst.
- retrieval bygger snippets over *alle* sources.

Anbefalet samspil:
- Guideline corpus → primær “DK praksis” og konkrete instruktioner.
- PubMed → supplerende evidence (reviews/RCT) når guideline ikke dækker, eller når man vil have nyere evidens.

Praktisk i retrieval:
- Kør guideline-selection først (hurtig).
- Kør PubMed som i dag, men:
  - Hvis PubMed rate limits (429), fortsæt med warnings (som nu).
  - Overvej at reducere PubMed-scope hvis guidelines giver rigeligt materiale (valgfrit).
- Når snippets merges:
  - Garantér at der er guideline-snippets i top-k (fx via “at least M from corpus A”).
  - Brug “evidence policy” rapporteringen til at flagge sætninger der ikke matcher.

---

## 8) Ydeevne-budgetter og konkrete parametre (startværdier)

Startværdier (justér efter målinger):
- Candidate docs (FTS): `N_docs = 40`
- Min extracted text længde: `min_chars = 800` (for at filtrere tomme portal-sider)
- Chunks per doc: `chunk_text(max_chars=900, overlap=120)` (som nu)
- Chunk candidates til embeddings rerank: `N_chunks = 200` (BM25 prefilter)
- Final retrieval til writer: `top_k = 80` (som nu)
- Diversity: max 6 docs per source_id; max 12 chunks per doc

Observability:
- log i `run_manifest.json` runtime:
  - antal docs scannet, antal filtreret, antal chunks vurderet
  - cache hit-rate (chunks/embeddings)
  - timings per fase (FTS, load, chunk, retrieve)

---

## 9) Compliance / sikkerhed / licens (skal afklares)

Dette er ikke “kode-krav” men implementeringskrav:
- Regionalt materiale (VIP/D4/etc.) kan være adgangsbeskyttet; distribution kan være begrænset.
- Sørg for at UI/exports tydeligt markerer terms/licence.
- Undgå patientdata: harvested docs bør være guidelines, men check for indlejrede patientcases/eksempler.
- Hvis appen kan eksportere “bundle”, så kan den potentielt kopiere adgangsbeskyttet materiale ud af systemet → kræver policy/beslutning (fx slå bundle fra for certain sources eller strip raw files).

---

## 10) Handoff: “hvor starter man i koden”

Akut Procedure Writer:
- Pipeline entry: `backend/akutwriter/pipeline/run.py:run_pipeline()`
- Retrieval: `backend/akutwriter/pipeline/retrieve.py`
- Snippets builder: `backend/akutwriter/pipeline/retrieve.py:build_snippets()`
- Writer: `backend/akutwriter/pipeline/writer.py`
- Citation validation: `backend/akutwriter/pipeline/citations.py`
- Evidence report: `backend/akutwriter/pipeline/evidence.py`
- DB: `backend/akutwriter/db.py`
- API: `backend/akutwriter/main.py`

Guideline Harvester:
- Library index: `guideline_harvester/guideline_harvester/index.py`
- Storage layout: `guideline_harvester/guideline_harvester/storage.py` (for iterators; se projektet)
- CLI: `guideline_harvester/guideline_harvester/cli.py`

---

## 11) Definition of Done (samlet)

Integration anses som færdig når:
- En run-generation (typisk procedure) kan bruge lokale guidelines + PubMed uden at overskride runtime/størrelsesbudget.
- `sources.jsonl` indeholder de valgte guideline docs med korrekt metadata og hashes.
- Output passerer citation-validatoren.
- UI viser hvilke guideline docs der indgik, og kan hente raw/normalized fra run.
- Indeks og caches kan rebuildes deterministisk og er dokumenteret.

