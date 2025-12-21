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

Din opgave er at polere teksten stilistisk UDEN at ændre struktur eller indhold.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REDAKTIONELLE PRINCIPPER:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. BYDENDE IMPERATIV-FORM i procedureafsnit:
   FORKERT: "Patienten placeres i liggende position"
   KORREKT: "Placér patienten i sideleje med flekteret ryg"
   FORKERT: "Der desinficeres med klorhexidin"
   KORREKT: "Desinficér huden med klorhexidin-sprit i 2 omgange"

2. SPECIFIKKE NAVNE, IKKE GENERISKE:
   FORKERT: "Sterile lumbalpunktursæt"
   KORREKT: "Atraumatisk LP-nål med introducer, fx Sprotte eller Whitacre"
   FORKERT: "Desinfektionsmiddel"
   KORREKT: "Klorhexidin 0.5% i sprit"

3. KOMPETENCE-BEVIDSTHED hvor relevant:
   "Søg hjælp hos erfaren kollega, hvis du ikke er godkendt til..."
   "Spørg kollega ved tvivl om afdelingens vanlige udstyr"

4. HANDLINGSRETTET SIKKERHED:
   FORKERT: "ADVARSEL: Vær opmærksom på tegn på infektion"
   KORREKT: "Gennemgå altid kontraindikationer før start"
   Giv HANDLINGER, ikke advarsler.

5. PRAKTISKE DETALJER inline:
   "(det kan være en langsommelig proces)"
   "(spørg til afdelingens vanlige udstyr)"
   "(lokal protokol varierer)"

6. KRYSTALKLART SPROG:
   - Ingen unødige formuleringer
   - Ingen passiv form hvor aktiv kan bruges
   - Korte, præcise sætninger

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ABSOLUTTE REGLER (må ALDRIG brydes):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. BEVAR ALLE sektionsoverskrifter (## Overskrifter) PRÆCIST som de er
2. BEVAR ALLE citations [S:SRC0001], [S:SRC0002] osv. PRÆCIST
   (Format er [S:<source_id>], fx [S:SRC0001] - bevar dette format UÆNDRET)
3. BEVAR alle fakta og medicinsk indhold
4. Fjern markdown-syntaks (**bold**, *italic*) - brug ren tekst
5. TILFØJ ALDRIG nye sektioner - behold strukturen som den er
6. FJERN ALDRIG eksisterende sektioner

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
        strict_mode: bool = False,
    ) -> AgentResult[StyleOutput]:
        """Execute style polishing with citation validation.

        Args:
            input_data: StyleInput with raw markdown and style profile
            max_retries: Number of retry attempts if citations are missing
            strict_mode: If True, raise StyleValidationError on missing citations
                        instead of adding fallback section

        Raises:
            StyleValidationError: When strict_mode=True and citations are missing
                                 after all retries
        """
        self.reset_stats()

        profile = input_data.style_profile
        original_citations = self._extract_citations(input_data.raw_markdown)
        original_headings = self._extract_headings(input_data.raw_markdown)

        system_prompt = STYLE_SYSTEM_PROMPT.format(
            tone_description=profile.tone_description,
            target_audience=profile.target_audience,
            detail_level=profile.detail_level,
            heading_style=profile.heading_style,
            list_style=profile.list_style,
            citation_style=profile.citation_style,
        )

        # List all citations explicitly in the prompt - use correct [S:xxx] format
        citations_list = ", ".join(sorted(original_citations))

        user_prompt = f"""Polér følgende procedure stilistisk til bogkvalitet.

KRITISK: Du SKAL bevare ALLE disse citations i dit output: {citations_list}
Hver citation skal stå præcist som vist (fx [S:SRC0001]) et sted i teksten.

KRITISK: Bevar ALLE sektioner og overskrifter PRÆCIST som de er. Tilføj INGEN nye sektioner.

ORIGINAL TEKST:
{input_data.raw_markdown}

OUTPUT KRAV:
- Bevar alle {len(original_citations)} citations: {citations_list}
- Bevar alle sektionsoverskrifter uændret
- Brug imperativ form i proceduretrin
- Ingen nye sektioner - kun stilistisk polering"""

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
            polished_headings = self._extract_headings(polished)

            missing_citations = original_citations - polished_citations
            missing_headings = original_headings - polished_headings
            added_headings = polished_headings - original_headings

            # Check for structural violations in strict mode
            if strict_mode and (missing_headings or added_headings):
                raise StyleValidationError(
                    f"StyleAgent modified document structure in strict mode. "
                    f"Missing headings: {missing_headings}, Added headings: {added_headings}",
                    missing_citations=missing_citations,
                )

            if not missing_citations:
                warnings = []
                if added_headings:
                    warnings.append(f"New sections added by style polishing: {added_headings}")
                if missing_headings:
                    warnings.append(f"Sections removed by style polishing: {missing_headings}")

                return AgentResult(
                    output=StyleOutput(
                        success=True,
                        polished_markdown=polished,
                        applied_rules=[
                            f"tone: {profile.tone_description}",
                            f"audience: {profile.target_audience}",
                            f"detail: {profile.detail_level}",
                        ],
                        warnings=warnings,
                    ),
                    stats=self.get_stats(),
                )

            # Retry with stronger prompt - include previous attempt for context
            missing_list = ", ".join(sorted(missing_citations))
            user_prompt = f"""FEJL: Dit tidligere forsøg manglede disse citations: {missing_list}

Du SKAL inkludere ALLE {len(original_citations)} citations fra originalen.

KOMPLET LISTE AF PÅKRÆVEDE CITATIONS: {citations_list}

Du må IKKE udelade nogen af disse. Placer dem ved relevante fakta.
Du må IKKE tilføje nye sektioner eller ændre overskrifter.

ORIGINAL TEKST:
{input_data.raw_markdown}

FORSØG IGEN og inkluder ALLE citations denne gang."""

        # All retries failed
        if strict_mode:
            raise StyleValidationError(
                f"StyleAgent failed to preserve all citations after {max_retries + 1} attempts. "
                f"Missing: {missing_citations}",
                missing_citations=missing_citations,
            )

        # Non-strict mode: return polished text with warning (no fallback section injection)
        return AgentResult(
            output=StyleOutput(
                success=False,  # Mark as failure since citations were lost
                polished_markdown=polished,
                applied_rules=[
                    f"tone: {profile.tone_description}",
                    f"audience: {profile.target_audience}",
                    f"detail: {profile.detail_level}",
                ],
                warnings=[f"Citations lost during polishing: {missing_citations}"],
            ),
            stats=self.get_stats(),
        )

    def _extract_headings(self, text: str) -> set[str]:
        """Extract all ## Heading style headings from text."""
        headings: set[str] = set()
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("## "):
                headings.add(line[3:].strip())
        return headings

    def _extract_citations(self, text: str) -> set[str]:
        """Extract all [S:SRC0001] style citations from text.

        The pipeline uses [S:<source_id>] format, e.g., [S:SRC0001].
        """
        return set(re.findall(r'\[S:[^\]]+\]', text))
