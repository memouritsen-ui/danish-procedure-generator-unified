"""StyleAgent for LLM-powered markdown polishing.

Transforms raw procedure markdown into professionally-written medical text
while preserving all citations and factual content.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict

from procedurewriter.agents.base import AgentInput, AgentOutput, AgentResult, BaseAgent
from procedurewriter.models.style_profile import StyleProfile
from procedurewriter.pipeline.types import SourceRecord


class StyleValidationError(Exception):
    """Raised when polished output fails validation."""

    def __init__(self, message: str, missing_citations: set[str] | None = None):
        super().__init__(message)
        self.missing_citations = missing_citations or set()


class StyleInput(AgentInput):
    """Input for StyleAgent."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    raw_markdown: str
    sources: list[Any] = []  # SourceRecord, but using Any for flexibility
    style_profile: StyleProfile


class StyleOutput(AgentOutput):
    """Output from StyleAgent."""

    polished_markdown: str = ""
    applied_rules: list[str] = []
    warnings: list[str] = []


STYLE_SYSTEM_PROMPT = """Du er en erfaren medicinsk redaktør af kliniske procedurebøger.

Din opgave er at omskrive procedurer så de følger denne REDAKTIONELLE RAMME:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OBLIGATORISK STRUKTUR (følg denne rækkefølge):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Indikationer
2. Kontraindikationer
3. Forberedelse (inkl. kompetencevurdering)
4. Udstyr (specifikt efter forberedelse)
5. Fremgangsmåde
6. Forklaringslag ← TILFØJ DETTE AFSNIT
7. Sikkerhedsboks
8. Komplikationer
9. Disposition og opfølgning

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REDAKTIONELLE PRINCIPPER:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. BYDENDE IMPERATIV-FORM i Fremgangsmåde:
   FORKERT: "Patienten placeres i liggende position"
   KORREKT: "Placér patienten i sideleje med flekteret ryg"
   FORKERT: "Der desinficeres med klorhexidin"
   KORREKT: "Desinficér huden med klorhexidin-sprit i 2 omgange"

2. SPECIFIKKE NAVNE, IKKE GENERISKE:
   FORKERT: "Sterile lumbalpunktursæt"
   KORREKT: "Atraumatisk LP-nål med introducer, fx Sprotte eller Whitacre"
   FORKERT: "Desinfektionsmiddel"
   KORREKT: "Klorhexidin 0.5% i sprit"

3. FORKLARINGSLAG (obligatorisk sektion efter Fremgangsmåde):
   Tilføj et afsnit der forklarer:
   - HVORFOR specifikke valg træffes
   - Evidensgrundlag for anbefalinger
   - Rationalet bag teknikken
   Eksempel: "Brug af atraumatisk nål reducerer risikoen for
   postdural punktur-hovedpine og bør være standard."

4. KOMPETENCE-BEVIDSTHED i Forberedelse:
   Tilføj: "Søg hjælp hos erfaren kollega, hvis du ikke er godkendt til..."
   Tilføj: "Spørg kollega ved tvivl om afdelingens vanlige udstyr"

5. HANDLINGSRETTET SIKKERHED i Sikkerhedsboks:
   FORKERT: "ADVARSEL: Vær opmærksom på tegn på infektion"
   KORREKT: "Gennemgå altid kontraindikationer før start"
   Giv HANDLINGER, ikke advarsler.

6. PRAKTISKE DETALJER inline:
   Tilføj: "(det kan være en langsommelig proces)"
   Tilføj: "(spørg til afdelingens vanlige udstyr)"
   Tilføj: "(lokal protokol varierer)"

7. FEJLHÅNDTERING INLINE i Fremgangsmåde:
   "Ved mistanke om kontaminering: gør steril teknik om"
   "Dry tap: ny indstiksretning eller nyt interspatie"

8. KRYSTALKLART SPROG:
   - Ingen unødige formuleringer
   - Ingen passiv form hvor aktiv kan bruges
   - Ingen sproglige variationer for variationens skyld
   - Korte, præcise sætninger

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ABSOLUTTE REGLER (må ALDRIG brydes):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. BEVAR alle citations [SRC0001], [SRC0002] osv. PRÆCIST
2. BEVAR alle fakta og medicinsk indhold
3. Fjern markdown-syntaks (**bold**, *italic*) - brug ren tekst
4. Bevar sektionsoverskrifter som ## Overskrift

STIL-PROFIL: {tone_description}
MÅLGRUPPE: {target_audience}
DETALJENIVEAU: {detail_level}
OVERSKRIFTSSTIL: {heading_style}
LISTESTIL: {list_style}
CITATIONSSTIL: {citation_style}"""


class StyleAgent(BaseAgent[StyleInput, StyleOutput]):
    """Agent that polishes markdown to professional medical writing style."""

    @property
    def name(self) -> str:
        return "StyleAgent"

    def execute(
        self,
        input_data: StyleInput,
        max_retries: int = 3,
    ) -> AgentResult[StyleOutput]:
        """Execute style polishing with citation validation."""
        self.reset_stats()

        profile = input_data.style_profile
        original_citations = self._extract_citations(input_data.raw_markdown)

        system_prompt = STYLE_SYSTEM_PROMPT.format(
            tone_description=profile.tone_description,
            target_audience=profile.target_audience,
            detail_level=profile.detail_level,
            heading_style=profile.heading_style,
            list_style=profile.list_style,
            citation_style=profile.citation_style,
        )

        # List all citations explicitly in the prompt
        citations_list = ", ".join(sorted(original_citations))

        user_prompt = f"""Omskriv følgende procedure til bogkvalitet.

KRITISK: Du SKAL bevare ALLE disse citations i dit output: {citations_list}
Hver citation skal stå præcist som vist (fx [SRC0001]) et sted i teksten.

ORIGINAL TEKST:
{input_data.raw_markdown}

OUTPUT KRAV:
- Bevar alle {len(original_citations)} citations: {citations_list}
- Følg den redaktionelle ramme præcist
- Tilføj Forklaringslag-sektion
- Brug imperativ form i Fremgangsmåde"""

        for attempt in range(max_retries + 1):
            response = self.llm_call(
                messages=[
                    self._make_system_message(system_prompt),
                    self._make_user_message(user_prompt),
                ],
                temperature=0.3,
            )

            polished = response.content
            polished_citations = self._extract_citations(polished)

            missing = original_citations - polished_citations
            if not missing:
                return AgentResult(
                    output=StyleOutput(
                        success=True,
                        polished_markdown=polished,
                        applied_rules=[
                            f"tone: {profile.tone_description}",
                            f"audience: {profile.target_audience}",
                            f"detail: {profile.detail_level}",
                        ],
                        warnings=[],
                    ),
                    stats=self.get_stats(),
                )

            # Retry with stronger prompt - include previous attempt for context
            missing_list = ", ".join(sorted(missing))
            user_prompt = f"""FEJL: Dit tidligere forsøg manglede disse citations: {missing_list}

Du SKAL inkludere ALLE {len(original_citations)} citations fra originalen.

KOMPLET LISTE AF PÅKRÆVEDE CITATIONS: {citations_list}

Du må IKKE udelade nogen af disse. Placer dem ved relevante fakta.

ORIGINAL TEKST:
{input_data.raw_markdown}

FORSØG IGEN og inkluder ALLE citations denne gang."""

        # All retries failed - use best attempt with warning
        # Insert missing citations at end of document with note
        missing_refs = "\n\n## Supplerende referencer\n" + "\n".join(
            f"- {cit}: Se originalkilde" for cit in sorted(missing)
        )
        polished_with_missing = polished + missing_refs

        return AgentResult(
            output=StyleOutput(
                success=True,  # Accept with warnings rather than failing
                polished_markdown=polished_with_missing,
                applied_rules=[
                    f"tone: {profile.tone_description}",
                    f"audience: {profile.target_audience}",
                    f"detail: {profile.detail_level}",
                ],
                warnings=[f"Nogle citations blev tilføjet som supplerende referencer: {missing}"],
            ),
            stats=self.get_stats(),
        )

    def _extract_citations(self, text: str) -> set[str]:
        """Extract all [SRC0001] style citations from text."""
        return set(re.findall(r'\[SRC\d+\]', text))
