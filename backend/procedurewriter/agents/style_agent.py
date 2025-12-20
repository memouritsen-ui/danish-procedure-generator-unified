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


STYLE_SYSTEM_PROMPT = """Du er en erfaren medicinsk redaktør og forfatter af kliniske lærebøger.

Din opgave er at omskrive procedurer til professionel bogkvalitet.

ABSOLUTTE REGLER (må ALDRIG brydes):
1. BEVAR alle citations [SRC0001], [SRC0002] osv. PRÆCIST som de er
2. BEVAR alle fakta og medicinsk indhold - omskriv KUN formuleringen
3. Fjern markdown-syntaks (**bold**, *italic*) - brug ren tekst
4. Bevar alle sektionsoverskrifter

STIL-PROFIL:
{tone_description}

MÅLGRUPPE: {target_audience}

DETALJENIVEAU: {detail_level}

FORMATERINGSINSTRUKTIONER:
- Overskriftsstil: {heading_style}
- Listestil: {list_style}
- Citationsstil: {citation_style}

Omskriv teksten så den:
- Har flydende, professionelle overgange mellem afsnit
- Bruger korrekt medicinsk terminologi
- Er klar og præcis
- Passer til målgruppen"""


class StyleAgent(BaseAgent[StyleInput, StyleOutput]):
    """Agent that polishes markdown to professional medical writing style."""

    @property
    def name(self) -> str:
        return "StyleAgent"

    def execute(
        self,
        input_data: StyleInput,
        max_retries: int = 2,
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

        user_prompt = f"""Omskriv følgende procedure til bogkvalitet:

{input_data.raw_markdown}

HUSK: Alle citations [SRC0001] osv. SKAL bevares præcist!"""

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

            # Retry with stronger prompt
            user_prompt = f"""FEJL: Du manglede disse citations: {missing}

Du SKAL inkludere ALLE citations fra originalen. Prøv igen:

{input_data.raw_markdown}

KRITISK: Hver eneste [SRC0001], [SRC0002] osv. SKAL være i dit output!"""

        # All retries failed
        return AgentResult(
            output=StyleOutput(
                success=False,
                polished_markdown=input_data.raw_markdown,  # Fallback to original
                applied_rules=[],
                warnings=[f"Citation validation failed after {max_retries + 1} attempts. Missing: {missing}"],
                error=f"Manglende citations: {missing}",
            ),
            stats=self.get_stats(),
        )

    def _extract_citations(self, text: str) -> set[str]:
        """Extract all [SRC0001] style citations from text."""
        return set(re.findall(r'\[SRC\d+\]', text))
