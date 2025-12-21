"""Phase 0 Validation: Claim Extraction Proof-of-Concept.

Tests whether we can reliably extract medical claims from procedure text.
Claim types:
- DOSE: Drug dosages (e.g., "amoxicillin 50 mg/kg/d")
- THRESHOLD: Clinical thresholds (e.g., "CURB-65 ≥3", "sat <92%")
- RECOMMENDATION: Clinical recommendations (e.g., "bør indlægges")
- CONTRAINDICATION: When NOT to do something
- RED_FLAG: Warning signs requiring action
- ALGORITHM_STEP: Numbered procedure steps
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ClaimType(Enum):
    DOSE = "dose"
    THRESHOLD = "threshold"
    RECOMMENDATION = "recommendation"
    CONTRAINDICATION = "contraindication"
    RED_FLAG = "red_flag"
    ALGORITHM_STEP = "algorithm_step"


@dataclass
class Claim:
    claim_type: ClaimType
    text: str
    value: Optional[str]  # Normalized value if applicable
    unit: Optional[str]
    source_refs: list[str]  # [SRC0023] etc.
    line_number: int
    confidence: float  # 0-1 extraction confidence


# Regex patterns for claim extraction
DOSE_PATTERNS = [
    # "amoxicillin 50 mg/kg/d fordelt på 2-3 doser"
    r'([a-zA-ZæøåÆØÅ\-]+)\s+(\d+(?:[.,]\d+)?)\s*(mg|g|mcg|μg|ml|IE|U)(?:/kg)?(?:/d(?:ag|øgn)?)?(?:\s+(?:fordelt\s+på|x)\s+(\d+(?:-\d+)?)\s+(?:doser?|gange?))?',
    # "500 mg hver 12. time"
    r'(\d+(?:[.,]\d+)?)\s*(mg|g|mcg|μg|ml)\s+(?:hver|x)\s+(\d+)\.?\s*(?:time|dag)',
    # "750 mg p.o. hver 6. time"
    r'(\d+(?:[.,]\d+)?)\s*(mg|g)\s+(?:p\.?o\.?|i\.?v\.?)\s+hver\s+(\d+)\.?\s*time',
]

THRESHOLD_PATTERNS = [
    # "CURB-65 score 2-4", "CRB-65 ≥3"
    r'(CURB-65|CRB-65|CURB65|CRB65)\s*(?:score)?\s*([≥≤><]?\s*\d+(?:-\d+)?)',
    # "saturation <92%", "sat <85%", "SaO2 <90%"
    r'(?:sat(?:uration)?|SpO2|SaO2)\s*([<>≤≥])\s*(\d+)\s*%',
    # "temperatur >38°C", "feber >38"
    r'(?:temperatur|feber|temp)\s*([<>≤≥])\s*(\d+(?:[.,]\d+)?)\s*°?C?',
    # "alder >65", "alder <6 måneder", "≥18 år", "0-17 år"
    r'alder\s*([<>≤≥])\s*(\d+)\s*(år|måneder|mdr|uger)?',
    r'([≥≤><])\s*(\d+)\s*år',
    r'(\d+)[-–](\d+)\s*år',
    # "børn <2 år"
    r'børn\s*([<>≤≥])\s*(\d+)\s*år',
    # "RF >30/min", "respirationsfrekvens"
    r'(?:RF|respirationsfrekvens)\s*([<>≤≥])\s*(\d+)(?:/min)?',
    # "BT <90/60"
    r'(?:BT|blodtryk)\s*([<>≤≥])\s*(\d+)/(\d+)',
    # "Urea >7 mmol/l"
    r'(?:urea|karbamid)\s*([<>≤≥])\s*(\d+(?:[.,]\d+)?)\s*mmol/l',
    # "kapillærrespons >2 sek"
    r'kapillærrespons\s*([<>≤≥])\s*(\d+)\s*sek',
    # "PEF", "peak flow"
    r'(?:PEF|peak\s*flow|PF)\s*([<>≤≥])\s*(\d+)',
    # "x 1 pr. time", "mindst x 1"
    r'(?:mindst\s+)?x\s*(\d+)\s*(?:pr\.?\s*)?(time|dag|døgn)',
]

RECOMMENDATION_PATTERNS = [
    r'(?:bør|skal|anbefales|overvejes)\s+(.{10,80}?)(?:\.|,|\[)',
    r'(?:iværksæt|start|giv)\s+(.{10,80}?)(?:\.|,|\[)',
]

CONTRAINDICATION_PATTERNS = [
    r'(?:kontraindikationer?|må ikke|undlad|afgræns)\s*:?\s*(.{10,100}?)(?:\.|$)',
    r'(?:ikke\s+omfattet|håndteres\s+ikke)',
]

RED_FLAG_PATTERNS = [
    r'(?:alarmsymptom|advarsel|kritisk|akut)\s*:?\s*(.{10,80})',
    r'(?:mistanke\s+om|ved\s+tegn\s+på)\s+(.{10,60})',
]

SOURCE_REF_PATTERN = r'\[S:SRC\d+\]|\[SRC\d+\]'


def extract_source_refs(text: str) -> list[str]:
    """Extract all source references from text."""
    refs = re.findall(SOURCE_REF_PATTERN, text)
    return [ref.replace('[S:', '[').replace('SRC', 'SRC') for ref in refs]


def extract_doses(text: str, line_num: int) -> list[Claim]:
    """Extract dose claims from text."""
    claims = []
    for pattern in DOSE_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            full_match = match.group(0)
            refs = extract_source_refs(text)
            claims.append(Claim(
                claim_type=ClaimType.DOSE,
                text=full_match,
                value=match.group(1) if match.lastindex >= 1 else None,
                unit=match.group(2) if match.lastindex >= 2 else None,
                source_refs=refs,
                line_number=line_num,
                confidence=0.9 if refs else 0.6,
            ))
    return claims


def extract_thresholds(text: str, line_num: int) -> list[Claim]:
    """Extract threshold claims from text."""
    claims = []
    for pattern in THRESHOLD_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            full_match = match.group(0)
            refs = extract_source_refs(text)
            claims.append(Claim(
                claim_type=ClaimType.THRESHOLD,
                text=full_match,
                value=full_match,
                unit=None,
                source_refs=refs,
                line_number=line_num,
                confidence=0.85 if refs else 0.5,
            ))
    return claims


def extract_all_claims(procedure_text: str) -> list[Claim]:
    """Extract all claims from procedure text."""
    all_claims = []

    for line_num, line in enumerate(procedure_text.split('\n'), 1):
        # Skip empty lines and headers
        if not line.strip() or line.startswith('#'):
            continue

        # Extract doses
        all_claims.extend(extract_doses(line, line_num))

        # Extract thresholds
        all_claims.extend(extract_thresholds(line, line_num))

    return all_claims


def validate_claim_extraction(procedure_text: str) -> dict:
    """Validate claim extraction on a procedure and return metrics."""
    claims = extract_all_claims(procedure_text)

    # Count by type
    by_type = {}
    for claim in claims:
        t = claim.claim_type.value
        by_type[t] = by_type.get(t, 0) + 1

    # Count with/without source refs
    with_refs = sum(1 for c in claims if c.source_refs)
    without_refs = sum(1 for c in claims if not c.source_refs)

    # Average confidence
    avg_confidence = sum(c.confidence for c in claims) / len(claims) if claims else 0

    return {
        "total_claims": len(claims),
        "by_type": by_type,
        "with_source_refs": with_refs,
        "without_source_refs": without_refs,
        "avg_confidence": round(avg_confidence, 2),
        "claims": claims,
    }


# Manual test - expected claims from Pneumoni procedure
EXPECTED_DOSES_PNEUMONI = [
    "amoxicillin 50 mg/kg/d",
    "benzyl-penicillin 100 mg/kg/d",
    "clarithromycin 15 mg/kg/d",
    "ampicillin 100 mg/kg/d",
    "gentamicin 5 mg/kg",
    "metronidazol 24 mg/kg/d",
    "clarithromycin 500 mg",
    "amoxicillin 750 mg",
    "cefuroxim 750 mg",
    "roxithromycin 150 mg",
]

EXPECTED_THRESHOLDS_PNEUMONI = [
    "CURB-65 ≥3",
    "CRB-65 2-4",
    "CRB-65 4-5",
    "sat <92%",
    "saturation <85%",
    "temperatur >38°C",
    "alder >65",
    "RF >30/min",
    "BT <90/60",
    "Urea >7 mmol/l",
    "kapillærrespons >2 sek",
    "alder <6 måneder",
]


if __name__ == "__main__":
    # Test with sample text
    sample = """
    Start antibiotika hos børn med simpel pneumoni med oral amoxicillin 50 mg/kg/d fordelt på 2–3 doser. [S:SRC0023]
    Giv ved svær pneumoni i.v. benzyl-penicillin 100 mg/kg/d fordelt på 3 doser. [S:SRC0023]
    Stratificér voksne med pneumoni efter CURB-65 (alder >65; 1 point pr. parameter). [S:SRC0020]
    Patienter med CRB-65 score 2–4 bør indlægges, og intensiv behandling overvejes ved score 4–5. [S:SRC0026]
    Definér svær pneumoni hos børn ved >1 af: Sat <92%, takypnø, kapillærrespons >2 sek. [S:SRC0023]
    """

    result = validate_claim_extraction(sample)
    print(f"Total claims: {result['total_claims']}")
    print(f"By type: {result['by_type']}")
    print(f"With refs: {result['with_source_refs']}")
    print(f"Avg confidence: {result['avg_confidence']}")
    print("\nExtracted claims:")
    for claim in result['claims']:
        print(f"  [{claim.claim_type.value}] {claim.text} -> refs: {claim.source_refs}")
