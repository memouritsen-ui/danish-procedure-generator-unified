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

if TYPE_CHECKING:
    pass


SYSTEM_PROMPT = """Du er en medicinsk fagforfatter, der specialiserer dig i at skrive kliniske procedurer på dansk til akutmedicin.

Retningslinjer for skrivning:
1. Skriv klart og præcist på faglig dansk
2. Brug aktiv form og direkte instruktioner
3. Strukturer med overskrifter: Indikationer, Kontraindikationer, Udstyr, Fremgangsmåde, Komplikationer
4. Citér kilder med [kilde_id] notation
5. Hver faktuel påstand skal have en citation
6. Brug punktform til trin-for-trin instruktioner
7. Inkludér advarsler og sikkerhedsforanstaltninger

Outputformat: Markdown med danske overskrifter og [source_id] citations."""


WRITING_PROMPT = """Skriv en komplet klinisk procedure for:

**Procedure:** {procedure}

{context_section}

**Tilgængelige kilder til citation:**
{sources}

{style_section}

{outline_section}

Skriv proceduren på dansk med korrekte citations. Hver faktuel påstand skal citeres med [source_id]."""


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
                f"- [{s.source_id}] {s.title} ({s.year or 'n/a'})"
                for s in input_data.sources[:15]  # Limit sources
            )

            style_section = ""
            if input_data.style_guide:
                style_section = f"**Stilguide:** {input_data.style_guide}"

            outline_section = ""
            if input_data.outline:
                outline_section = "**Foreslået disposition:**\n" + "\n".join(
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
                max_tokens=4000,
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

        except Exception as e:
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
        citations = re.findall(r"\[([a-zA-Z0-9_-]+)\]", content)
        # Return unique citations in order of first appearance
        seen = set()
        unique = []
        for cit in citations:
            if cit not in seen:
                seen.add(cit)
                unique.append(cit)
        return unique
