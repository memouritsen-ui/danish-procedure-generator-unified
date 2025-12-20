"""StyleParserAgent for converting natural language to StyleProfile.

Transforms user's natural language description into a structured StyleProfile
that can be used for document generation.
"""
from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict

from procedurewriter.agents.base import AgentInput, AgentOutput, AgentResult, BaseAgent
from procedurewriter.models.style_profile import StyleProfile


class StyleParserInput(AgentInput):
    """Input for StyleParserAgent."""

    natural_language_prompt: str


class StyleParserOutput(AgentOutput):
    """Output from StyleParserAgent."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    parsed_profile: StyleProfile | None = None


PARSER_SYSTEM_PROMPT = """Du er en ekspert i at konvertere naturlige sprogbeskrivelser til strukturerede stilprofiler for medicinske dokumenter.

Givet en beskrivelse af ønsket stil, skal du returnere et JSON-objekt med følgende felter:

{
  "name": "Kort navn til profilen (max 50 tegn)",
  "tone_description": "Detaljeret beskrivelse af tonen (formel/uformel, aktiv/passiv form, osv.)",
  "target_audience": "Målgruppe (f.eks. 'Medicinstuderende', 'Speciallæger', 'Sygeplejersker')",
  "detail_level": "concise" | "moderate" | "comprehensive",
  "include_clinical_pearls": true | false,
  "include_evidence_badges": true | false,
  "heading_style": "numbered" | "unnumbered",
  "list_style": "bullets" | "numbered" | "prose",
  "citation_style": "superscript" | "inline",
  "color_scheme": "professional_blue" | "neutral_gray" | "clinical_red",
  "safety_box_style": "yellow_background" | "red_border" | "icon_based"
}

RETURNER KUN VALID JSON - ingen forklaringer eller andet tekst."""


class StyleParserAgent(BaseAgent[StyleParserInput, StyleParserOutput]):
    """Agent that parses natural language into StyleProfile."""

    @property
    def name(self) -> str:
        return "StyleParserAgent"

    def execute(self, input_data: StyleParserInput) -> AgentResult[StyleParserOutput]:
        """Parse natural language description to StyleProfile."""
        self.reset_stats()

        user_prompt = f"""Konverter denne stilbeskrivelse til en struktureret profil:

"{input_data.natural_language_prompt}"

Returnér kun JSON-objektet."""

        response = self.llm_call(
            messages=[
                self._make_system_message(PARSER_SYSTEM_PROMPT),
                self._make_user_message(user_prompt),
            ],
            temperature=0.2,
        )

        try:
            # Extract JSON from response (handle code blocks)
            content = response.content.strip()
            if "```json" in content:
                match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
                if match:
                    content = match.group(1)
            elif "```" in content:
                match = re.search(r'```\s*(.*?)\s*```', content, re.DOTALL)
                if match:
                    content = match.group(1)

            data = json.loads(content)

            profile = StyleProfile(
                id="",  # Will be assigned on save
                name=data.get("name", "Ny Stil"),
                description=None,
                is_default=False,
                tone_description=data.get("tone_description", ""),
                target_audience=data.get("target_audience", ""),
                detail_level=data.get("detail_level", "moderate"),
                section_order=data.get("section_order", []),
                include_clinical_pearls=data.get("include_clinical_pearls", False),
                include_evidence_badges=data.get("include_evidence_badges", True),
                heading_style=data.get("heading_style", "numbered"),
                list_style=data.get("list_style", "bullets"),
                citation_style=data.get("citation_style", "superscript"),
                color_scheme=data.get("color_scheme", "professional_blue"),
                safety_box_style=data.get("safety_box_style", "yellow_background"),
                original_prompt=input_data.natural_language_prompt,
            )

            return AgentResult(
                output=StyleParserOutput(
                    success=True,
                    parsed_profile=profile,
                ),
                stats=self.get_stats(),
            )

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            return AgentResult(
                output=StyleParserOutput(
                    success=False,
                    error=f"Kunne ikke parse LLM-svar: {e}",
                ),
                stats=self.get_stats(),
            )
