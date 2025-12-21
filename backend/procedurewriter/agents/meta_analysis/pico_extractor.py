"""PICO extractor agent with cross-lingual support.

Extracts Population, Intervention, Comparison, Outcome from study
text with Danish → English MeSH normalization and confidence gating.
"""
from __future__ import annotations

import json
import logging

from pydantic import BaseModel, Field, model_validator

from procedurewriter.agents.base import AgentResult, BaseAgent
from procedurewriter.agents.meta_analysis.models import ManualReviewRequired, PICOData
from procedurewriter.llm.providers import LLMProvider

logger = logging.getLogger(__name__)


class PICOExtractionInput(BaseModel):
    """Input for PICO extraction.

    Requires study_id and at least one of title or abstract.
    """
    study_id: str = Field(..., min_length=1)
    title: str | None = None
    abstract: str | None = None
    methods: str | None = None

    @model_validator(mode="after")
    def require_content(self) -> PICOExtractionInput:
        """Require at least title or abstract."""
        if not self.title and not self.abstract:
            raise ValueError("At least one of 'title' or 'abstract' must be provided")
        return self


class PICOExtractor(BaseAgent[PICOExtractionInput, PICOData]):
    """Agent for extracting PICO elements from study text.

    Features:
    - Cross-lingual support (Danish → English MeSH normalization)
    - Confidence scoring with threshold gating
    - Optional self-correction pass for low-confidence extractions

    Raises ManualReviewRequired if confidence is below threshold after
    all extraction attempts.
    """

    def __init__(
        self,
        llm: LLMProvider,
        model: str | None = None,
        confidence_threshold: float = 0.50,  # Lowered from 0.85 - be more inclusive
        enable_self_correction: bool = True,  # Enable by default to improve extraction
        raise_on_low_confidence: bool = False,  # Don't throw exceptions by default
    ) -> None:
        """Initialize PICO extractor.

        Args:
            llm: LLM provider for extraction.
            model: Model name override.
            confidence_threshold: Minimum confidence for automatic acceptance (0-1).
                                 Lowered to 0.50 to be more inclusive of partial matches.
            enable_self_correction: Enable second-pass self-correction for
                                   low-confidence extractions. Default True.
            raise_on_low_confidence: If True, raise ManualReviewRequired exception
                                    for low confidence. If False (default), return
                                    the low-confidence data for downstream handling.
        """
        super().__init__(llm, model)
        self._confidence_threshold = confidence_threshold
        self._enable_self_correction = enable_self_correction
        self._raise_on_low_confidence = raise_on_low_confidence

    @property
    def name(self) -> str:
        return "pico_extractor"

    def execute(self, input_data: PICOExtractionInput) -> AgentResult[PICOData]:
        """Extract PICO elements from study input.

        Args:
            input_data: Study text (title, abstract, methods).

        Returns:
            AgentResult containing PICOData if confidence >= threshold.

        Raises:
            ManualReviewRequired: If confidence < threshold after all attempts.
        """
        # First extraction pass
        pico_data = self._extract_pico(input_data)

        # Check if self-correction needed and enabled
        if (
            pico_data.confidence < self._confidence_threshold
            and self._enable_self_correction
        ):
            logger.info(
                f"Low confidence ({pico_data.confidence:.2f}) for {input_data.study_id}, "
                "attempting self-correction"
            )
            pico_data = self._self_correct(input_data, pico_data)

        # Final confidence check - only raise if explicitly configured
        if pico_data.confidence < self._confidence_threshold:
            if self._raise_on_low_confidence:
                raise ManualReviewRequired(
                    confidence=pico_data.confidence,
                    reason=f"PICO extraction confidence {pico_data.confidence:.2f} below threshold {self._confidence_threshold}",
                    study_id=input_data.study_id,
                )
            else:
                # Log warning but return data for downstream handling
                logger.warning(
                    f"Low PICO confidence ({pico_data.confidence:.2f}) for {input_data.study_id}, "
                    "returning data for downstream filtering"
                )

        return AgentResult(
            output=pico_data,
            stats=self._stats,
        )

    def _extract_pico(self, input_data: PICOExtractionInput) -> PICOData:
        """Perform PICO extraction via LLM."""
        prompt = self._build_extraction_prompt(input_data)
        messages = [
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "user", "content": prompt},
        ]

        response = self.llm_call(messages, temperature=0.1)
        return self._parse_response(response.content)

    def _self_correct(
        self, input_data: PICOExtractionInput, initial_result: PICOData
    ) -> PICOData:
        """Attempt self-correction to improve extraction confidence."""
        prompt = self._build_correction_prompt(input_data, initial_result)
        messages = [
            {"role": "system", "content": self._get_correction_system_prompt()},
            {"role": "user", "content": prompt},
        ]

        response = self.llm_call(messages, temperature=0.1)
        return self._parse_response(response.content)

    def _get_system_prompt(self) -> str:
        """System prompt for PICO extraction."""
        return """You are an expert medical literature analyst specializing in systematic reviews.

Your task is to extract PICO (Population, Intervention, Comparison, Outcome) elements
from clinical study text with high precision.

CRITICAL REQUIREMENTS:
1. Extract PICO elements in the ORIGINAL LANGUAGE of the study text
2. Normalize all extracted terms to English MeSH (Medical Subject Headings) vocabulary
3. Provide a confidence score (0.0-1.0) reflecting extraction certainty
4. Handle both English and Danish medical literature

For Danish text:
- Keep original Danish terms in population/intervention/comparison/outcome fields
- Provide English MeSH equivalents in the *_mesh fields

OUTPUT FORMAT (JSON):
{
    "population": "Target population description (original language)",
    "intervention": "Intervention description (original language)",
    "comparison": "Comparator description or null if single-arm (original language)",
    "outcome": "Primary outcome description (original language)",
    "confidence": 0.0-1.0,
    "population_mesh": ["MeSH term 1", "MeSH term 2"],
    "intervention_mesh": ["MeSH term 1"],
    "outcome_mesh": ["MeSH term 1"],
    "detected_language": "en" or "da"
}

Respond ONLY with valid JSON. No explanatory text."""

    def _get_correction_system_prompt(self) -> str:
        """System prompt for self-correction pass."""
        return """You are an expert medical literature analyst reviewing a PICO extraction.

The initial extraction had low confidence. Your task is to:
1. Re-analyze the study text more carefully
2. Identify any ambiguities or errors in the initial extraction
3. Provide an improved extraction with higher precision

Focus on:
- Specific population characteristics (age, condition, severity)
- Precise intervention details (drug, dose, duration)
- Clear outcome definitions (measurement, timeframe)
- Accurate MeSH term mappings

OUTPUT FORMAT (JSON):
{
    "population": "Improved population description",
    "intervention": "Improved intervention description",
    "comparison": "Improved comparator or null",
    "outcome": "Improved outcome description",
    "confidence": 0.0-1.0,
    "population_mesh": ["MeSH terms"],
    "intervention_mesh": ["MeSH terms"],
    "outcome_mesh": ["MeSH terms"],
    "detected_language": "en" or "da"
}

Respond ONLY with valid JSON. No explanatory text."""

    def _build_extraction_prompt(self, input_data: PICOExtractionInput) -> str:
        """Build extraction prompt from input data."""
        parts = [f"Study ID: {input_data.study_id}"]

        if input_data.title:
            parts.append(f"Title: {input_data.title}")

        if input_data.abstract:
            parts.append(f"Abstract: {input_data.abstract}")

        if input_data.methods:
            parts.append(f"Methods: {input_data.methods}")

        return "\n\n".join(parts)

    def _build_correction_prompt(
        self, input_data: PICOExtractionInput, initial_result: PICOData
    ) -> str:
        """Build self-correction prompt."""
        initial_json = json.dumps(
            {
                "population": initial_result.population,
                "intervention": initial_result.intervention,
                "comparison": initial_result.comparison,
                "outcome": initial_result.outcome,
                "confidence": initial_result.confidence,
            },
            indent=2,
        )

        return f"""Original study text:

{self._build_extraction_prompt(input_data)}

Initial extraction (confidence: {initial_result.confidence:.2f}):
{initial_json}

Please provide an improved extraction with higher confidence and precision.
Focus on extracting more specific details from the text."""

    def _parse_response(self, content: str) -> PICOData:
        """Parse LLM response into PICOData."""
        try:
            # Handle markdown code blocks if present
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            data = json.loads(content)

            return PICOData(
                population=data["population"],
                intervention=data["intervention"],
                comparison=data.get("comparison"),
                outcome=data["outcome"],
                confidence=data["confidence"],
                population_mesh=data.get("population_mesh", []),
                intervention_mesh=data.get("intervention_mesh", []),
                outcome_mesh=data.get("outcome_mesh", []),
            )

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse PICO extraction response: {e}")
            # Return low-confidence result to trigger manual review
            return PICOData(
                population="[EXTRACTION FAILED]",
                intervention="[EXTRACTION FAILED]",
                comparison=None,
                outcome="[EXTRACTION FAILED]",
                confidence=0.0,
                population_mesh=[],
                intervention_mesh=[],
                outcome_mesh=[],
            )
