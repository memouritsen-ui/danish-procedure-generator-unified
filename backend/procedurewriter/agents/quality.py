"""
Quality Agent - Scores content quality and determines if ready for publication.

Responsible for:
1. Scoring content on multiple criteria (1-10 scale)
2. Determining if content passes quality threshold
3. Suggesting specific revisions if needed
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from procedurewriter.agents.base import AgentResult, BaseAgent
from procedurewriter.agents.models import QualityCriterion, QualityInput, QualityOutput

if TYPE_CHECKING:
    from procedurewriter.llm.providers import LLMProvider


SYSTEM_PROMPT = """Du er en kvalitetskontrollør for kliniske procedurer med fokus på dansk akutmedicin.

Vurder indhold på følgende kriterier (1-10 skala):

1. **Faglig korrekthed** - Er indholdet medicinsk korrekt?
2. **Citationsdækning** - Er alle påstande korrekt citeret?
3. **Klarhed** - Er instruktionerne klare og utvetydige?
4. **Fuldstændighed** - Dækker proceduren alle nødvendige aspekter?
5. **Dansk sprogkvalitet** - Er sproget korrekt og fagligt dansk?
6. **Praktisk anvendelighed** - Kan en kliniker bruge dette direkte?

Samlet score beregnes som gennemsnit, rundet op/ned.

Score betydning:
- 9-10: Fremragende, klar til publikation
- 8: God kvalitet, mindre justeringer mulige
- 6-7: Acceptabel, men forbedringer anbefales
- 4-5: Under standard, revision påkrævet
- 1-3: Uacceptabel, skal omskrives"""


QUALITY_PROMPT = """Vurder kvaliteten af følgende kliniske procedure:

**Procedure:**
{content}

**Anvendte kilder ({citation_count} citations):**
{sources}

Evaluer på de 6 kriterier og giv:
1. Score for hvert kriterium (1-10) med korte noter
2. Samlet score (1-10)
3. Om indholdet er klar til publikation (score >= 8)
4. Specifikke forbedringsforslag hvis score < 8

Output format (JSON):
```json
{{
  "criteria": [
    {{"name": "Faglig korrekthed", "score": 8, "notes": "..."}},
    {{"name": "Citationsdækning", "score": 7, "notes": "..."}},
    {{"name": "Klarhed", "score": 9, "notes": "..."}},
    {{"name": "Fuldstændighed", "score": 8, "notes": "..."}},
    {{"name": "Dansk sprogkvalitet", "score": 8, "notes": "..."}},
    {{"name": "Praktisk anvendelighed", "score": 8, "notes": "..."}}
  ],
  "overall_score": 8,
  "passes_threshold": true,
  "ready_for_publication": true,
  "revision_suggestions": []
}}
```"""


class QualityAgent(BaseAgent[QualityInput, QualityOutput]):
    """Agent that evaluates content quality and readiness for publication."""

    @property
    def name(self) -> str:
        return "Quality"

    def execute(self, input_data: QualityInput) -> AgentResult[QualityOutput]:
        """
        Evaluate content quality.

        Args:
            input_data: Contains content to evaluate and sources used

        Returns:
            AgentResult with quality scores and readiness determination
        """
        self.reset_stats()

        try:
            # Format sources
            sources_text = "\n".join(
                f"- [{s.source_id}] {s.title}"
                for s in input_data.sources[:10]
            )

            # Call LLM for quality evaluation
            response = self.llm_call(
                messages=[
                    self._make_system_message(SYSTEM_PROMPT),
                    self._make_user_message(
                        QUALITY_PROMPT.format(
                            content=input_data.content_markdown,
                            sources=sources_text,
                            citation_count=len(input_data.citations_used),
                        )
                    ),
                ],
                temperature=0.1,  # Low temperature for consistent scoring
                max_tokens=1500,
            )

            # Parse response
            output = self._parse_response(response.content)

        except Exception as e:
            output = QualityOutput(
                success=False,
                error=str(e),
                overall_score=1,
                criteria=[],
                passes_threshold=False,
                revision_suggestions=["Kvalitetsvurdering fejlede"],
                ready_for_publication=False,
            )

        return AgentResult(output=output, stats=self.get_stats())

    def _parse_response(self, content: str) -> QualityOutput:
        """Parse LLM response into QualityOutput."""
        # Extract JSON from response
        json_match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)

        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find raw JSON
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                json_str = json_match.group()
            else:
                # Fallback: low score indicating parsing failure
                return QualityOutput(
                    success=True,
                    overall_score=5,
                    criteria=[],
                    passes_threshold=False,
                    revision_suggestions=["Kunne ikke parse kvalitetsvurdering"],
                    ready_for_publication=False,
                )

        try:
            data = json.loads(json_str)

            # Parse criteria
            criteria = []
            for c in data.get("criteria", []):
                criteria.append(
                    QualityCriterion(
                        name=c.get("name", ""),
                        score=int(c.get("score", 5)),
                        notes=c.get("notes"),
                    )
                )

            overall = int(data.get("overall_score", 5))
            passes = overall >= 8

            return QualityOutput(
                success=True,
                overall_score=overall,
                criteria=criteria,
                passes_threshold=passes,
                revision_suggestions=data.get("revision_suggestions", []),
                ready_for_publication=data.get("ready_for_publication", passes),
            )

        except (json.JSONDecodeError, TypeError, KeyError, ValueError) as e:
            return QualityOutput(
                success=True,
                overall_score=5,
                criteria=[],
                passes_threshold=False,
                revision_suggestions=[f"Parsing fejl: {str(e)}"],
                ready_for_publication=False,
            )
