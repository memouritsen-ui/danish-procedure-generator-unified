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
- Procedure-sektionen må KUN bruge fuldtekst-kilder; hvis ingen fuldtekst findes, indsæt [TECHNICAL_DETAIL_UNVERIFIED_NO_FULLTEXT].
- Tilføj en "Evidence Grade Table" i hver sektion, der mapper anbefalinger til kildekvalitet.

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
                f"- [S:{s.source_id}] {s.title} ({s.year or 'n/a'}) [{_fulltext_label(s)}]"
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
            content = self._postprocess_content(
                content,
                input_data.sources,
                input_data.evidence_flags or [],
            )

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

    def _postprocess_content(self, content: str, sources: list, evidence_flags: list[str]) -> str:
        source_ids = [s.source_id for s in sources if getattr(s, "source_id", None)]
        full_text_ids = {
            s.source_id for s in sources
            if getattr(s, "full_text_available", None)
        }
        fallback_source_id = source_ids[0] if source_ids else "UNAVAILABLE"
        fallback_full_text_id = next(iter(full_text_ids), fallback_source_id)
        evidence_map = _build_evidence_grade_map(sources)

        prelude, sections = _split_sections(content)
        if evidence_flags:
            for flag in evidence_flags:
                if flag and flag not in prelude:
                    prelude.append(flag)
        output_lines: list[str] = []
        output_lines.extend(prelude)

        for heading, body_lines in sections:
            is_procedure = heading.strip().lower() == "procedure"
            has_table = _has_evidence_table(body_lines)
            step_rows: list[tuple[str, list[str]]] = []
            new_body: list[str] = []

            if is_procedure and not full_text_ids:
                if not any("[TECHNICAL_DETAIL_UNVERIFIED_NO_FULLTEXT]" in line for line in body_lines):
                    new_body.append("[TECHNICAL_DETAIL_UNVERIFIED_NO_FULLTEXT]")

            for line in body_lines:
                if not _is_step_line(line):
                    new_body.append(line)
                    continue

                citations = _extract_citation_ids(line)
                line_base = _strip_citations(line).rstrip()

                if is_procedure and full_text_ids:
                    filtered = [c for c in citations if c in full_text_ids]
                    if not filtered:
                        filtered = [fallback_full_text_id]
                    new_line = line_base + _format_citations(filtered)
                    citations = filtered
                else:
                    if not citations:
                        citations = [fallback_source_id]
                        new_line = line_base + _format_citations(citations)
                    else:
                        new_line = line

                step_rows.append((_strip_step_prefix(line_base), citations))
                new_body.append(new_line)

            output_lines.append(f"## {heading}".rstrip())
            output_lines.extend(new_body)

            if not has_table:
                table_lines = _build_evidence_grade_table(step_rows, evidence_map)
                output_lines.append("")
                output_lines.extend(table_lines)

        return "\n".join(output_lines).strip()


def _split_sections(content: str) -> tuple[list[str], list[tuple[str, list[str]]]]:
    lines = content.splitlines()
    prelude: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    current_heading: str | None = None
    current_body: list[str] = []

    for line in lines:
        if line.startswith("## "):
            if current_heading is not None:
                sections.append((current_heading, current_body))
            else:
                if current_body:
                    prelude.extend(current_body)
            current_heading = line[3:].strip()
            current_body = []
        else:
            if current_heading is None:
                prelude.append(line)
            else:
                current_body.append(line)

    if current_heading is not None:
        sections.append((current_heading, current_body))
    return prelude, sections


def _is_step_line(line: str) -> bool:
    stripped = line.lstrip()
    if stripped.startswith(("-", "*", "•")):
        return True
    return bool(re.match(r"^\d+[.)]\s+", stripped))


def _extract_citation_ids(line: str) -> list[str]:
    return re.findall(r"\[S:([^\]]+)\]", line)


def _strip_citations(line: str) -> str:
    return re.sub(r"\s*\[S:[^\]]+\]", "", line)


def _format_citations(citations: list[str]) -> str:
    return "".join(f" [S:{c}]" for c in citations if c)


def _strip_step_prefix(line: str) -> str:
    stripped = line.lstrip()
    if stripped.startswith(("-", "*", "•")):
        return stripped[1:].strip()
    return re.sub(r"^\d+[.)]\s+", "", stripped).strip()


def _has_evidence_table(lines: list[str]) -> bool:
    return any("Evidence Grade Table" in line for line in lines)


def _build_evidence_grade_map(sources: list) -> dict[str, tuple[float, str]]:
    mapping: dict[str, tuple[float, str]] = {}
    for src in sources:
        source_id = getattr(src, "source_id", None)
        if not source_id:
            continue
        tier = (getattr(src, "evidence_tier", None) or getattr(src, "source_type", None) or "").lower()
        label, weight = _evidence_label_and_weight(tier)
        mapping[source_id] = (weight, f"{label} ({weight:.1f})")
    return mapping


def _evidence_label_and_weight(tier: str) -> tuple[str, float]:
    tiers = {
        "systematic_review": ("Cochrane/Meta-Analysis", 1.0),
        "meta_analysis": ("Cochrane/Meta-Analysis", 1.0),
        "cochrane_review": ("Cochrane/Meta-Analysis", 1.0),
        "rct": ("PubMed RCT", 0.9),
        "international_guideline": ("International Guideline", 0.7),
        "danish_guideline": ("Danish National Guideline", 0.4),
        "local_protocol": ("Local Protocol", 0.2),
    }
    return tiers.get(tier, ("Unclassified", 0.3))


def _build_evidence_grade_table(
    step_rows: list[tuple[str, list[str]]],
    evidence_map: dict[str, tuple[float, str]],
) -> list[str]:
    lines = ["### Evidence Grade Table", "| Recommendation | Evidence Grade | Sources |", "| --- | --- | --- |"]
    if not step_rows:
        lines.append("| No technical steps identified | Unclassified (0.3) | - |")
        return lines

    for recommendation, citations in step_rows:
        best_weight = 0.0
        best_label = "Unclassified (0.3)"
        for cit in citations:
            weight, label = evidence_map.get(cit, (0.3, "Unclassified (0.3)"))
            if weight > best_weight:
                best_weight = weight
                best_label = label
        sources_cell = ", ".join(f"S:{c}" for c in citations) if citations else "-"
        rec = recommendation or "Recommendation"
        lines.append(f"| {rec} | {best_label} | {sources_cell} |")

    return lines


def _fulltext_label(source: object) -> str:
    full_text = getattr(source, "full_text_available", None)
    if full_text is True:
        return "FULLTEXT"
    if full_text is False:
        return "ABSTRACT ONLY"
    return "FULLTEXT UNKNOWN"
