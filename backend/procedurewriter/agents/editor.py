"""
Editor Agent - Reviews and improves procedure content.

Responsible for:
1. Improving prose quality and clarity
2. Ensuring proper Danish medical terminology
3. Checking citation coverage
4. Suggesting improvements
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from procedurewriter.agents.base import AgentResult, BaseAgent
from procedurewriter.agents.models import EditorInput, EditorOutput, EditSuggestion

if TYPE_CHECKING:
    pass


SYSTEM_PROMPT = """Du er en medicinsk redaktør med speciale i dansk fagsprog og kliniske procedurer.

Din opgave er at:
1. Forbedre tekstens klarhed og præcision
2. Sikre korrekt dansk medicinsk terminologi
3. Kontrollere at alle påstande er citeret
4. Rette grammatiske og stavefejl
5. Forbedre flow og læsbarhed

Vær opmærksom på:
- Brug af aktiv form frem for passiv
- Konsistent terminologi gennem hele teksten
- Korrekt fagsprog (undgå anglicismer)
- Tydelige trin-for-trin instruktioner"""


EDITING_PROMPT = """Rediger følgende kliniske procedure:

**Procedure:**
{content}

**Tilgængelige kilder (til reference):**
{sources}

{style_section}

Opgaver:
1. Forbedr tekstens klarhed og læsbarhed
2. Ret sproglige fejl (dansk)
3. Sikr konsistent terminologi
4. Behold alle citations [S:<source_id>]
5. Foreslå konkrete ændringer

Output format:
1. Først den redigerede tekst (komplet)
2. Derefter en JSON-sektion med forslag:
```json
{{
  "suggestions": [
    {{"original": "...", "suggested": "...", "reason": "...", "severity": "minor|moderate|critical"}}
  ],
  "danish_notes": "Noter om dansk sprogkvalitet"
}}
```"""


class EditorAgent(BaseAgent[EditorInput, EditorOutput]):
    """Agent that edits and improves procedure content."""

    @property
    def name(self) -> str:
        return "Editor"

    def execute(self, input_data: EditorInput) -> AgentResult[EditorOutput]:
        """
        Edit and improve procedure content.

        Args:
            input_data: Contains content to edit and available sources

        Returns:
            AgentResult with edited content and suggestions
        """
        self.reset_stats()

        try:
            # Format sources
            sources_text = "\n".join(
                f"- [{s.source_id}] {s.title}"
                for s in input_data.sources[:10]
            )

            style_section = ""
            if input_data.style_guide:
                style_section = f"**Stilguide:** {input_data.style_guide}"

            # Call LLM for editing
            response = self.llm_call(
                messages=[
                    self._make_system_message(SYSTEM_PROMPT),
                    self._make_user_message(
                        EDITING_PROMPT.format(
                            content=input_data.content_markdown,
                            sources=sources_text,
                            style_section=style_section,
                        )
                    ),
                ],
                temperature=0.3,
                max_tokens=8000,
            )

            # Parse response
            edited_content, suggestions, danish_notes = self._parse_response(
                response.content, input_data.content_markdown
            )

            output = EditorOutput(
                success=True,
                edited_content=edited_content,
                suggestions_applied=suggestions,
                danish_quality_notes=danish_notes,
            )

        except Exception as e:
            output = EditorOutput(
                success=False,
                error=str(e),
                edited_content=input_data.content_markdown,  # Return original on error
                suggestions_applied=[],
                danish_quality_notes=None,
            )

        return AgentResult(output=output, stats=self.get_stats())

    def _parse_response(
        self, content: str, original: str
    ) -> tuple[str, list[EditSuggestion], str | None]:
        """
        Parse the LLM response into edited content and suggestions.

        Returns:
            Tuple of (edited_content, suggestions, danish_notes)
        """
        suggestions: list[EditSuggestion] = []
        danish_notes: str | None = None

        # Try to find JSON section
        json_match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)

        if json_match:
            # Extract content before JSON
            edited_content = content[: json_match.start()].strip()

            # Parse JSON
            try:
                data = json.loads(json_match.group(1))

                # Parse suggestions
                for s in data.get("suggestions", []):
                    suggestions.append(
                        EditSuggestion(
                            original_text=s.get("original", ""),
                            suggested_text=s.get("suggested", ""),
                            reason=s.get("reason", ""),
                            severity=s.get("severity", "minor"),
                        )
                    )

                danish_notes = data.get("danish_notes")

            except (json.JSONDecodeError, TypeError, KeyError):
                pass

        else:
            # No JSON found - use entire response as edited content
            edited_content = content.strip()

        # If edited content is empty or too short, fall back to original
        if len(edited_content) < len(original) * 0.5:
            edited_content = original

        return edited_content, suggestions, danish_notes
