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


SYSTEM_PROMPT = """Du er en senior kvalitetskontrollør for kliniske procedurer med fokus på dansk akutmedicin.

DIN STANDARD ER TINTINALLI'S EMERGENCY MEDICINE og lignende referencetekster.
Procedurer skal være egnet til direkte klinisk brug af læger og sygeplejersker.

Vurder indhold på følgende kriterier (1-10 skala):

1. **Faglig korrekthed** - Er indholdet medicinsk korrekt og opdateret?
   - Korrekte doser, intervaller, og kontraindikationer
   - Evidensbaserede anbefalinger med GRADE-niveau

2. **Klinisk specificitet (TINTINALLI-NIVEAU)** - Er detaljen tilstrækkelig?
   - PRÆCISE doser (mg/kg, max-doser, intervaller)
   - ANATOMISKE landmarks beskrevet
   - ALDERSSPECIFIKKE variationer (pædiatri, geriatri)
   - MONITORERING parametre og intervaller

3. **Citationsdækning** - Er påstande dokumenteret?
   - Hver faktuel påstand har kildereference
   - Kilder er højkvalitet (guidelines > systematic reviews > RCT)

4. **Klarhed og trin-for-trin** - Kan en kliniker følge dette direkte?
   - Nummererede trin i logisk rækkefølge
   - Ingen tvetydigheder eller uklare instruktioner

5. **Fuldstændighed** - Er alle aspekter dækket?
   - Indikationer, kontraindikationer, komplikationer
   - Udstyrsliste, patientpositionering
   - Hvad gør man ved fejl/komplikationer?

6. **Dansk sprogkvalitet** - Er sproget professionelt dansk?
   - Korrekt medicinsk terminologi
   - Præcis og konsistent ordlyd

VIGTIGT: Hvis score < 8, SKAL du give SPECIFIKKE forbedringsforslag med:
- Hvilken SEKTION der skal forbedres
- HVAD der mangler (f.eks. "Mangler pædiatrisk dosis for adrenalin")
- HVORDAN det kan forbedres (f.eks. "Tilføj: Børn: 0.01 mg/kg IM, max 0.5 mg")

Score betydning:
- 9-10: Tintinalli-niveau, klar til publikation
- 8: God kvalitet, mindre justeringer
- 6-7: Mangler klinisk specificitet, revision påkrævet
- 4-5: Under standard, omfattende revision påkrævet
- 1-3: Uacceptabel, skal omskrives"""


QUALITY_PROMPT = """Vurder kvaliteten af følgende kliniske procedure mod TINTINALLI-STANDARD:

**Procedure:**
{content}

**Anvendte kilder ({citation_count} citations):**
{sources}

Evaluer på de 6 kriterier og giv:
1. Score for hvert kriterium (1-10) med SPECIFIKKE noter om mangler
2. Samlet score (1-10)
3. Om indholdet er klar til publikation (score >= 8)
4. OBLIGATORISKE specifikke forbedringsforslag hvis score < 8

KRITISKE SPØRGSMÅL at besvare:
- Er ALLE doser angivet med mg/kg og max-doser?
- Er der PÆDIATRISKE og GERIATRISKE variationer?
- Er ANATOMISKE landmarks beskrevet præcist?
- Er der MONITORERING-parametre og intervaller?
- Er KOMPLIKATIONER og deres håndtering beskrevet?

Output format (JSON):
```json
{{
  "criteria": [
    {{"name": "Faglig korrekthed", "score": 8, "notes": "Korrekte indikationer, men mangler kontraindikationer for graviditet"}},
    {{"name": "Klinisk specificitet (TINTINALLI-NIVEAU)", "score": 6, "notes": "Mangler pædiatriske doser og anatomiske landmarks"}},
    {{"name": "Citationsdækning", "score": 7, "notes": "3 påstande uden kildereference i afsnit Fremgangsmåde"}},
    {{"name": "Klarhed og trin-for-trin", "score": 9, "notes": "God struktur, klare trin"}},
    {{"name": "Fuldstændighed", "score": 7, "notes": "Mangler udstyrsliste og komplikationshåndtering"}},
    {{"name": "Dansk sprogkvalitet", "score": 8, "notes": "Korrekt dansk, enkelte engelske termer kunne oversættes"}}
  ],
  "overall_score": 7,
  "passes_threshold": false,
  "ready_for_publication": false,
  "revision_suggestions": [
    "SEKTION Fremgangsmåde: Tilføj anatomiske landmarks - beskriv præcis placering af indsættelsessted (f.eks. '4.-5. interkostalrum i midaksillarlinjen')",
    "SEKTION Lægemidler: Tilføj pædiatriske doser for lidokain (f.eks. 'Børn: 3-4 mg/kg, max 200 mg')",
    "SEKTION Komplikationer: Tilføj afsnit om håndtering af iatrogen pneumothorax",
    "GENERELT: Tilføj kildereference til påstand om drænplacering i trin 3"
  ]
}}
```

VIGTIGT: Hvis score < 8, SKAL revision_suggestions indeholde mindst 3 SPECIFIKKE forslag
med SEKTION-reference og KONKRET forbedring."""


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
