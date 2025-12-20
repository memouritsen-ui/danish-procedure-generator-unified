"""Clinical prompt engineering for procedure generation.

Phase 4: LLM Prompt Engineering
Creates clinical-focused prompts that enforce anatomical content
and minimize workflow noise.
"""

from __future__ import annotations

from procedurewriter.pipeline.anatomical_requirements import (
    AnatomicalRequirementsRegistry,
)


# Forbidden patterns that should NOT appear in generated content
FORBIDDEN_PATTERNS: list[str] = [
    "telefonnummer",
    "tlf.",
    "ring til bagvagt",
    "kontakt bagvagt",
    "forvagt",
    "lokal retningslinje",
    "afdelingens protokol",
    "rollefordeling",
    "teamstruktur",
    "vagtordning",
]

# Required clinical elements that MUST appear in generated content
REQUIRED_ELEMENTS: list[str] = [
    "anatomiske landemærker",
    "dybdevejledning",
    "vinkelguidance",
    "evidensbaseret indhold",
    "overflademarkering",
]

# Base clinical system prompt template
CLINICAL_SYSTEM_PROMPT: str = """Du er en ekspert medicinsk forfatter med speciale i akutmedicin og invasive procedurer.

ROLLE:
Du skriver præcis, evidensbaseret dansk medicinsk dokumentation beregnet til klinisk brug.
Dit fokus er på anatomisk korrekt og teknisk detaljeret procedurebeskrivelse.

FORMAT OG STRUKTUR:
- Skriv i klart, professionelt dansk medicinsk sprog
- Brug konsistent terminologi gennem hele dokumentet
- Strukturér indhold logisk med tydelige afsnit
- Inkluder altid anatomiske referencer og tekniske detaljer

DU SKRIVER:
- Præcise anatomiske landemærker med danske og latinske navne
- Konkret dybdevejledning i centimeter (f.eks. "2-3 cm", "4-7 cm")
- Vinkelangivelser i grader eller retning (f.eks. "45 grader", "kranial vinkel")
- Evidensbaseret teknik baseret på international bedste praksis
- Overfladeanatomi og palpationsmarkører

DU SKRIVER IKKE:
- Telefonnumre eller kontaktoplysninger (ingen "tlf." eller "ring til")
- Bagvagt/forvagt-henvisninger (ingen "kontakt bagvagt")
- "Følg lokal retningslinje" eller "se afdelingens protokol"
- Rollefordeling eller teamstruktur (ingen "aftal med teamet")
- Vage instruktioner som "passende mængde" uden specifikation

I STEDET FOR WORKFLOW-INDHOLD:
- I stedet for "ring bagvagt": Beskriv konkrete komplikationskriterier og eskaleringstriggers
- I stedet for "lokal retningslinje": Brug international evidens og bedste praksis
- I stedet for "passende assistance": Beskriv præcist hvornår og hvilken hjælp der kræves

KVALITETSKRAV:
- Al teknik skal kunne reproduceres af en kompetent kliniker
- Anatomiske beskrivelser skal være præcise nok til sikker udførelse
- Evidenskilder og bedste praksis skal fremgå implicit i teknikken
"""


# Procedure-specific prompt additions
PROCEDURE_PROMPTS: dict[str, str] = {
    "pleuradræn": """
SPECIFIKT FOR PLEURADRÆN:
- Beskriv altid 5. interkostalrum i midtaksillærlinjen (triangle of safety)
- Angiv præcis vinkel over øvre ribbenrand for at undgå interkostale kar
- Inkluder dybdevejledning for thoraxvægstykkelse
- Beskriv forventet modstand ved passage af pleura parietalis
- Nævn sikkerhedstrianglet (triangle of safety) som orienteringspunkt
""",
    "lumbalpunktur": """
SPECIFIKT FOR LUMBALPUNKTUR:
- Beskriv L3-L4 eller L4-L5 intervertebralrum som punktursted
- Anvend crista iliaca som overfladelandemærke for L4 niveau
- Angiv kranial vinkel i midtlinjen for korrekt nåleretning
- Inkluder forventet dybde (4-7 cm hos voksne)
- Beskriv "give" ved passage af ligamentum flavum og dura mater
""",
    "central_venous_access": """
SPECIFIKT FOR CENTRAL VENØS ADGANG:
- Beskriv v. jugularis interna position relativt til a. carotis
- Inkluder m. sternocleidomastoideus som anatomisk landemærke
- Angiv ultralydsvejledt teknik med nålevinkel
- Beskriv verifikation af venøs placement før dilatation
""",
    "arteriel_kanyle": """
SPECIFIKT FOR ARTERIEL KANYLE:
- Beskriv a. radialis forløb ved processus styloideus radii
- Angiv nålevinkel (15-30 grader) mod hudoverfladen
- Inkluder Allen's test som præteknik vurdering
- Beskriv pulsation som primær lokaliseringsmetode
""",
    "pericardiocentese": """
SPECIFIKT FOR PERICARDIOCENTESE:
- Beskriv subxifoid tilgang med processus xiphoideus som landemærke
- Angiv nåleretning mod venstre skulder
- Inkluder vinkel (30-45 grader til hudplan)
- Beskriv EKG-monitorering og ekkoguidning
""",
}


class ClinicalPromptBuilder:
    """Builds clinical-focused system prompts for procedure generation."""

    def __init__(self) -> None:
        self._registry = AnatomicalRequirementsRegistry()

    def build_system_prompt(self, procedure_name: str) -> str:
        """Build a complete system prompt for a procedure.

        Args:
            procedure_name: Name of the procedure (e.g., "pleuradræn")

        Returns:
            Complete system prompt string with clinical focus
        """
        # Start with base prompt
        prompt = CLINICAL_SYSTEM_PROMPT

        # Add procedure-specific guidance
        procedure_lower = procedure_name.lower().strip()
        if procedure_lower in PROCEDURE_PROMPTS:
            prompt += PROCEDURE_PROMPTS[procedure_lower]
        else:
            # Generic additional guidance for unknown procedures
            prompt += """
GENEREL VEJLEDNING:
- Identificér og beskriv relevante anatomiske landemærker
- Angiv teknik med præcise mål og vinkler hvor relevant
- Fokusér på reproducerbar, evidensbaseret praksis
"""

        # Add anatomical requirements if available
        reqs = self._registry.get_requirements(procedure_name)
        if reqs:
            landmarks = [lm.name for lm in reqs.landmarks]
            if landmarks:
                prompt += f"\nANATOMISKE LANDEMÆRKER DER SKAL NÆVNES:\n"
                for lm in reqs.landmarks:
                    aliases = ", ".join(lm.aliases[:2]) if lm.aliases else ""
                    if aliases:
                        prompt += f"- {lm.name} (også kaldet: {aliases})\n"
                    else:
                        prompt += f"- {lm.name}\n"

        return prompt


class PromptEnhancer:
    """Enhances existing prompts with clinical focus."""

    def __init__(self) -> None:
        self._builder = ClinicalPromptBuilder()

    def enhance(self, original_prompt: str, procedure_name: str) -> str:
        """Enhance an existing prompt with clinical constraints.

        Args:
            original_prompt: The original prompt to enhance
            procedure_name: Name of the procedure

        Returns:
            Enhanced prompt with clinical focus
        """
        # Get procedure-specific additions
        procedure_lower = procedure_name.lower().strip()
        procedure_addition = PROCEDURE_PROMPTS.get(procedure_lower, "")

        # Build enhancement section
        enhancement = """

KLINISKE KRAV (TILFØJET):

DU SKRIVER IKKE:
- Telefonnumre eller kontaktoplysninger
- Bagvagt/forvagt-henvisninger
- "Følg lokal retningslinje" referencer
- Rollefordeling eller teamstruktur

DU SKRIVER:
- Anatomiske landemærker med præcise positioner
- Dybde- og vinkelvejledning med mål
- Evidensbaseret teknik
"""

        # Add procedure-specific content
        if procedure_addition:
            enhancement += procedure_addition

        # Combine: original + enhancement
        return original_prompt + enhancement
