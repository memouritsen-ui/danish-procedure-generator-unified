"""
Writer Agent - Generates procedure content with citations.

Responsible for:
1. Writing structured medical procedure content in Danish
2. Including proper citations to sources
3. Following clinical writing guidelines
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from procedurewriter.agents.base import AgentResult, BaseAgent
from procedurewriter.agents.models import WriterInput, WriterOutput

# Import provider-specific exceptions with fallbacks
try:
    from openai import APIError as OpenAIError
except ImportError:
    OpenAIError = type(None)  # type: ignore[misc,assignment]

try:
    from anthropic import APIError as AnthropicError
except ImportError:
    AnthropicError = type(None)  # type: ignore[misc,assignment]

if TYPE_CHECKING:
    pass


SYSTEM_PROMPT = """Du er en medicinsk fagforfatter og pædagog, der specialiserer dig i at skrive kliniske procedurer på dansk til akutmedicin. Dit mål er at skabe indhold der er klinisk præcist, lærende og konsistent i struktur.

## STRUKTUR (ABSOLUT KRAV - ALLE SEKTIONER SKAL MED)
- DU SKAL SKRIVE ALLE sektioner fra dispositionen - INGEN må springes over!
- Brug SEKTIONERNE præcis i den angivne disposition og i samme rækkefølge.
- Sektionoverskrifter skal matche dispositionen PRÆCIS og ORDRET (## ...) - UDEN nummerering.
- Hvis du ikke har kilder til en sektion, skriv kort generel klinisk vejledning med [S:SRC0001].
- Det er KRITISK at alle 14 sektioner er med - ikke kun Indikationer/Kontraindikationer/Komplikationer.

## PÆDAGOGISK KRAV
Hver sektion skal balancere:
1. **HANDLING** - Hvad skal gøres (konkret instruktion)
2. **RATIONALE** - Hvorfor gøres det (klinisk begrundelse)
3. **EVIDENS** - Kildehenvisning med kontekst

## CITATION-REGLER (STRIKT)
- Brug KUN citations-tags i formatet [S:<source_id>].
- Hver sætning eller bullet skal have mindst én citation.
- Citér med kontekst (ikke bare et tal).

## FORMATERING
- Brug standard Markdown: ## for hovedsektioner, ### for undersektioner
- Brug kun '-' eller nummerering (1., 2., 3.) til lister
- Fremhæv sikkerhedsadvarsler med **ADVARSEL:** prefix

Outputformat: Markdown med danske overskrifter, klinisk terminologi og korrekt citationsformat."""


WRITING_PROMPT = """Skriv en KOMPLET klinisk procedure for:

**Procedure:** {procedure}

{context_section}

**Tilgængelige kilder til citation:**
{sources}

{style_section}

{outline_section}

VIGTIGT: Du SKAL inkludere ALLE sektioner fra dispositionen ovenfor. Spring INGEN sektioner over!
Hver sektion skal have mindst 2-3 bullets med klinisk relevant indhold.
Skriv proceduren på dansk med korrekte citations. Hver faktuel påstand skal citeres med [S:<source_id>]."""


class WriterAgent(BaseAgent[WriterInput, WriterOutput]):
    """Agent that writes medical procedure content with citations."""

    @property
    def name(self) -> str:
        return "Writer"

    def execute(self, input_data: WriterInput) -> AgentResult[WriterOutput]:
        """
        Generate procedure content.

        Args:
            input_data: Contains procedure title, sources, and optional outline

        Returns:
            AgentResult with generated content
        """
        self.reset_stats()

        try:
            # Build prompt sections
            context_section = ""
            if input_data.context:
                context_section = f"**Kontekst:** {input_data.context}"

            sources_text = "\n".join(
                f"- [S:{s.source_id}] {s.title} ({s.year or 'n/a'})"
                for s in input_data.sources[:15]
            )

            style_section = ""
            if input_data.style_guide:
                style_section = f"**Stilguide:** {input_data.style_guide}"

            outline_section = ""
            if input_data.outline:
                outline_section = "**Disposition (brug disse overskrifter i rækkefølge):**\n" + "\n".join(
                    f"- {section}" for section in input_data.outline
                )

            # Generate content
            response = self.llm_call(
                messages=[
                    self._make_system_message(SYSTEM_PROMPT),
                    self._make_user_message(
                        WRITING_PROMPT.format(
                            procedure=input_data.procedure_title,
                            context_section=context_section,
                            sources=sources_text,
                            style_section=style_section,
                            outline_section=outline_section,
                        )
                    ),
                ],
                temperature=0.4,
                max_tokens=16000,  # GPT-5.x may use reasoning tokens
            )

            content = response.content.strip()

            # Extract sections and citations
            sections = self._extract_sections(content)
            citations = self._extract_citations(content)
            word_count = len(content.split())

            output = WriterOutput(
                success=True,
                content_markdown=content,
                sections=sections,
                citations_used=citations,
                word_count=word_count,
            )

        except (OpenAIError, AnthropicError, OSError, KeyError, AttributeError, TypeError) as e:
            # LLM API, network, or response parsing errors - return failure output
            import logging
            logging.getLogger(__name__).error(f"Writer failed: {e}")
            output = WriterOutput(
                success=False,
                error=str(e),
                content_markdown="",
                sections=[],
                citations_used=[],
                word_count=0,
            )

        return AgentResult(output=output, stats=self.get_stats())

    def _extract_sections(self, content: str) -> list[str]:
        """Extract section headings from markdown content."""
        sections = []
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("#"):
                # Remove # marks and get heading text
                heading = re.sub(r"^#+\s*", "", line)
                sections.append(heading)
        return sections

    def _extract_citations(self, content: str) -> list[str]:
        """Extract unique citation IDs from content."""
        # Find all [source_id] patterns
        citations = re.findall(r"\[S:([^\]]+)\]", content)
        # Return unique citations in order of first appearance
        seen = set()
        unique = []
        for cit in citations:
            if cit not in seen:
                seen.add(cit)
                unique.append(cit)
        return unique
