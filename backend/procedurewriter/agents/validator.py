"""
Validator Agent - Validates claims against sources.

Responsible for:
1. Checking if claims are supported by available sources
2. Identifying unsupported statements
3. Providing confidence scores for each validation
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from procedurewriter.agents.base import AgentResult, BaseAgent
from procedurewriter.agents.models import ClaimValidation, ValidatorInput, ValidatorOutput

if TYPE_CHECKING:
    from procedurewriter.llm.providers import LLMProvider


SYSTEM_PROMPT = """You are a medical fact-checker specializing in validating clinical claims against source literature.

Your task is to evaluate whether claims are supported by the provided sources.

Guidelines:
1. A claim is SUPPORTED if at least one source directly or strongly implies it
2. A claim is UNSUPPORTED if no source provides evidence for it
3. Assign confidence based on:
   - 0.9-1.0: Directly stated in source
   - 0.7-0.8: Strongly implied by source
   - 0.5-0.6: Somewhat supported, may need additional citation
   - 0.3-0.4: Weakly related
   - 0.0-0.2: No support found

Be conservative - medical claims require strong evidence."""


VALIDATION_PROMPT = """Evaluate the following claims against the available sources.

Sources available:
{sources}

Claims to validate:
{claims}

For each claim, determine:
1. is_supported: true/false
2. supporting_source_ids: list of source IDs that support it
3. confidence: 0.0 to 1.0
4. notes: brief explanation

Output format: JSON array of validation objects.
Example:
[
  {{
    "claim": "Epinephrine is first-line treatment for anaphylaxis",
    "is_supported": true,
    "supporting_source_ids": ["src_001", "src_003"],
    "confidence": 0.95,
    "notes": "Directly stated in guidelines"
  }}
]"""


class ValidatorAgent(BaseAgent[ValidatorInput, ValidatorOutput]):
    """Agent that validates claims against available sources."""

    @property
    def name(self) -> str:
        return "Validator"

    def execute(self, input_data: ValidatorInput) -> AgentResult[ValidatorOutput]:
        """
        Validate claims against sources.

        Args:
            input_data: Contains claims to validate and available sources

        Returns:
            AgentResult with validation results
        """
        self.reset_stats()

        try:
            if not input_data.claims:
                output = ValidatorOutput(
                    success=True,
                    validations=[],
                    supported_count=0,
                    unsupported_count=0,
                )
                return AgentResult(output=output, stats=self.get_stats())

            # Format sources for prompt
            sources_text = "\n".join(
                f"- [{s.source_id}] {s.title} ({s.year or 'n/a'})"
                + (f"\n  Abstract: {s.abstract_excerpt[:200]}..." if s.abstract_excerpt else "")
                for s in input_data.sources[:10]  # Limit to top 10 sources
            )

            # Format claims
            claims_text = "\n".join(
                f"{i+1}. {claim}" for i, claim in enumerate(input_data.claims)
            )

            # Call LLM for validation
            response = self.llm_call(
                messages=[
                    self._make_system_message(SYSTEM_PROMPT),
                    self._make_user_message(
                        VALIDATION_PROMPT.format(
                            sources=sources_text,
                            claims=claims_text,
                        )
                    ),
                ],
                temperature=0.1,
                max_tokens=2000,
            )

            # Parse validations
            validations = self._parse_validations(response.content, input_data.claims)

            # Count supported/unsupported
            supported = sum(1 for v in validations if v.is_supported)
            unsupported = len(validations) - supported

            output = ValidatorOutput(
                success=True,
                validations=validations,
                supported_count=supported,
                unsupported_count=unsupported,
            )

        except Exception as e:
            output = ValidatorOutput(
                success=False,
                error=str(e),
                validations=[],
                supported_count=0,
                unsupported_count=0,
            )

        return AgentResult(output=output, stats=self.get_stats())

    def _parse_validations(
        self, content: str, original_claims: list[str]
    ) -> list[ClaimValidation]:
        """Parse LLM response into ClaimValidation objects."""
        validations: list[ClaimValidation] = []

        try:
            # Extract JSON from response
            clean_content = content.strip()

            # Try to extract from markdown code block first
            code_block_match = re.search(r"```(?:json)?\s*([\[\{].*?[\]\}])\s*```", clean_content, re.DOTALL)
            if code_block_match:
                clean_content = code_block_match.group(1)
            else:
                # Try to find raw JSON array
                array_match = re.search(r"(\[[\s\S]*\])", clean_content)
                if array_match:
                    clean_content = array_match.group(1)

            parsed = json.loads(clean_content)

            if isinstance(parsed, list):
                for item in parsed:
                    validations.append(
                        ClaimValidation(
                            claim=item.get("claim", ""),
                            is_supported=item.get("is_supported", False),
                            supporting_source_ids=item.get("supporting_source_ids", []),
                            confidence=item.get("confidence", 0.0),
                            notes=item.get("notes"),
                        )
                    )

        except (json.JSONDecodeError, TypeError, KeyError):
            # Fallback: create unvalidated entries for each claim
            validations = [
                ClaimValidation(
                    claim=claim,
                    is_supported=False,
                    supporting_source_ids=[],
                    confidence=0.0,
                    notes="Validation parsing failed",
                )
                for claim in original_claims
            ]

        return validations
