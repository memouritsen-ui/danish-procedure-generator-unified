"""
Paradox Resolver Agent - Reconciles conflicts between high-weight evidence and Danish guidelines.
"""

from __future__ import annotations

import logging

from procedurewriter.agents.base import AgentResult, BaseAgent
from procedurewriter.agents.models import ParadoxResolverInput, ParadoxResolverOutput, SourceReference

# Import provider-specific exceptions with fallbacks
try:
    from openai import APIError as OpenAIError
except ImportError:
    OpenAIError = type(None)  # type: ignore[misc,assignment]

try:
    from anthropic import APIError as AnthropicError
except ImportError:
    AnthropicError = type(None)  # type: ignore[misc,assignment]

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You compare clinical evidence sources for conflicts.

Goal:
- Compare high-weight international evidence with Danish guidelines.
- If conflicts exist (drug choice, dosing, equipment, thresholds), write a "Clinical Adaptation Note".
- If no conflicts exist, return exactly: NO_CONFLICT

Output:
- If conflicts: a short Clinical Adaptation Note (2-5 bullets) for the writer.
- If no conflicts: NO_CONFLICT
"""


class ParadoxResolverAgent(BaseAgent[ParadoxResolverInput, ParadoxResolverOutput]):
    """Agent that reconciles high-weight evidence with Danish guidelines."""

    @property
    def name(self) -> str:
        return "ParadoxResolver"

    def execute(self, input_data: ParadoxResolverInput) -> AgentResult[ParadoxResolverOutput]:
        self.reset_stats()

        try:
            high_weight, danish_guidelines = self._partition_sources(input_data.sources)
            compared_ids = [s.source_id for s in high_weight + danish_guidelines]

            if not high_weight or not danish_guidelines:
                output = ParadoxResolverOutput(
                    success=True,
                    conflicts_detected=False,
                    adaptation_note=None,
                    compared_sources=compared_ids,
                )
                return AgentResult(output=output, stats=self.get_stats())

            prompt = self._build_prompt(
                procedure=input_data.procedure_title,
                high_weight_sources=high_weight,
                danish_sources=danish_guidelines,
            )

            response = self.llm_call(
                messages=[
                    self._make_system_message(SYSTEM_PROMPT),
                    self._make_user_message(prompt),
                ],
                temperature=0.2,
                max_tokens=1200,
            )

            note = response.content.strip()
            if note == "NO_CONFLICT":
                output = ParadoxResolverOutput(
                    success=True,
                    conflicts_detected=False,
                    adaptation_note=None,
                    compared_sources=compared_ids,
                )
            else:
                output = ParadoxResolverOutput(
                    success=True,
                    conflicts_detected=True,
                    adaptation_note=note,
                    compared_sources=compared_ids,
                )

        except (OpenAIError, AnthropicError, OSError, KeyError, AttributeError, TypeError) as e:
            logger.error(f"ParadoxResolver failed: {e}")
            output = ParadoxResolverOutput(
                success=False,
                error=str(e),
                conflicts_detected=False,
                adaptation_note=None,
                compared_sources=[],
            )

        return AgentResult(output=output, stats=self.get_stats())

    def _partition_sources(
        self, sources: list[SourceReference]
    ) -> tuple[list[SourceReference], list[SourceReference]]:
        high_weight: list[SourceReference] = []
        danish: list[SourceReference] = []
        for src in sources:
            weight = _evidence_weight(src)
            tier = (src.evidence_tier or src.source_type or "").lower()
            if weight > 0.8:
                high_weight.append(src)
            elif tier == "danish_guideline":
                danish.append(src)
        return high_weight, danish

    def _build_prompt(
        self,
        *,
        procedure: str,
        high_weight_sources: list[SourceReference],
        danish_sources: list[SourceReference],
    ) -> str:
        def _format_sources(items: list[SourceReference]) -> str:
            lines = []
            for src in items:
                summary = (src.abstract_excerpt or src.abstract or "").strip()
                if summary:
                    summary = summary.replace("\n", " ")
                lines.append(f"- [S:{src.source_id}] {src.title} :: {summary}")
            return "\n".join(lines)

        return (
            f"Procedure: {procedure}\n\n"
            "High-weight international evidence (weight > 0.8):\n"
            f"{_format_sources(high_weight_sources)}\n\n"
            "Danish guidelines (weight 0.4):\n"
            f"{_format_sources(danish_sources)}"
        )


def _evidence_weight(source: SourceReference) -> float:
    tier = (source.evidence_tier or source.source_type or "unclassified").lower()
    weights = {
        "systematic_review": 1.0,
        "meta_analysis": 1.0,
        "rct": 0.9,
        "international_guideline": 0.7,
        "danish_guideline": 0.4,
        "local_protocol": 0.2,
    }
    return float(weights.get(tier, 0.3))
