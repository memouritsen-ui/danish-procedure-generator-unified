"""Stage 06: ClaimExtract - Extract verifiable claims from procedure drafts.

The ClaimExtract stage parses claims from markdown content:
1. Receives draft markdown from Stage 05 (Draft)
2. Uses LLM to extract verifiable claims
3. Creates Claim objects with types (dose, threshold, etc.)
4. Outputs claims for Bind stage
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from procedurewriter.models.claims import Claim, ClaimType
from procedurewriter.pipeline.events import EventType
from procedurewriter.pipeline.stages.base import PipelineStage

if TYPE_CHECKING:
    from procedurewriter.llm.providers import LLMProvider
    from procedurewriter.pipeline.events import EventEmitter

logger = logging.getLogger(__name__)

# Default model for claim extraction
DEFAULT_MODEL = "gpt-4o-mini"

# System prompt for claim extraction
SYSTEM_PROMPT = """You are a medical claim extraction specialist. Your task is to identify and extract verifiable medical claims from clinical procedure text.

Extract claims of the following types:
- DOSE: Drug dosages (e.g., "amoxicillin 50 mg/kg/d")
- THRESHOLD: Clinical thresholds (e.g., "CURB-65 >= 3", "SpO2 < 92%")
- RECOMMENDATION: Clinical recommendations (e.g., "should be admitted")
- CONTRAINDICATION: When NOT to do something (e.g., "avoid in penicillin allergy")
- RED_FLAG: Warning signs requiring action
- ALGORITHM_STEP: Numbered procedure steps

For each claim, provide:
1. claim_type: One of the types above (lowercase)
2. text: The exact claim text from the document
3. normalized_value: Standardized numeric value if applicable
4. unit: Unit of measurement if applicable
5. line_number: Approximate line number (1-based)
6. confidence: Extraction confidence (0.0-1.0)
7. source_refs: List of source IDs mentioned (e.g., ["SRC001"])

Return a JSON array of claim objects. If no claims found, return empty array [].
Only extract verifiable, specific claims - not general statements."""


@dataclass
class ClaimExtractInput:
    """Input for the ClaimExtract stage."""

    run_id: str
    run_dir: Path
    procedure_title: str
    content_markdown: str
    model: str = DEFAULT_MODEL
    emitter: "EventEmitter | None" = None


@dataclass
class ClaimExtractOutput:
    """Output from the ClaimExtract stage."""

    run_id: str
    run_dir: Path
    procedure_title: str
    claims: list[Claim]
    total_claims: int
    content_markdown: str = ""  # Pass through for later stages


class ClaimExtractStage(PipelineStage[ClaimExtractInput, ClaimExtractOutput]):
    """Stage 06: ClaimExtract - Extract verifiable claims from procedure drafts."""

    def __init__(self, llm_client: "LLMProvider | None" = None) -> None:
        """Initialize the ClaimExtract stage.

        Args:
            llm_client: Optional LLM client to use. If not provided,
                        will be created on first use.
        """
        self._llm_client = llm_client

    @property
    def name(self) -> str:
        """Return the stage name."""
        return "claimextract"

    def _get_llm_client(self) -> "LLMProvider":
        """Get or create the LLM client."""
        if self._llm_client is None:
            from procedurewriter.llm import get_llm_client

            self._llm_client = get_llm_client()
        return self._llm_client

    def execute(self, input_data: ClaimExtractInput) -> ClaimExtractOutput:
        """Execute the claim extraction stage.

        Parses procedure markdown to extract verifiable claims.

        Args:
            input_data: ClaimExtract input containing markdown content

        Returns:
            ClaimExtract output with list of Claim objects
        """
        # Emit progress event if emitter provided
        if input_data.emitter is not None:
            input_data.emitter.emit(
                EventType.PROGRESS,
                {
                    "message": f"Extracting claims from {input_data.procedure_title}",
                    "stage": "claimextract",
                },
            )

        # Handle empty content
        if not input_data.content_markdown.strip():
            logger.info("Empty content, no claims to extract")
            return ClaimExtractOutput(
                run_id=input_data.run_id,
                run_dir=input_data.run_dir,
                procedure_title=input_data.procedure_title,
                claims=[],
                total_claims=0,
                content_markdown=input_data.content_markdown,
            )

        try:
            # Call LLM to extract claims
            raw_claims = self._extract_claims_with_llm(
                content=input_data.content_markdown,
                procedure_title=input_data.procedure_title,
                model=input_data.model,
            )

            # Convert raw claims to Claim objects
            claims = self._build_claim_objects(
                raw_claims=raw_claims,
                run_id=input_data.run_id,
            )

            logger.info(f"Extracted {len(claims)} claims from procedure")

            return ClaimExtractOutput(
                run_id=input_data.run_id,
                run_dir=input_data.run_dir,
                procedure_title=input_data.procedure_title,
                claims=claims,
                total_claims=len(claims),
                content_markdown=input_data.content_markdown,
            )

        except Exception as e:
            logger.error(f"Claim extraction failed: {e}")
            return ClaimExtractOutput(
                run_id=input_data.run_id,
                run_dir=input_data.run_dir,
                procedure_title=input_data.procedure_title,
                claims=[],
                total_claims=0,
                content_markdown=input_data.content_markdown,
            )

    def _extract_claims_with_llm(
        self,
        content: str,
        procedure_title: str,
        model: str,
    ) -> list[dict[str, Any]]:
        """Use LLM to extract claims from content.

        Args:
            content: Markdown content to parse
            procedure_title: Title for context
            model: LLM model to use

        Returns:
            List of raw claim dictionaries from LLM
        """
        llm = self._get_llm_client()

        user_prompt = f"""Procedure: {procedure_title}

Content to analyze:
{content}

Extract all verifiable medical claims from this procedure. Return as JSON array."""

        response = llm.chat_completion(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            model=model,
            temperature=0.2,  # Low temperature for consistent extraction
            max_tokens=4000,
        )

        # Parse JSON response
        try:
            # Try to extract JSON from response
            content_text = response.content.strip()

            # Handle markdown code blocks
            if "```json" in content_text:
                content_text = content_text.split("```json")[1].split("```")[0]
            elif "```" in content_text:
                content_text = content_text.split("```")[1].split("```")[0]

            claims_data = json.loads(content_text)

            if not isinstance(claims_data, list):
                logger.warning("LLM returned non-list response")
                return []

            return claims_data

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")
            return []

    def _build_claim_objects(
        self,
        raw_claims: list[dict[str, Any]],
        run_id: str,
    ) -> list[Claim]:
        """Convert raw claim dictionaries to Claim objects.

        Args:
            raw_claims: List of claim dictionaries from LLM
            run_id: Pipeline run ID

        Returns:
            List of Claim objects
        """
        claims: list[Claim] = []

        for raw in raw_claims:
            try:
                # Parse claim type
                claim_type_str = raw.get("claim_type", "").lower()
                try:
                    claim_type = ClaimType(claim_type_str)
                except ValueError:
                    logger.warning(f"Unknown claim type: {claim_type_str}")
                    claim_type = ClaimType.RECOMMENDATION  # Default

                # Build Claim object
                claim = Claim(
                    run_id=run_id,
                    claim_type=claim_type,
                    text=raw.get("text", ""),
                    normalized_value=raw.get("normalized_value"),
                    unit=raw.get("unit"),
                    source_refs=raw.get("source_refs", []),
                    line_number=raw.get("line_number", 1),
                    confidence=raw.get("confidence", 0.5),
                )
                claims.append(claim)

            except Exception as e:
                logger.warning(f"Failed to build claim object: {e}")

        return claims
