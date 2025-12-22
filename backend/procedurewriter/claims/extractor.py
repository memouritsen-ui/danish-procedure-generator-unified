"""ClaimExtractor - Pattern-based claim extraction from medical procedure text.

This extractor uses regex patterns to identify verifiable medical claims:
- DOSE: Drug dosages (e.g., "amoxicillin 50 mg/kg/d")
- THRESHOLD: Clinical thresholds (e.g., "CURB-65 >= 3", "SpO2 < 92%")
- RECOMMENDATION: Clinical recommendations (e.g., "bør indlægges", "skal behandles")
- CONTRAINDICATION: When NOT to do something (e.g., "må ikke gives", "kontraindiceret")
- RED_FLAG: Warning signs requiring action (e.g., "OBS:", "mistanke om", "tilkald")
- ALGORITHM_STEP: Numbered procedure steps (e.g., "1. Sikr luftveje", "Trin 1:")

The patterns are derived from Phase 0 validation work on Danish medical procedures.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from procedurewriter.models.claims import Claim, ClaimType

if TYPE_CHECKING:
    from collections.abc import Sequence

# Regex patterns for dose extraction
DOSE_PATTERNS: list[re.Pattern[str]] = [
    # "amoxicillin 50 mg/kg/d fordelt pa 2-3 doser"
    re.compile(
        r"([a-zA-ZæøåÆØÅ\-]+)\s+(\d+(?:[.,]\d+)?)\s*(mg|g|mcg|μg|ml|IE|U)"
        r"(?:/kg)?(?:/d(?:ag|øgn)?)?(?:\s+(?:fordelt\s+pa|x)\s+"
        r"(\d+(?:-\d+)?)\s+(?:doser?|gange?))?",
        re.IGNORECASE,
    ),
    # "500 mg hver 12. time" or "500 mg x 2"
    re.compile(
        r"(\d+(?:[.,]\d+)?)\s*(mg|g|mcg|μg|ml)\s+(?:hver|x)\s+(\d+)\.?\s*(?:time|dag)?",
        re.IGNORECASE,
    ),
    # "750 mg p.o. hver 6. time" or "100 mg/kg i.v."
    re.compile(
        r"(\d+(?:[.,]\d+)?)\s*(mg|g)(?:/kg)?\s+(?:p\.?o\.?|i\.?v\.?)",
        re.IGNORECASE,
    ),
]

# Regex patterns for threshold extraction
THRESHOLD_PATTERNS: list[re.Pattern[str]] = [
    # "CURB-65 score 2-4", "CRB-65 >=3", "CURB-65 >= 3"
    re.compile(
        r"(CURB-65|CRB-65|CURB65|CRB65)\s*(?:score)?\s*"
        r"((?:>=|<=|>|<|≥|≤)?\s*\d+(?:-\d+)?)",
        re.IGNORECASE,
    ),
    # "saturation <92%", "sat <85%", "SpO2 <90%"
    re.compile(
        r"(?:sat(?:uration)?|SpO2|SaO2)\s*([<>≤≥])\s*(\d+)\s*%?",
        re.IGNORECASE,
    ),
    # "temperatur >38°C", "feber >38", "temp > 38"
    re.compile(
        r"(?:temperatur|feber|temp)\s*([<>≤≥])\s*(\d+(?:[.,]\d+)?)\s*°?C?",
        re.IGNORECASE,
    ),
    # "alder >65", "alder <6 maneder"
    re.compile(
        r"alder\s*([<>≤≥])\s*(\d+)\s*(år|måneder|mdr|uger)?",
        re.IGNORECASE,
    ),
    # "RF >30/min", "respirationsfrekvens"
    re.compile(
        r"(?:RF|respirationsfrekvens)\s*([<>≤≥])\s*(\d+)(?:/min)?",
        re.IGNORECASE,
    ),
    # "BT <90/60"
    re.compile(
        r"(?:BT|blodtryk)\s*([<>≤≥])\s*(\d+)/(\d+)",
        re.IGNORECASE,
    ),
]

# Regex patterns for recommendation extraction
# Danish modal verbs: "bør" (should), "skal" (must), "anbefales" (recommended)
# Note: Danish allows 0-3 words between modal and verb (e.g., "bør patienten indlægges")
RECOMMENDATION_PATTERNS: list[re.Pattern[str]] = [
    # "bør" + [0-3 words] + verb: bør indlægges, bør patienten indlægges, etc.
    re.compile(
        r"(bør\s+(?:\w+\s+){0,3}(?:indlægges|behandles|gives|vurderes|overvejes|"
        r"suppleres|pauseres|undgås|konfereres|monitoreres|sikres|"
        r"påbegyndes|afsluttes|seponeres|reduceres|øges|"
        r"administreres|ordineres|iværksættes|afventes|genoptages))",
        re.IGNORECASE,
    ),
    # "skal" + [0-3 words] + verb: skal indlægges, skal antibiotika gives, etc.
    re.compile(
        r"(skal\s+(?:\w+\s+){0,3}(?:indlægges|behandles|gives|vurderes|overvejes|"
        r"suppleres|pauseres|undgås|konfereres|monitoreres|sikres|"
        r"påbegyndes|afsluttes|seponeres|reduceres|øges|"
        r"administreres|ordineres|iværksættes|afventes|genoptages))",
        re.IGNORECASE,
    ),
    # "anbefales" patterns: det anbefales at, anbefales i.v., etc.
    re.compile(
        r"((?:det\s+)?anbefales\s+(?:at|i\.?v\.?|p\.?o\.?|ved|hvis|når)?)",
        re.IGNORECASE,
    ),
    # "anbefalet" patterns: den anbefalede behandling
    re.compile(
        r"((?:den\s+)?anbefale(?:t|de)\s+\w+)",
        re.IGNORECASE,
    ),
    # "tilrådes" patterns: tilrådes, det tilrådes at
    re.compile(
        r"((?:det\s+)?tilrådes(?:\s+at)?)",
        re.IGNORECASE,
    ),
    # "indicerer" / "indiceres" patterns
    re.compile(
        r"(indice(?:rer|res)\s+(?:\w+\s+)?(?:for|ved|behov)?)",
        re.IGNORECASE,
    ),
]

# Regex patterns for contraindication extraction
# Danish patterns: "må ikke" (must not), "kontraindiceret" (contraindicated), "aldrig" (never)
CONTRAINDICATION_PATTERNS: list[re.Pattern[str]] = [
    # "må ikke" + verb: må ikke gives, må ikke anvendes, etc.
    re.compile(
        r"(må\s+(?:ikke|aldrig)\s+(?:\w+\s+){0,2}(?:gives|anvendes|ordineres|"
        r"kombineres|administreres|bruges|benyttes|tages|indtages))",
        re.IGNORECASE,
    ),
    # "er kontraindiceret" patterns with optional modifiers
    re.compile(
        r"((?:er\s+)?(?:absolut|relativt)?\s*kontraindiceret(?:\s+(?:ved|hos|i))?)",
        re.IGNORECASE,
    ),
    # "kontraindikation" noun patterns
    re.compile(
        r"((?:absolut|relativ)?\s*kontraindikation(?:er)?(?:\s+(?:er|inkluderer|omfatter))?)",
        re.IGNORECASE,
    ),
    # "bør ikke" + verb patterns
    re.compile(
        r"(bør\s+ikke\s+(?:\w+\s+){0,2}(?:gives|anvendes|ordineres|"
        r"kombineres|administreres|bruges|benyttes|tages))",
        re.IGNORECASE,
    ),
    # "skal ikke" + verb patterns
    re.compile(
        r"(skal\s+ikke\s+(?:\w+\s+){0,2}(?:gives|anvendes|ordineres|"
        r"kombineres|administreres|bruges|benyttes|tages))",
        re.IGNORECASE,
    ),
    # "aldrig" patterns: aldrig give, giv aldrig, aldrig anvend
    re.compile(
        r"((?:aldrig\s+(?:give|anvend|brug|administrer|ordiner))|"
        r"(?:giv\s+aldrig))",
        re.IGNORECASE,
    ),
    # "undgå" imperative patterns
    re.compile(
        r"(undgå\s+(?:brug\s+af|anvendelse\s+af|at\s+give)?)",
        re.IGNORECASE,
    ),
]

# Regex patterns for red flag extraction
# Danish warning patterns: advarsel, OBS, vigtigt, kritisk, akut, mistanke, risiko
RED_FLAG_PATTERNS: list[re.Pattern[str]] = [
    # "advarsel" patterns: Advarsel:, advarselstegn, advarselssymptomer
    re.compile(
        r"(advarsel(?:stegn|ssymptomer)?(?:\s*:)?)",
        re.IGNORECASE,
    ),
    # "OBS" and "NB" attention patterns
    re.compile(
        r"((?:OBS|NB)\s*[!:])",
        re.IGNORECASE,
    ),
    # "vigtigt" patterns: Vigtigt:, vigtigt at
    re.compile(
        r"(vigtigt(?:\s*:|(?:\s+at)))",
        re.IGNORECASE,
    ),
    # "kritisk" and "livstruende" patterns
    re.compile(
        r"((?:kritisk|livstruende)\s+\w+)",
        re.IGNORECASE,
    ),
    # "akut" + urgency patterns: akut behov, akut risiko, akut fare, akut henvisning
    re.compile(
        r"(akut\s+(?:behov|risiko|fare|henvisning))",
        re.IGNORECASE,
    ),
    # "mistanke om" and "mistænkes" patterns
    re.compile(
        r"(mistanke\s+om|mistænkes)",
        re.IGNORECASE,
    ),
    # "risiko for" and "fare for" patterns
    re.compile(
        r"((?:høj\s+)?risiko\s+for|øget\s+risiko|fare\s+for)",
        re.IGNORECASE,
    ),
    # "henvis straks/akut" patterns
    re.compile(
        r"(henvis\s+(?:straks|akut))",
        re.IGNORECASE,
    ),
    # "tilkald" patterns: tilkald, tilkald hjælp
    re.compile(
        r"(tilkald(?:\s+\w+)?)",
        re.IGNORECASE,
    ),
    # "kontakt straks" patterns
    re.compile(
        r"(kontakt\s+straks)",
        re.IGNORECASE,
    ),
    # "øjeblikkelig" patterns
    re.compile(
        r"(øjeblikkelig\s+\w+)",
        re.IGNORECASE,
    ),
    # "straks" in treatment context
    re.compile(
        r"((?:behandling|intervention)\s+straks)",
        re.IGNORECASE,
    ),
]

# Regex patterns for algorithm step extraction
# Danish step patterns: numbered (1. 2. 3.), lettered (A. B. C.), Trin X, Fase X, etc.
ALGORITHM_STEP_PATTERNS: list[re.Pattern[str]] = [
    # "1. Action" or "1: Action" or "1) Action" - numbered steps at line start
    # Must be at start of line to avoid matching numbers mid-sentence
    re.compile(
        r"^(\d{1,2}[.):]\s+\S.+)",
        re.MULTILINE,
    ),
    # "Trin 1:" or "Trin 1" or "TRIN 1:" - Step prefix
    re.compile(
        r"((?:trin|TRIN)\s+\d+\s*:?\s*\S.+)",
        re.IGNORECASE,
    ),
    # "Fase 1:" or "FASE 1:" - Phase prefix
    re.compile(
        r"((?:fase|FASE)\s+\d+\s*:?\s*\S.+)",
        re.IGNORECASE,
    ),
    # "Del 1:" or "DEL 1:" - Part prefix
    re.compile(
        r"((?:del|DEL)\s+\d+\s*:?\s*\S.+)",
        re.IGNORECASE,
    ),
    # "A. Action" or "A) Action" - uppercase lettered steps at line start
    re.compile(
        r"^([A-Z][.):]\s+\S.+)",
        re.MULTILINE,
    ),
    # "a. Action" or "a) Action" - lowercase lettered steps at line start
    re.compile(
        r"^([a-z][.):]\s+\S.+)",
        re.MULTILINE,
    ),
    # "Første:" or "Andet:" or "Tredje:" or "Fjerde:" - Danish ordinals
    re.compile(
        r"((?:første|andet|tredje|fjerde|femte|sjette|syvende|ottende|niende|tiende)\s*:\s*\S.+)",
        re.IGNORECASE,
    ),
]

# Pattern for source references [SRC001] or [S:SRC001]
SOURCE_REF_PATTERN = re.compile(r"\[S?:?SRC(\d+)\]", re.IGNORECASE)


class ClaimExtractor:
    """Pattern-based extractor for medical claims.

    Uses regex patterns to identify verifiable medical claims from procedure text.
    This is deterministic and testable, unlike LLM-based extraction.

    Attributes:
        run_id: Pipeline run ID to associate with extracted claims.
    """

    def __init__(self, run_id: str = "") -> None:
        """Initialize the claim extractor.

        Args:
            run_id: Pipeline run ID for extracted claims. Defaults to empty string.
        """
        self.run_id = run_id

    def extract(self, text: str) -> list[Claim]:
        """Extract all claims from procedure text.

        Processes text line by line, extracting dose and threshold claims.
        Skips empty lines and markdown header lines (starting with #).

        Args:
            text: Procedure text to extract claims from.

        Returns:
            List of Claim objects with claim_type, text, line_number, etc.
        """
        if not text or not text.strip():
            return []

        claims: list[Claim] = []

        for line_num, line in enumerate(text.split("\n"), start=1):
            # Skip empty lines and markdown headers
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            # Extract source refs from this line
            source_refs = self._extract_source_refs(line)

            # Extract doses
            claims.extend(self._extract_doses(line, line_num, source_refs))

            # Extract thresholds
            claims.extend(self._extract_thresholds(line, line_num, source_refs))

            # Extract recommendations
            claims.extend(self._extract_recommendations(line, line_num, source_refs))

            # Extract contraindications
            claims.extend(self._extract_contraindications(line, line_num, source_refs))

            # Extract red flags
            claims.extend(self._extract_red_flags(line, line_num, source_refs))

            # Extract algorithm steps
            claims.extend(self._extract_algorithm_steps(line, line_num, source_refs))

        return claims

    def extract_all(self, text: str) -> list[Claim]:
        """Alias for extract() method.

        Args:
            text: Procedure text to extract claims from.

        Returns:
            List of Claim objects.
        """
        return self.extract(text)

    def _extract_source_refs(self, text: str) -> list[str]:
        """Extract source reference IDs from text.

        Looks for patterns like [SRC001] or [S:SRC001].

        Args:
            text: Line of text to search.

        Returns:
            List of source reference strings (e.g., ["SRC0023"]).
        """
        matches = SOURCE_REF_PATTERN.findall(text)
        return [f"SRC{m}" for m in matches]

    def _extract_doses(
        self,
        line: str,
        line_num: int,
        source_refs: list[str],
    ) -> list[Claim]:
        """Extract dose claims from a line of text.

        Args:
            line: Line of text to search.
            line_num: Line number (1-based).
            source_refs: Source references found on this line.

        Returns:
            List of dose claims found.
        """
        claims: list[Claim] = []

        for pattern in DOSE_PATTERNS:
            for match in pattern.finditer(line):
                full_text = match.group(0)
                # Confidence is higher if we have source references
                confidence = 0.9 if source_refs else 0.6

                claim = Claim(
                    run_id=self.run_id,
                    claim_type=ClaimType.DOSE,
                    text=full_text,
                    normalized_value=self._extract_numeric_value(match),
                    unit=self._extract_unit(match),
                    source_refs=source_refs.copy(),
                    line_number=line_num,
                    confidence=confidence,
                )
                claims.append(claim)

        return claims

    def _extract_thresholds(
        self,
        line: str,
        line_num: int,
        source_refs: list[str],
    ) -> list[Claim]:
        """Extract threshold claims from a line of text.

        Args:
            line: Line of text to search.
            line_num: Line number (1-based).
            source_refs: Source references found on this line.

        Returns:
            List of threshold claims found.
        """
        claims: list[Claim] = []

        for pattern in THRESHOLD_PATTERNS:
            for match in pattern.finditer(line):
                full_text = match.group(0)
                # Confidence is higher if we have source references
                confidence = 0.85 if source_refs else 0.5

                claim = Claim(
                    run_id=self.run_id,
                    claim_type=ClaimType.THRESHOLD,
                    text=full_text,
                    normalized_value=full_text,  # Thresholds use full text as value
                    unit=None,
                    source_refs=source_refs.copy(),
                    line_number=line_num,
                    confidence=confidence,
                )
                claims.append(claim)

        return claims

    def _extract_numeric_value(self, match: re.Match[str]) -> str | None:
        """Extract numeric value from regex match.

        Tries to find the first numeric group in the match.

        Args:
            match: Regex match object.

        Returns:
            Numeric value as string, or None if not found.
        """
        for i in range(1, match.lastindex + 1 if match.lastindex else 1):
            group = match.group(i)
            if group and re.match(r"^\d+(?:[.,]\d+)?$", group):
                return group
        return None

    def _extract_unit(self, match: re.Match[str]) -> str | None:
        """Extract unit from regex match.

        Looks for common medical units in match groups.

        Args:
            match: Regex match object.

        Returns:
            Unit string, or None if not found.
        """
        units = {"mg", "g", "mcg", "μg", "ml", "IE", "U"}
        for i in range(1, match.lastindex + 1 if match.lastindex else 1):
            group = match.group(i)
            if group and group.lower() in {u.lower() for u in units}:
                return group
        return None

    def _extract_recommendations(
        self,
        line: str,
        line_num: int,
        source_refs: list[str],
    ) -> list[Claim]:
        """Extract recommendation claims from a line of text.

        Identifies Danish modal verbs: bør (should), skal (must), anbefales (recommended).

        Args:
            line: Line of text to search.
            line_num: Line number (1-based).
            source_refs: Source references found on this line.

        Returns:
            List of recommendation claims found.
        """
        claims: list[Claim] = []

        for pattern in RECOMMENDATION_PATTERNS:
            for match in pattern.finditer(line):
                full_text = match.group(0)
                # Confidence is higher if we have source references
                confidence = 0.85 if source_refs else 0.6

                claim = Claim(
                    run_id=self.run_id,
                    claim_type=ClaimType.RECOMMENDATION,
                    text=full_text,
                    normalized_value=full_text.strip(),
                    unit=None,
                    source_refs=source_refs.copy(),
                    line_number=line_num,
                    confidence=confidence,
                )
                claims.append(claim)

        return claims

    def _extract_contraindications(
        self,
        line: str,
        line_num: int,
        source_refs: list[str],
    ) -> list[Claim]:
        """Extract contraindication claims from a line of text.

        Identifies Danish contraindication patterns: må ikke (must not),
        kontraindiceret (contraindicated), aldrig (never), undgå (avoid).

        Args:
            line: Line of text to search.
            line_num: Line number (1-based).
            source_refs: Source references found on this line.

        Returns:
            List of contraindication claims found.
        """
        claims: list[Claim] = []

        for pattern in CONTRAINDICATION_PATTERNS:
            for match in pattern.finditer(line):
                full_text = match.group(0)
                # Confidence is higher if we have source references
                confidence = 0.9 if source_refs else 0.7

                claim = Claim(
                    run_id=self.run_id,
                    claim_type=ClaimType.CONTRAINDICATION,
                    text=full_text,
                    normalized_value=full_text.strip(),
                    unit=None,
                    source_refs=source_refs.copy(),
                    line_number=line_num,
                    confidence=confidence,
                )
                claims.append(claim)

        return claims

    def _extract_red_flags(
        self,
        line: str,
        line_num: int,
        source_refs: list[str],
    ) -> list[Claim]:
        """Extract red flag claims from a line of text.

        Identifies Danish warning sign patterns: advarsel (warning),
        OBS (attention), vigtigt (important), kritisk (critical),
        akut (acute), mistanke (suspicion), risiko (risk).

        Args:
            line: Line of text to search.
            line_num: Line number (1-based).
            source_refs: Source references found on this line.

        Returns:
            List of red flag claims found.
        """
        claims: list[Claim] = []

        for pattern in RED_FLAG_PATTERNS:
            for match in pattern.finditer(line):
                full_text = match.group(0)
                # Confidence is higher if we have source references
                confidence = 0.9 if source_refs else 0.7

                claim = Claim(
                    run_id=self.run_id,
                    claim_type=ClaimType.RED_FLAG,
                    text=full_text,
                    normalized_value=full_text.strip(),
                    unit=None,
                    source_refs=source_refs.copy(),
                    line_number=line_num,
                    confidence=confidence,
                )
                claims.append(claim)

        return claims

    def _extract_algorithm_steps(
        self,
        line: str,
        line_num: int,
        source_refs: list[str],
    ) -> list[Claim]:
        """Extract algorithm step claims from a line of text.

        Identifies Danish step patterns: numbered steps (1. 2. 3.),
        lettered steps (A. B. C.), Trin X (Step X), Fase X (Phase X),
        Del X (Part X), and ordinal patterns (Første, Andet, etc.).

        Args:
            line: Line of text to search.
            line_num: Line number (1-based).
            source_refs: Source references found on this line.

        Returns:
            List of algorithm step claims found.
        """
        claims: list[Claim] = []

        for pattern in ALGORITHM_STEP_PATTERNS:
            for match in pattern.finditer(line):
                full_text = match.group(0)
                # Confidence is higher if we have source references
                confidence = 0.85 if source_refs else 0.65

                claim = Claim(
                    run_id=self.run_id,
                    claim_type=ClaimType.ALGORITHM_STEP,
                    text=full_text,
                    normalized_value=full_text.strip(),
                    unit=None,
                    source_refs=source_refs.copy(),
                    line_number=line_num,
                    confidence=confidence,
                )
                claims.append(claim)

        return claims
