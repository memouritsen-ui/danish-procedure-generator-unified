"""GPS (Good Practice Statement) Classification Module.

Per GRADE methodology, Good Practice Statements should be UNGRADED because
evidence review would be "poor use of time." Examples include procedural
statements like "Assess the patient's airway."

The core criterion is the "inverse test": if the opposite statement sounds
absurd, it's a GPS. "Don't assess the patient's airway" is obviously wrong.

References:
- GRADE Working Group: https://www.gradeworkinggroup.org/
- Guyatt et al. (2015) GRADE guidelines: Good Practice Statements
"""
from __future__ import annotations

import re
from enum import Enum


class SentenceType(str, Enum):
    """Classification of medical procedure sentences.

    GPS: Good Practice Statement - exempt from evidence requirements
    THERAPEUTIC: Drug/treatment claims - requires evidence
    PROGNOSTIC: Outcome/survival claims - requires evidence
    DIAGNOSTIC: Threshold/diagnostic criteria - requires evidence
    PROCEDURAL: General procedural text - default, may be GPS
    """
    GPS = "gps"
    THERAPEUTIC = "therapeutic"
    PROGNOSTIC = "prognostic"
    DIAGNOSTIC = "diagnostic"
    PROCEDURAL = "procedural"


# Patterns that indicate GPS (procedural verbs where inverse is absurd)
# Note: Use (?=\s|,|$) lookahead instead of \b for Danish accented characters
GPS_VERB_PATTERNS: list[str] = [
    # Assessment verbs - "Don't assess" is absurd
    # Matches: vurder, vurdér, vurderer, vurderes
    r"(?i)^vurd[eé]r(?:er|es|e)?(?=\s|,|$|\.\s)",
    r"(?i)^tjek(?:ker|kes)?(?=\s|,|$|\.\s)",
    r"(?i)^observ[eé]r(?:er|es|e)?(?=\s|,|$|\.\s)",
    r"(?i)^mål(?:er|es|e)?(?=\s|,|$|\.\s)",
    r"(?i)^kontroll[eé]r(?:er|es|e)?(?=\s|,|$|\.\s)",
    # Documentation verbs - "Don't document" is absurd
    r"(?i)^dokument[eé]r(?:er|es|e)?(?=\s|,|$|\.\s)",
    r"(?i)^registr[eé]r(?:er|es|e)?(?=\s|,|$|\.\s)",
    # Communication verbs - "Don't communicate" is absurd
    r"(?i)^kommunik[eé]r(?:er|es|e)?(?=\s|,|$|\.\s)",
    r"(?i)^inform[eé]r(?:er|es|e)?(?=\s|,|$|\.\s)",
    r"(?i)^forklar(?:er|es|e)?(?=\s|,|$|\.\s)",
    # Safety verbs - "Don't ensure safety" is absurd
    r"(?i)^sikr(?:er|es|e)?(?=\s|,|$|\.\s)",
    r"(?i)^sørg\s+for(?=\s|,|$)",
    # Monitoring verbs - "Don't monitor" is absurd
    r"(?i)^overv[aå]g(?:er|es|e)?(?=\s|,|$|\.\s)",
    r"(?i)^monit[oø]r[eé]r(?:er|es|e)?(?=\s|,|$|\.\s)",
    r"(?i)^monitor(?:er|es|e)?(?=\s|,|$|\.\s)",
    # Consideration verbs - "Don't consider" obvious risks is absurd
    r"(?i)^overvej(?=\s|,|$)",
    # Referral verbs - "Don't refer" when needed is absurd
    r"(?i)^henvis(?:er|es|e)?(?=\s|,|$|\.\s)",
    r"(?i)^bed\s+om(?=\s|,|$)",
    r"(?i)^tilkald(?:er|es|e)?(?=\s|,|$|\.\s)",
    # Additional common GPS verbs
    r"(?i)^bekr[æa]ft(?:er|es|e)?(?=\s|,|$|\.\s)",
    r"(?i)^verificer(?:er|es|e)?(?=\s|,|$|\.\s)",
    # Adaptation/adjustment verbs - "Don't adapt your approach" is absurd
    r"(?i)^tilpas(?:ser|ses|se)?(?=\s|,|$|\.\s)",
]

# Meta-analysis section patterns (self-referential, non-citable)
# These describe THIS document's methodology, not external evidence
META_ANALYSIS_PATTERNS: list[str] = [
    # Evidence basis statements
    r"(?i)^evidensen\s+baseres\s+på",
    r"(?i)^den\s+samlede\s+evidens",
    r"(?i)^samlet\s+inkluderer\s+evidensgrundlaget",
    # Meta-analysis methodology statements
    r"(?i)^formel\s+meta-analyse",
    r"(?i)^meta-analysen\s+viser",
    r"(?i)^studiekvaliteten\s+blev\s+vurderet",
    # Study synthesis statements
    r"(?i)^systematiske\s+reviews\s+fra",
    r"(?i)GRADE-metoden",
    # Source reference statements
    r"(?i)^se\s+de\s+individuelle\s+kilder",
    r"(?i)^se\s+.*kilder\s+for\s+detaljer",
]

# Fragment patterns (incomplete sentences that cannot have evidence)
FRAGMENT_PATTERNS: list[str] = [
    # Parenthetical references like "B3)", "A1)", "(se afsnit 3)"
    r"^[A-Z]\d+\)$",
    r"^\([^)]+\)$",
    # Abbreviations only like "amb.", "kons."
    r"^[a-zæøå]{2,5}\.$",
    # Continuation fragments starting with lowercase conjunctions
    r"^(?:at|og|samt|eller|men|for)\s+[a-zæøå]",
    # Lowercase-starting fragments (continuations from previous sentence)
    r"^[a-zæøå].*behandlingsbehov",
]

# Patterns that indicate NON-GPS (require evidence)
NON_GPS_PATTERNS: list[str] = [
    # Dosages with units - therapeutic claims
    r"\d+\s*(?:mg|ml|mcg|µg|g|kg|mmol|IE|enheder|mikrogram)",
    # Named drugs - therapeutic claims
    r"(?i)(?:adrenalin|epinefrin|salbutamol|prednisolon|hydrocortison|morfin|fentanyl|ketamin|propofol|midazolam|atropin|amiodaron|magnesium)",
    # Outcome claims - prognostic (includes risikoen, risiko, etc.)
    r"(?i)(?:mortalitet|overlevelse|dødelighed|prognose|risiko\w*\s+for\s+\w+)",
    # Diagnostic thresholds - diagnostic claims
    r"(?i)(?:diagnos\w*\s+(?:stilles|baseret|ved))",
    r"(?i)(?:SpO2|saturation|pulsoximetri)\s*(?:under|over|<|>)\s*\d+",
    r"(?i)(?:peak\s*flow)\s*(?:under|over|<|>)\s*\d+",
]

# Compiled patterns for performance
_GPS_PATTERNS_COMPILED = [re.compile(p) for p in GPS_VERB_PATTERNS]
_NON_GPS_PATTERNS_COMPILED = [re.compile(p) for p in NON_GPS_PATTERNS]
_META_ANALYSIS_PATTERNS_COMPILED = [re.compile(p) for p in META_ANALYSIS_PATTERNS]
_FRAGMENT_PATTERNS_COMPILED = [re.compile(p) for p in FRAGMENT_PATTERNS]

# Citation pattern to strip before classification
_CITATION_PATTERN = re.compile(r"\[S:[^\]]+\]")


def _strip_citations(text: str) -> str:
    """Remove citation markers from text."""
    return _CITATION_PATTERN.sub("", text).strip()


def _has_gps_verb(text: str) -> bool:
    """Check if text starts with a GPS verb pattern."""
    for pattern in _GPS_PATTERNS_COMPILED:
        if pattern.search(text):
            return True
    return False


def _has_non_gps_signal(text: str) -> bool:
    """Check if text contains signals that require evidence."""
    for pattern in _NON_GPS_PATTERNS_COMPILED:
        if pattern.search(text):
            return True
    return False


def _is_meta_analysis_statement(text: str) -> bool:
    """Check if text is a meta-analysis methodology statement.

    These are self-referential statements about the document's evidence
    synthesis process and are inherently non-citable.
    """
    for pattern in _META_ANALYSIS_PATTERNS_COMPILED:
        if pattern.search(text):
            return True
    return False


def _is_fragment(text: str) -> bool:
    """Check if text is an incomplete sentence fragment.

    Fragments cannot have evidence because they're not complete claims.
    Checks for:
    - Very short text (< 10 chars) without GPS verbs
    - Parenthetical references like "B3)", "(se afsnit 3)"
    - Abbreviation-only like "amb.", "kons."
    - Continuation fragments starting lowercase with conjunctions
    """
    # Very short fragments (but not GPS verbs)
    if len(text) < 10 and not _has_gps_verb(text):
        return True

    # Check explicit fragment patterns
    for pattern in _FRAGMENT_PATTERNS_COMPILED:
        if pattern.search(text):
            return True

    return False


def _detect_prognostic(text: str) -> bool:
    """Check if text contains prognostic claims."""
    prognostic_patterns = [
        r"(?i)(?:mortalitet|dødelighed)",
        r"(?i)(?:overlevelse|survival)",
        r"(?i)(?:prognose)",
        r"(?i)(?:risiko\w*\s+for\s+\w+)",  # Risikoen for komplikationer...
        r"(?i)(?:reduceres?\s+med\s+\d+)",
    ]
    for pattern in prognostic_patterns:
        if re.search(pattern, text):
            return True
    return False


def _detect_diagnostic(text: str) -> bool:
    """Check if text contains diagnostic threshold claims."""
    diagnostic_patterns = [
        r"(?i)(?:diagnos\w*\s+(?:stilles|baseret|ved))",
        r"(?i)(?:SpO2|saturation|pulsoximetri)\s*(?:under|over|<|>)\s*\d+",
        r"(?i)(?:peak\s*flow)\s*(?:under|over|<|>)\s*\d+",
        r"(?i)(?:indikerer|tyder\s+på)",
    ]
    for pattern in diagnostic_patterns:
        if re.search(pattern, text):
            return True
    return False


def classify_sentence_type(sentence: str) -> SentenceType:
    """Classify a sentence as GPS, THERAPEUTIC, PROGNOSTIC, DIAGNOSTIC, or PROCEDURAL.

    Classification priority (highest to lowest):
    1. FRAGMENT - incomplete sentences (always GPS, cannot have evidence)
    2. META_ANALYSIS - self-referential methodology statements (GPS)
    3. THERAPEUTIC - if contains drug dosages (requires evidence)
    4. PROGNOSTIC - if contains outcome/mortality claims
    5. DIAGNOSTIC - if contains diagnostic thresholds
    6. GPS - if starts with GPS verb AND no non-GPS signals
    7. PROCEDURAL - default for other text

    Args:
        sentence: The sentence text to classify

    Returns:
        SentenceType indicating the classification
    """
    if not sentence or not sentence.strip():
        return SentenceType.PROCEDURAL

    # Strip citations before analysis
    clean = _strip_citations(sentence)
    if not clean:
        return SentenceType.PROCEDURAL

    # Check for fragments FIRST (before non-GPS signals)
    # Fragments like "5 mg)" are incomplete and cannot have evidence
    if _is_fragment(clean):
        return SentenceType.GPS

    # Check for meta-analysis statements (self-referential, non-citable)
    if _is_meta_analysis_statement(clean):
        return SentenceType.GPS

    # Check for non-GPS signals (these override GPS verbs)
    if _has_non_gps_signal(clean):
        # Determine specific type
        if _detect_prognostic(clean):
            return SentenceType.PROGNOSTIC
        if _detect_diagnostic(clean):
            return SentenceType.DIAGNOSTIC
        # Default non-GPS with dosage/drug is therapeutic
        return SentenceType.THERAPEUTIC

    # Check for GPS verb patterns
    if _has_gps_verb(clean):
        return SentenceType.GPS

    # Default to procedural
    return SentenceType.PROCEDURAL


def passes_inverse_test(sentence: str) -> bool:
    """Check if a sentence passes the GRADE inverse test.

    The inverse test: if the negation of the statement sounds absurd,
    it's a Good Practice Statement.

    Examples:
    - "Assess the airway" → "Don't assess the airway" = ABSURD → passes
    - "Give 0.3mg adrenaline" → "Don't give 0.3mg adrenaline" = VALID → fails
    - "Evidensen baseres på reviews" → Negation absurd for procedure doc → passes

    Args:
        sentence: The sentence to test

    Returns:
        True if the inverse sounds absurd (GPS), False otherwise
    """
    if not sentence or not sentence.strip():
        return False

    clean = _strip_citations(sentence)
    if not clean:
        return False

    # Fragments pass (incomplete sentences can't be negated meaningfully)
    if _is_fragment(clean):
        return True

    # Meta-analysis statements pass (negation is absurd for procedure docs)
    # "Evidensen baseres IKKE på systematiske reviews" is absurd
    if _is_meta_analysis_statement(clean):
        return True

    # If it has drug dosages, inverse is valid (could give different dose)
    if _has_non_gps_signal(clean):
        return False

    # If it starts with GPS verb, inverse is absurd
    if _has_gps_verb(clean):
        return True

    return False
