# Design: LLM-Styret DOCX Generator med Stilprofiler

**Dato:** 2025-12-20
**Status:** Godkendt
**Formål:** Redesign DOCX-generator til professionel medicinsk faglitteratur med LLM-styret formatering og brugerdefinerbar "bogstil" via natural language.

---

## Overblik

### Problem
- Nuværende DOCX output ser ud som "markdown-i-Word" (`**asterisker**` i stedet for ægte bold)
- Ingen professionel bogformatering (titel, TOC, margin-pearls)
- Statisk template uden forståelse for indholdet
- Ingen mulighed for at definere redaktionel stil

### Løsning
Post-processing lag med LLM (`StyleAgent`) der polerer markdown før DOCX-generation, styret af brugerdefinerbare stilprofiler oprettet via naturligt sprog.

---

## Arkitektur

```
┌─────────────────────────────────────────────────────────────┐
│                        UI Layer                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ StyleEditor │  │ StyleList   │  │ StylePreview        │  │
│  │ (natural    │  │ (gemte      │  │ (live preview af    │  │
│  │  language)  │  │  profiler)  │  │  procedure-output)  │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Backend API                             │
│  POST /api/styles              - Opret/opdater profil       │
│  GET  /api/styles              - List alle profiler         │
│  POST /api/styles/preview      - Preview med sample text    │
│  POST /api/styles/parse        - NL → struktureret profil   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Pipeline Integration                      │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │ Eksisterende │ -> │ StyleAgent   │ -> │ DOCX Writer  │   │
│  │ Pipeline     │    │ (LLM polish) │    │ (forbedret)  │   │
│  │ (uændret)    │    │              │    │              │   │
│  └──────────────┘    └──────────────┘    └──────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**Dataflow:**
1. Pipeline genererer markdown + sources (som nu)
2. `StyleAgent` tager markdown + aktiv stilprofil → poleret markdown
3. Forbedret `write_procedure_docx` konverterer til professionel DOCX

---

## StyleAgent

**Placering:** `procedurewriter/agents/style_agent.py`

### Input/Output

```python
@dataclass
class StyleInput:
    raw_markdown: str           # Fra pipeline
    sources: list[SourceRecord] # Kildedata
    style_profile: StyleProfile # Aktiv stilprofil
    procedure_name: str

@dataclass
class StyleOutput:
    polished_markdown: str      # Omskrevet tekst
    applied_rules: list[str]    # Hvilke stil-regler blev anvendt
    warnings: list[str]         # "Kunne ikke finde klinisk pearl til sektion X"
```

### LLM Prompt-strategi

```
Du er en medicinsk redaktør. Omskriv denne procedure til bogkvalitet.

STIL-PROFIL:
{style_profile.tone_description}
Målgruppe: {style_profile.target_audience}
Detaljeniveau: {style_profile.detail_level}

REGLER:
1. BEVAR alle citations [SRC0001] præcist som de er
2. BEVAR alle fakta - omskriv kun formuleringen
3. Fjern markdown-syntaks (**bold**) - brug plain tekst
4. Strukturer med klare afsnit og overgange

ORIGINAL TEKST:
{raw_markdown}

Returnér den omskrevne tekst.
```

### Garantier
- Citations må ALDRIG ændres eller fjernes
- Faktuelt indhold bevares 100%
- Kun sproglig polering + strukturering

---

## StyleProfile Datamodel

### Database Schema

```sql
CREATE TABLE style_profiles (
    id TEXT PRIMARY KEY,              -- UUID
    name TEXT NOT NULL,               -- "Lærebog - Formel"
    description TEXT,                 -- Kort beskrivelse
    is_default BOOLEAN DEFAULT FALSE, -- Kun én aktiv default
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    -- Indhold & Tone (JSON)
    tone_config TEXT NOT NULL,

    -- Struktur (JSON)
    structure_config TEXT NOT NULL,

    -- Formattering (JSON)
    formatting_config TEXT NOT NULL,

    -- Visuel (JSON)
    visual_config TEXT NOT NULL,

    -- Original natural language input (til redigering)
    original_prompt TEXT
);
```

### Python Dataclass

```python
@dataclass
class StyleProfile:
    id: str
    name: str
    description: str | None
    is_default: bool

    # Indhold & Tone
    tone_description: str
    target_audience: str
    detail_level: str  # "concise" | "moderate" | "comprehensive"

    # Struktur
    section_order: list[str]
    include_clinical_pearls: bool
    include_evidence_badges: bool

    # Formattering
    heading_style: str  # "numbered" | "unnumbered"
    list_style: str     # "bullets" | "numbered" | "prose"
    citation_style: str # "superscript" | "inline"

    # Visuel
    color_scheme: str
    safety_box_style: str

    # Meta
    original_prompt: str | None  # For A→B loop
```

---

## Forbedret DOCX Writer

### Opdateret Signatur

```python
def write_procedure_docx(
    *,
    markdown_text: str,          # Nu: poleret fra StyleAgent
    sources: list[SourceRecord],
    output_path: Path,
    run_id: str,
    manifest_hash: str,
    style_profile: StyleProfile,  # NY: erstatter template_path
    quality_score: int | None = None,
) -> None:
```

### Nye Formateringsfunktioner

```python
# Professionel titel-side
def _write_title_page(doc, procedure_name: str, profile: StyleProfile):
    """
    - Centreret titel med procedure-navn
    - Undertitel: "Klinisk Procedurevejledning"
    - Genereret dato + version
    - Institutional logo placeholder
    """

# Indholdsfortegnelse
def _write_table_of_contents(doc, sections: list[str]):
    """Auto-genereret TOC baseret på sektioner"""

# Professionelle overskrifter (ikke markdown-style)
def _write_heading(doc, text: str, level: int, profile: StyleProfile):
    """
    - Ægte Word Heading styles (Heading 1, Heading 2)
    - Nummerering hvis profile.heading_style == "numbered"
    - Farver fra profile.color_scheme
    """

# Sikkerhedsboks med ægte formatering
def _write_safety_box(doc, content: str, profile: StyleProfile):
    """
    - Tabel med farvet baggrund (ikke markdown **ADVARSEL**)
    - Ikon hvis understøttet
    - Rød/gul kant baseret på alvorlighed
    """

# Kliniske pearls i margin (hvis aktiveret)
def _write_clinical_pearl(doc, text: str, profile: StyleProfile):
    """Tekstboks i højre margin med tip/pearl"""

# Professionel referenceliste
def _write_references(doc, sources: list[SourceRecord], profile: StyleProfile):
    """
    - Nummereret liste med korrekt citation-format
    - DOI/PMID som klikbare links
    - Evidensniveau-badges hvis aktiveret
    """
```

---

## API Endpoints

```python
# Profil CRUD
@app.get("/api/styles")
def list_styles() -> list[StyleProfileSummary]

@app.get("/api/styles/{style_id}")
def get_style(style_id: str) -> StyleProfile

@app.post("/api/styles")
def create_style(request: CreateStyleRequest) -> StyleProfile

@app.put("/api/styles/{style_id}")
def update_style(style_id: str, request: UpdateStyleRequest) -> StyleProfile

@app.delete("/api/styles/{style_id}")
def delete_style(style_id: str) -> None

@app.post("/api/styles/{style_id}/set-default")
def set_default_style(style_id: str) -> None

# NL → Profil parsing
@app.post("/api/styles/parse")
def parse_style_prompt(request: ParsePromptRequest) -> StyleProfile

# Live preview
@app.post("/api/styles/preview")
def preview_style(request: PreviewRequest) -> PreviewResponse
```

---

## Pipeline Integration

```python
# Eksisterende flow (uændret):
md = write_procedure_markdown(...)
evidence = build_evidence_report(md, snippets=snippets)

# NYT: Style polering
style_profile = get_default_style_profile(settings.db_path)

if style_profile and settings.use_llm:
    style_agent = StyleAgent(llm=llm, model=settings.model)
    style_result = style_agent.execute(StyleInput(
        raw_markdown=md,
        sources=sources,
        style_profile=style_profile,
        procedure_name=procedure,
    ))
    polished_md = style_result.polished_markdown
else:
    polished_md = md  # Fallback

# DOCX generation
write_procedure_docx(
    markdown_text=polished_md,
    sources=sources,
    output_path=docx_path,
    run_id=run_id,
    manifest_hash=manifest_hash,
    style_profile=style_profile,
    quality_score=quality_score,
)
```

### Bagudkompatibilitet
- Ingen stilprofil → nuværende opførsel
- `use_llm=False` → spring StyleAgent over
- Alle eksisterende runs virker stadig

---

## Fejlhåndtering

| Situation | Håndtering |
|-----------|------------|
| LLM fejler under polering | Fallback til rå markdown + warning |
| Citations mangler i output | Validér, retry med strengere prompt |
| Ugyldig NL→profil parsing | Vis fejl, bed bruger omformulere |
| Ingen default profil | Brug hardcoded "neutral" profil |
| Profil slettet under run | Brug cached profil fra start |

### Citation Validering

```python
def _validate_polished_output(original: str, polished: str) -> list[str]:
    original_citations = set(re.findall(r'\[SRC\d+\]', original))
    polished_citations = set(re.findall(r'\[SRC\d+\]', polished))

    missing = original_citations - polished_citations
    if missing:
        raise StyleValidationError(f"Manglende citations: {missing}")
```

---

## Implementeringsrækkefølge

1. Database schema + `StyleProfile` model
2. `StyleAgent` med citation-validering
3. Forbedret `write_procedure_docx`
4. API endpoints
5. Frontend `StylesPage.tsx`
6. Pipeline integration
7. Tests

---

## Test-strategi

```python
# Unit tests
test_style_agent_preserves_citations()
test_style_agent_respects_tone_setting()
test_nl_to_profile_parsing()
test_docx_writer_with_profile()

# Integration tests
test_full_pipeline_with_style_profile()
test_fallback_when_no_profile()
test_preview_endpoint()

# Snapshot tests
test_docx_output_matches_expected_format()
```
