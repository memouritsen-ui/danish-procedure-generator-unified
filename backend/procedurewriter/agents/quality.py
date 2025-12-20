"""
Quality Agent - Scores content quality and determines if ready for publication.

Responsible for:
1. Scoring content on multiple criteria (1-10 scale)
2. Determining if content passes quality threshold
3. Suggesting specific revisions if needed
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

from procedurewriter.agents.base import AgentResult, BaseAgent
from procedurewriter.agents.models import QualityCriterion, QualityInput, QualityOutput

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class QualityParsingError(Exception):
    """Raised when LLM output cannot be parsed as valid quality JSON.

    This distinguishes formatting errors (retryable) from content issues.
    Callers should retry with the same content, not penalize the score.
    """

    def __init__(self, message: str, raw_response: str, parse_error: Exception | None = None):
        super().__init__(message)
        self.raw_response = raw_response
        self.parse_error = parse_error
        self.is_retryable = True  # Formatting errors are retryable


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

    def execute(
        self,
        input_data: QualityInput,
        *,
        max_parse_retries: int = 2,
    ) -> AgentResult[QualityOutput]:
        """
        Evaluate content quality.

        Args:
            input_data: Contains content to evaluate and sources used
            max_parse_retries: Number of retries for JSON parsing failures

        Returns:
            AgentResult with quality scores and readiness determination

        Note:
            Parsing errors trigger retries (LLM formatting issue).
            Other errors (API, network) are not retried here.
        """
        self.reset_stats()

        # Format sources
        sources_text = "\n".join(
            f"- [{s.source_id}] {s.title}"
            for s in input_data.sources[:10]
        )

        messages = [
            self._make_system_message(SYSTEM_PROMPT),
            self._make_user_message(
                QUALITY_PROMPT.format(
                    content=input_data.content_markdown,
                    sources=sources_text,
                    citation_count=len(input_data.citations_used),
                )
            ),
        ]

        last_parsing_error: QualityParsingError | None = None

        for attempt in range(1, max_parse_retries + 2):  # +2 for initial + retries
            try:
                # Call LLM for quality evaluation
                response = self.llm_call(
                    messages=messages,
                    temperature=0.1,  # Low temperature for consistent scoring
                    max_tokens=1500,
                )

                # Parse response - may raise QualityParsingError
                output = self._parse_response(response.content)
                return AgentResult(output=output, stats=self.get_stats())

            except QualityParsingError as e:
                last_parsing_error = e
                if attempt <= max_parse_retries:
                    logger.warning(
                        "Quality parsing failed (attempt %d/%d), retrying: %s",
                        attempt, max_parse_retries + 1, e
                    )
                    # Add a hint to the conversation for the retry
                    messages.append(self._make_assistant_message(e.raw_response))
                    messages.append(self._make_user_message(
                        "Din respons kunne ikke parses som gyldig JSON. "
                        "Svar venligst KUN med den specificerede JSON-struktur, "
                        "startende med ```json og sluttende med ```."
                    ))
                else:
                    logger.error(
                        "Quality parsing failed after %d attempts: %s",
                        max_parse_retries + 1, e
                    )

            except Exception as e:
                # Non-retryable errors (API, network, etc.)
                logger.exception("Quality evaluation failed: %s", e)
                output = QualityOutput(
                    success=False,
                    error=str(e),
                    overall_score=1,
                    criteria=[],
                    passes_threshold=False,
                    revision_suggestions=["Kvalitetsvurdering fejlede: API/netværk fejl"],
                    ready_for_publication=False,
                )
                return AgentResult(output=output, stats=self.get_stats())

        # All parsing retries exhausted
        output = QualityOutput(
            success=False,
            error=f"Parsing failed after {max_parse_retries + 1} attempts: {last_parsing_error}",
            overall_score=1,
            criteria=[],
            passes_threshold=False,
            revision_suggestions=[
                "LLM returnerede ugyldigt JSON-format gentagne gange. "
                "Dette indikerer et formateringsproblem, ikke indholdsproblem."
            ],
            ready_for_publication=False,
        )
        return AgentResult(output=output, stats=self.get_stats())

    def _make_assistant_message(self, content: str) -> dict[str, str]:
        """Create an assistant message for conversation history."""
        return {"role": "assistant", "content": content}

    def _parse_response(self, content: str) -> QualityOutput:
        """Parse LLM response into QualityOutput.

        Raises:
            QualityParsingError: If the response cannot be parsed as valid JSON.
                This is a retryable error - the LLM produced malformed output.
        """
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
                # No JSON found - this is a formatting error, not a content issue
                logger.warning(
                    "Quality agent returned non-JSON response (first 200 chars): %s",
                    content[:200]
                )
                raise QualityParsingError(
                    message="LLM response did not contain valid JSON structure",
                    raw_response=content,
                    parse_error=None,
                )

        try:
            data = json.loads(json_str)

            # Validate required fields exist
            if "overall_score" not in data:
                raise QualityParsingError(
                    message="JSON missing required field 'overall_score'",
                    raw_response=content,
                    parse_error=None,
                )

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

        except QualityParsingError:
            raise  # Re-raise our custom exception
        except (json.JSONDecodeError, TypeError, KeyError, ValueError) as e:
            logger.warning(
                "Quality JSON parsing failed: %s. Response (first 500 chars): %s",
                e, content[:500]
            )
            raise QualityParsingError(
                message=f"Failed to parse quality JSON: {e}",
                raw_response=content,
                parse_error=e,
            ) from e
