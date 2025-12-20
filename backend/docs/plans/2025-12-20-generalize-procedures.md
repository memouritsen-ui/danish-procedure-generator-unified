# Generalized Medical Procedures - Problem Analysis & Solution

> **Problem**: Generated procedures contain department-specific content (phone numbers, "bagvagt" references, specific rooms/locations) that won't apply to all Danish emergency medicine doctors.

**Goal**: Create universal procedure manuals that any Danish emergency medicine doctor can use, regardless of their hospital.

---

## Part 1: Problem Exploration

### 1.1 Examples of Department-Specific Content (from Pleuradræn procedure)

| Type | Example | Problem |
|------|---------|---------|
| Phone numbers | "tlf. 5804", "tlf. 5803" | Only valid at one hospital |
| Specific rooms | "medicinsk base (overfor stue 99)" | Location-specific |
| Named departments | "thoraxkirurgisk afdeling i Skejby" | Region-specific |
| IT systems | "CASE-bestilling" | Hospital-specific software |
| Role assignments | "ortopædkirurgisk vagthavende anlægger" | Varies by hospital |
| Workflow paths | "henvis via ultralydsafdeling" | Organization-specific |

### 1.2 Root Cause Analysis

The problem originates from **how sources are processed**:

1. **Source documents** are regional/hospital guidelines (e-dok.rm.dk, vip.regionh.dk, etc.)
2. **Sources contain local instructions** by design - they're written FOR that hospital
3. **Current pipeline copies verbatim** - extracts and synthesizes without filtering
4. **StyleAgent focuses on structure**, not content generalization

### 1.3 Why This Matters

A doctor in Odense reading "kontakt anæstesiologisk forvagt (tlf. 5804)" will:
- Not know what phone number to call at THEIR hospital
- Possibly call the wrong number
- Lose trust in the procedure document

**The procedure should say**: "Kontakt anæstesiologisk forvagt via din afdelings lokale telefonnumre."

---

## Part 2: Solution Design

### 2.1 High-Level Approach

Add a **ContentGeneralizer** step to the pipeline that:
1. Detects department-specific patterns
2. Replaces with generalized equivalents
3. Preserves clinical accuracy

### 2.2 Detection Patterns

```python
DEPARTMENT_SPECIFIC_PATTERNS = {
    # Phone numbers
    r'tlf\.?\s*\d{4,8}': 'afdelingens lokale nummer',
    r'telefon\s*\d{4,8}': 'afdelingens lokale nummer',

    # Specific rooms/locations
    r'stue\s+\d+': 'relevant behandlingsrum',
    r'overfor stue \d+': '[fjernet lokationsreference]',
    r'ved medicinsk base \([^)]+\)': 'fra afdelingens udstyrsdepot',

    # Named hospitals/departments
    r'i Skejby': '',  # Remove, keep department name
    r'på [A-ZÆØÅ][a-zæøå]+sygehus': 'på relevant afdeling',

    # IT systems
    r'CASE-bestilling': 'bestillingssystem',
    r'i EPIC': 'i journalsystem',

    # Specific role assignments that vary
    r'ortopædkirurgisk vagthavende anlægger': 'relevant specialist anlægger',
}
```

### 2.3 Generalization Strategy

**Keep specific when universal:**
- Drug dosages (e.g., "fentanyl 50-100 mikrog")
- Clinical criteria (e.g., ">2 cm lateralt i hilushøjde")
- Equipment specifications (e.g., "CH20 eller CH28")

**Generalize when local:**
- Phone numbers → "afdelingens kontaktnummer"
- Room numbers → "behandlingsrum" or remove
- Named individuals → role descriptions
- Hospital names → "relevant afdeling"

### 2.4 Implementation Options

#### Option A: Post-Processing Step (Recommended)
Add `ContentGeneralizer` after StyleAgent, before DOCX generation.

**Pros:**
- Simple to implement
- Doesn't change existing pipeline
- Easy to test and iterate

**Cons:**
- Regex-based, may miss edge cases

#### Option B: LLM-Based Generalization
Use LLM to rewrite sections with local content.

**Pros:**
- More intelligent generalization
- Can handle nuanced cases

**Cons:**
- More expensive
- Adds latency
- May alter clinical content unintentionally

#### Option C: Source Filtering
Filter local content during source extraction.

**Pros:**
- Removes problem at source

**Cons:**
- Complex to implement
- May lose relevant context

### 2.5 Recommended Solution: Hybrid Approach

1. **Pattern-based detection** for obvious cases (phone numbers, room numbers)
2. **LLM review** for flagged sections to ensure clinical accuracy preserved
3. **[LOKAL]** markers for content that truly varies by hospital

---

## Part 3: Implementation Plan

### Task 1: Create ContentGeneralizer Class

**File:** `procedurewriter/pipeline/content_generalizer.py`

```python
class ContentGeneralizer:
    """Generalizes department-specific content in procedures."""

    def __init__(self):
        self.patterns = self._load_patterns()
        self.stats = {"replaced": 0, "flagged": 0}

    def generalize(self, content: str) -> tuple[str, dict]:
        """
        Generalize content and return stats.

        Returns:
            Tuple of (generalized_content, stats_dict)
        """
        ...
```

### Task 2: Define Pattern Categories

1. **Phone patterns**: `tlf`, `telefon`, 4-8 digit numbers
2. **Location patterns**: `stue`, `afdeling X`, `ved Y base`
3. **Hospital patterns**: Named hospitals, `i [City]`
4. **System patterns**: `CASE`, `EPIC`, specific IT systems
5. **Role patterns**: Specific person assignments

### Task 3: Add [LOKAL] Markers

For content that genuinely varies, add markers:

```markdown
## Disposition og opfølgning
- Kontakt [LOKAL: din afdelings bagvagt] for indikationsstilling
- Hent udstyr fra [LOKAL: afdelingens procedurevogn]
```

### Task 4: Integration into Pipeline

In `run.py`, add generalization step:

```python
# After StyleAgent, before DOCX
from procedurewriter.pipeline.content_generalizer import ContentGeneralizer

generalizer = ContentGeneralizer()
content, stats = generalizer.generalize(procedure_content)
logger.info(f"Generalized content: {stats['replaced']} replacements")
```

### Task 5: Add Configuration

Allow hospitals to configure their own replacements:

```yaml
# config/generalizer.yaml
replacements:
  "tlf. 5804": "afdelingens anæstesiforvagt"
  "medicinsk base": "udstyrsdepot"

preserve:
  - drug_dosages
  - clinical_criteria
  - equipment_specs
```

---

## Part 4: Expected Outcome

### Before (Current)
```
Kontakt anæstesiologisk forvagt (tlf. 5804) mhp. tilsyn på operationsafsnittet.
```

### After (Generalized)
```
Kontakt anæstesiologisk forvagt via afdelingens lokale nummer mhp. tilsyn.
```

### With [LOKAL] marker
```
Kontakt anæstesiologisk forvagt [LOKAL: se afdelingens kontaktliste] mhp. tilsyn.
```

---

## Part 5: Validation

1. **Unit tests** for pattern matching
2. **Regression tests** to ensure clinical content preserved
3. **Manual review** of 5 procedures before/after
4. **Domain expert review** if available

---

## Timeline Estimate

- Task 1-2: ContentGeneralizer + patterns (core implementation)
- Task 3: [LOKAL] markers
- Task 4: Pipeline integration
- Task 5: Configuration system
- Testing and validation

**Total: Can be implemented in this session.**
