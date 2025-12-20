# Procedure Generator Transformation Plan

## Problem Statement

The current system generates **workflow aggregators**, not **medical textbook content**. The output is useful for navigating hospital politics and local protocols, but fails to teach doctors how to actually perform procedures.

### Critical Issues Identified

1. **Missing Procedure Technique**: The core clinical content (HOW to do the procedure) is replaced with "følg lokal instruks"
2. **Organizational Noise**: 40%+ content about who to call, phone numbers, bagvagt, rollefordeling
3. **Repetition**: Same information repeated 6+ times (e.g., "tilkald anæstesi")
4. **No Anatomical Guidance**: Zero anatomical landmarks, no surface anatomy, no depth guidance
5. **Sources Are Local Workflows**: All sources are Danish regional e-dok/VIP guidelines, not international evidence
6. **"Følg lokal retningslinje" Overuse**: Appears 11+ times in a single procedure

### Root Cause Analysis

The system fetches **Danish hospital workflow documents** and synthesizes them into... more workflow documents. The LLM has no access to:
- International guidelines (BTS, ACCP, EAACI)
- Medical textbook content (anatomy, technique)
- Primary research (RCTs, meta-analyses)
- Educational material (step-by-step technique guides)

## Transformation Strategy

**Philosophy**: Non-destructive. Enhance, don't replace. Keep the pipeline architecture, but transform what flows through it.

### Layer 1: Source Diversification (HIGH PRIORITY)

**Problem**: Sources are exclusively Danish regional guidelines (e-dok.rm.dk, vip.regionh.dk, dok.regionsjaelland.dk)

**Solution**: Multi-tier source retrieval

```
Tier 1 (International Gold Standard)
├── NICE Guidelines
├── Cochrane Reviews
├── WHO Clinical Guidelines
├── Specialty Society Guidelines (BTS, ACCP, EAACI, ESC)
└── UpToDate (if accessible)

Tier 2 (Academic Evidence)
├── PubMed Systematic Reviews
├── PubMed RCTs
├── PubMed Meta-analyses
└── High-impact journal guidelines (NEJM, Lancet, BMJ)

Tier 3 (Technique Sources)
├── Medscape Procedures
├── StatPearls
├── YouTube educational channels (UCSF, Stanford, NHS)
└── Medical textbook excerpts

Tier 4 (Danish Context) - KEEP but DEMOTE
├── Danske regionale retningslinjer
├── Sundhedsstyrelsen
└── DSAM guidelines
```

**Implementation**:
- Create `procedurewriter/pipeline/international_sources.py`
- Add NICE API integration
- Add Cochrane Library search
- Weight international sources higher in retrieval
- Danish sources become "local adaptation" layer, not primary content

### Layer 2: Content Type Classification (HIGH PRIORITY)

**Problem**: LLM can't distinguish between workflow content and clinical content

**Solution**: Snippet classification before synthesis

```python
class SnippetType(Enum):
    TECHNIQUE = "technique"           # HOW to do it (anatomy, steps, depth)
    WORKFLOW = "workflow"             # WHO does it, WHEN to call
    EVIDENCE = "evidence"             # WHY it works (studies, outcomes)
    SAFETY = "safety"                 # Complications, contraindications
    EQUIPMENT = "equipment"           # What you need
    LOCAL_PROTOCOL = "local_protocol" # Hospital-specific (to be generalized)
```

**Implementation**:
- Create `procedurewriter/pipeline/snippet_classifier.py`
- Use LLM to classify each snippet before retrieval
- Filter snippets by type for each section
- "Fremgangsmåde" section should ONLY get TECHNIQUE snippets
- Workflow snippets go to "Forberedelse" only

### Layer 3: Anatomical Content Requirement (MEDIUM PRIORITY)

**Problem**: Procedures lack anatomical guidance

**Solution**: Mandatory anatomical content for invasive procedures

```yaml
# config/procedure_types.yaml
invasive_procedures:
  - pleuradræn
  - lumbalpunktur
  - central_venous_access
  - arteriel_kanyle
  - pericardiocentes

anatomical_requirements:
  pleuradræn:
    landmarks:
      - "5. interkostalrum"
      - "midtaksillærlinjen"
      - "triangel-of-safety"
    depth_guidance: true
    surface_anatomy: true

  lumbalpunktur:
    landmarks:
      - "L3-L4 eller L4-L5"
      - "crista iliaca"
      - "processus spinosus"
    depth_guidance: true
    surface_anatomy: true
```

**Implementation**:
- Create `procedurewriter/pipeline/anatomical_requirements.py`
- Add validation step: if procedure is invasive, check for landmarks
- If landmarks missing, fetch additional anatomical sources
- Add explicit anatomical section to template for invasive procedures

### Layer 4: Repetition Elimination (MEDIUM PRIORITY)

**Problem**: Same information repeated 6+ times

**Solution**: Semantic deduplication

```python
class RepetitionDetector:
    def detect_semantic_duplicates(self, sections: list[str]) -> list[DuplicateGroup]:
        """Find semantically similar content across sections."""
        # Use embeddings to cluster similar statements
        # Merge into canonical single statement
        # Place in most appropriate section only
```

**Implementation**:
- Create `procedurewriter/pipeline/deduplication.py`
- Run after initial generation, before DOCX
- Use embedding similarity to detect near-duplicates
- Keep only first/best occurrence
- Add cross-reference if truly needed in multiple places

### Layer 5: Workflow Content Filtering (MEDIUM PRIORITY)

**Problem**: 40% content is organizational noise

**Solution**: Workflow content filter

```python
WORKFLOW_PATTERNS = [
    r"ring til.*bagvagt",
    r"tlf\.?\s*\d+",
    r"tilkald.*anæstesi.*ved.*tvivl",
    r"følg.*lokal.*retningslinje",
    r"aftal.*rollefordeling",
    r"spørg.*kollega",
    r"tjek.*afdelingens",
]

class WorkflowFilter:
    def filter_workflow_content(self, text: str) -> tuple[str, str]:
        """Separate workflow content from clinical content.

        Returns:
            clinical_content: Pure clinical procedure content
            workflow_content: Organizational content (moved to appendix or removed)
        """
```

**Implementation**:
- Extend `ContentGeneralizer` to separate (not just mark) workflow content
- Move workflow content to separate "Lokal tilpasning" section at end
- Or remove entirely with flag `--clinical-only`

### Layer 6: Template Transformation (LOW PRIORITY)

**Problem**: Template structure encourages workflow-heavy sections

**Solution**: Clinical-focused template

```yaml
# New template structure
sections:
  - heading: "Anatomi og orientering"  # NEW: Mandatory for invasive
    format: paragraphs
    bundle: explanation
    required_for: invasive

  - heading: "Indikationer"
    format: bullets
    bundle: action

  - heading: "Kontraindikationer"
    format: bullets
    bundle: action

  - heading: "Udstyr"
    format: bullets
    bundle: action
    source_filter: equipment  # ONLY equipment snippets

  - heading: "Fremgangsmåde"  # MOST IMPORTANT
    format: numbered
    bundle: action
    source_filter: technique  # ONLY technique snippets
    subheadings:
      - "Positionering"
      - "Overfladeanatomi og landmarks"
      - "Steril teknik"
      - "Trin-for-trin procedure"
      - "Verifikation"

  - heading: "Sikkerhed og komplikationer"
    format: bullets
    bundle: safety

  - heading: "Evidensgrundlag"
    format: paragraphs
    bundle: explanation
    source_filter: evidence

  - heading: "Lokal tilpasning"  # NEW: Workflow content quarantine
    format: bullets
    bundle: action
    source_filter: workflow
    note: "Tilpasses lokalt - kontakt afdelingsledelse"
```

### Layer 7: LLM Prompt Engineering (LOW PRIORITY)

**Problem**: LLM prompts don't enforce clinical focus

**Solution**: Redesigned prompts

```python
CLINICAL_SYSTEM_PROMPT = """Du er forfatter til et dansk medicinsk opslagsværk.

DU SKRIVER IKKE:
- Hvem man skal ringe til
- Telefonnumre eller bagvagtordninger
- "Følg lokal retningslinje" (brug ALDRIG dette udtryk)
- Rollefordeling eller teamstrukturer
- Afdelingsspecifikke protokoller

DU SKRIVER:
- Præcis teknik med anatomiske landmarks
- Målbare dybder og vinkler
- Overfladeanatomi og orienteringspunkter
- Evidensbaserede doser og valg
- Komplikationer med håndtering

Hvis kilden siger "følg lokal retningslinje", skal du i stedet:
1. Søge efter international evidens for bedste praksis
2. Angive den mest veldokumenterede fremgangsmåde
3. Notere at institutionel variation kan forekomme
"""
```

## Implementation Priority

| Phase | Component | Effort | Impact | Dependencies |
|-------|-----------|--------|--------|--------------|
| 1 | Source Diversification | HIGH | CRITICAL | None |
| 1 | Snippet Classification | MEDIUM | HIGH | None |
| 2 | Workflow Content Filter | LOW | HIGH | Phase 1 |
| 2 | Repetition Elimination | MEDIUM | MEDIUM | Phase 1 |
| 3 | Anatomical Requirements | MEDIUM | HIGH | Phase 1+2 |
| 3 | Template Transformation | LOW | MEDIUM | Phase 1+2 |
| 4 | LLM Prompt Engineering | LOW | MEDIUM | All above |

## Non-Destructive Approach

**Keep unchanged**:
- Pipeline architecture (`run_pipeline()`)
- Source fetching infrastructure (`fetcher.py`, `CachedHttpClient`)
- Snippet retrieval system (`retrieve.py`, BM25/embeddings)
- Evidence verification (`evidence_verifier.py`)
- DOCX generation (`docx_writer.py`)
- Style agent (`style_agent.py`)
- Content generalizer (`content_generalizer.py`)

**Extend/enhance**:
- Add new source types to allowlist
- Add snippet classification step
- Add workflow filter step
- Modify templates
- Update prompts

**New files to create**:
- `procedurewriter/pipeline/international_sources.py`
- `procedurewriter/pipeline/snippet_classifier.py`
- `procedurewriter/pipeline/deduplication.py`
- `procedurewriter/pipeline/anatomical_requirements.py`
- `config/procedure_types.yaml`

## Success Criteria

After transformation, a generated procedure should:

1. **Teach the technique**: A doctor with zero prior experience could perform the basic procedure
2. **Include anatomy**: Surface landmarks, depth guidance, orientation
3. **Cite international evidence**: BTS, NICE, Cochrane, not just regional e-dok
4. **Minimize workflow noise**: <10% organizational content
5. **No "følg lokal retningslinje"**: Zero occurrences
6. **No repetition**: Each piece of information appears once
7. **Quality score >4**: Not 2

## Estimated Timeline

- Phase 1: 2-3 days (source diversification + classification)
- Phase 2: 1-2 days (filtering + deduplication)
- Phase 3: 2-3 days (anatomical + template)
- Phase 4: 1 day (prompt engineering)
- Testing + iteration: 2-3 days

**Total: 8-12 days of focused work**

## Next Steps

1. **Immediate**: Create `international_sources.py` with NICE and Cochrane integration
2. **Immediate**: Update `source_allowlist.yaml` with international source domains
3. **Week 1**: Implement snippet classification
4. **Week 1**: Test with pleuradræn and anafylaksi procedures
5. **Week 2**: Implement remaining phases based on results
