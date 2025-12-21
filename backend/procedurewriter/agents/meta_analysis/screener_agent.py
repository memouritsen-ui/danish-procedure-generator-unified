"""Study screening agent for PICO-based inclusion/exclusion.

Compares extracted PICO data against user's PICO query to determine
study relevance for systematic review inclusion.
"""
from __future__ import annotations

import json
import logging
from typing import Literal

from pydantic import BaseModel, Field

from procedurewriter.agents.base import AgentResult, BaseAgent
from procedurewriter.agents.meta_analysis.models import PICOData
from procedurewriter.llm.providers import LLMProvider

logger = logging.getLogger(__name__)


class PICOQuery(BaseModel):
    """User's PICO query for study screening.

    Defines the target population, intervention, comparison, and outcome
    that studies must match for inclusion in systematic review.
    """
    population: str = Field(..., min_length=1)
    intervention: str = Field(..., min_length=1)
    comparison: str | None = None
    outcome: str = Field(..., min_length=1)


class ScreeningDecision(BaseModel):
    """Output of study screening decision.

    Includes decision, reason, confidence, and optional manual verification flag.
    """
    decision: Literal["Include", "Exclude"] = Field(
        ..., description="Include or Exclude decision"
    )
    reason: str = Field(..., description="Justification for the decision")
    confidence: float = Field(..., ge=0.0, le=1.0)
    needs_manual_verification: bool = Field(
        default=False,
        description="True if low confidence requires manual review",
    )
    verification_reason: str = Field(
        default="",
        description="Reason for requiring manual verification",
    )


class ScreeningInput(BaseModel):
    """Input for study screening."""
    study_id: str = Field(..., min_length=1)
    pico_data: PICOData
    query: PICOQuery


class StudyScreenerAgent(BaseAgent[ScreeningInput, ScreeningDecision]):
    """Agent for screening studies against PICO query.

    Compares extracted PICO elements against the user's query to determine
    whether a study should be included in the systematic review.

    Neurotic Rule: If intervention or outcome confidence is < 0.90, the
    agent flags the study as "Potentially Relevant - Needs Manual Verification".
    """

    def __init__(
        self,
        llm: LLMProvider,
        model: str | None = None,
        confidence_threshold: float = 0.60,  # Lowered from 0.90 - be more inclusive
    ) -> None:
        """Initialize screener agent.

        Args:
            llm: LLM provider for screening decisions.
            model: Model name override.
            confidence_threshold: Minimum confidence for automatic decisions (0-1).
                                 Lowered to 0.60 to include more potentially relevant studies.
        """
        super().__init__(llm, model)
        self._confidence_threshold = confidence_threshold

    @property
    def name(self) -> str:
        return "study_screener"

    def execute(self, input_data: ScreeningInput) -> AgentResult[ScreeningDecision]:
        """Screen study against PICO query.

        Args:
            input_data: Study PICO data and query to match against.

        Returns:
            AgentResult containing ScreeningDecision.
        """
        # Get LLM screening decision
        decision = self._make_screening_decision(input_data)

        # Check if manual verification needed due to low PICO confidence
        needs_verification = input_data.pico_data.confidence < self._confidence_threshold
        verification_reason = ""

        if needs_verification:
            verification_reason = (
                f"PICO extraction confidence ({input_data.pico_data.confidence:.2f}) "
                f"is below threshold ({self._confidence_threshold}). "
                "Manual verification recommended."
            )
            decision = ScreeningDecision(
                decision=decision.decision,
                reason=decision.reason,
                confidence=decision.confidence,
                needs_manual_verification=True,
                verification_reason=verification_reason,
            )

        return AgentResult(
            output=decision,
            stats=self._stats,
        )

    def _make_screening_decision(self, input_data: ScreeningInput) -> ScreeningDecision:
        """Use LLM to make screening decision."""
        prompt = self._build_screening_prompt(input_data)
        messages = [
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "user", "content": prompt},
        ]

        response = self.llm_call(messages, temperature=0.1)
        return self._parse_response(response.content)

    def _get_system_prompt(self) -> str:
        """System prompt for study screening."""
        return """You are an expert systematic review methodologist with an INCLUSIVE approach.

Your task is to screen a study for RELEVANCE to a medical procedure review.

IMPORTANT: Err on the side of INCLUSION. Include any study that might provide useful evidence.

DECISION CRITERIA:
- Include: Study addresses the procedure or related aspects (population, intervention, OR outcomes)
- Include: Study provides relevant background, techniques, or evidence
- Include: Partial matches where at least 2 of 4 PICO elements match
- Exclude ONLY if clearly irrelevant (different body system, unrelated condition, wrong study type)

WHEN IN DOUBT, INCLUDE. Missing a relevant study is worse than including a tangentially relevant one.

When comparing:
1. Population: Accept related populations (e.g., "adults with chest trauma" matches "pneumothorax patients")
2. Intervention: Accept related techniques (e.g., "chest tube insertion" matches "thoracostomy")
3. Comparison: Be flexible - any reasonable comparator is acceptable
4. Outcome: Accept any clinically relevant outcome (success rates, complications, mortality, etc.)

PARTIAL MATCH SCORING:
- 4/4 PICO match: Include with high confidence (0.9+)
- 3/4 PICO match: Include with good confidence (0.7-0.9)
- 2/4 PICO match: Include with moderate confidence (0.5-0.7)
- 1/4 PICO match: Include with low confidence if highly relevant (0.3-0.5)
- 0/4 PICO match: Exclude

OUTPUT FORMAT (JSON):
{
    "decision": "Include" or "Exclude",
    "reason": "Clear explanation of decision",
    "confidence": 0.0-1.0,
    "pico_matches": 0-4
}

Respond ONLY with valid JSON. No explanatory text."""

    def _build_screening_prompt(self, input_data: ScreeningInput) -> str:
        """Build screening prompt from input data."""
        return f"""STUDY PICO (Extracted):
- Population: {input_data.pico_data.population}
- Intervention: {input_data.pico_data.intervention}
- Comparison: {input_data.pico_data.comparison or 'Not specified'}
- Outcome: {input_data.pico_data.outcome}
- Extraction Confidence: {input_data.pico_data.confidence:.2f}

REVIEW QUERY (Target):
- Population: {input_data.query.population}
- Intervention: {input_data.query.intervention}
- Comparison: {input_data.query.comparison or 'Not specified'}
- Outcome: {input_data.query.outcome}

Should this study be INCLUDED or EXCLUDED from the systematic review?"""

    def _parse_response(self, content: str) -> ScreeningDecision:
        """Parse LLM response into ScreeningDecision."""
        try:
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            data = json.loads(content)

            return ScreeningDecision(
                decision=data["decision"],
                reason=data["reason"],
                confidence=data.get("confidence", 0.8),
                needs_manual_verification=False,
                verification_reason="",
            )

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse screening response: {e}")
            # Default to exclude with low confidence on parse failure
            return ScreeningDecision(
                decision="Exclude",
                reason="Failed to parse screening response",
                confidence=0.0,
                needs_manual_verification=True,
                verification_reason="Parse error - manual review required",
            )
