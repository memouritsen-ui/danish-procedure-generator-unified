"""Bias assessment agent using Cochrane Risk of Bias 2.0.

Assesses randomized trials across 5 RoB 2.0 domains and detects
linguistic markers for blinding, ITT analysis, and power calculations.
"""
from __future__ import annotations

import json
import logging

from pydantic import BaseModel, Field

from procedurewriter.agents.base import AgentResult, BaseAgent
from procedurewriter.agents.meta_analysis.models import RiskOfBias, RiskOfBiasAssessment
from procedurewriter.llm.providers import LLMProvider

logger = logging.getLogger(__name__)


class BiasAssessmentInput(BaseModel):
    """Input for bias assessment."""
    study_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    abstract: str = Field(..., min_length=1)
    methods: str | None = None


class BiasAssessmentOutput(BaseModel):
    """Output of bias assessment including RoB 2.0 domains and linguistic markers."""
    study_id: str
    assessment: RiskOfBiasAssessment
    linguistic_markers: dict[str, bool] = Field(
        description="Detected linguistic markers: blinding, intention_to_treat, power_analysis"
    )
    domain_justifications: dict[str, str] = Field(
        description="Justification for each domain assessment"
    )


class BiasAssessmentAgent(BaseAgent[BiasAssessmentInput, BiasAssessmentOutput]):
    """Agent for assessing risk of bias using Cochrane RoB 2.0.

    Evaluates randomized trials across 5 domains:
    1. Randomization process
    2. Deviations from intended interventions
    3. Missing outcome data
    4. Measurement of the outcome
    5. Selection of the reported result

    Also detects linguistic markers for:
    - Blinding (double-blind, single-blind, open-label)
    - Intention-to-treat analysis
    - Power analysis/sample size calculation
    """

    def __init__(
        self,
        llm: LLMProvider,
        model: str | None = None,
    ) -> None:
        """Initialize bias assessment agent.

        Args:
            llm: LLM provider for bias assessment.
            model: Model name override.
        """
        super().__init__(llm, model)

    @property
    def name(self) -> str:
        return "bias_assessor"

    def execute(self, input_data: BiasAssessmentInput) -> AgentResult[BiasAssessmentOutput]:
        """Assess risk of bias for a study.

        Args:
            input_data: Study text for bias assessment.

        Returns:
            AgentResult containing BiasAssessmentOutput with RoB 2.0 assessment.
        """
        output = self._assess_bias(input_data)

        return AgentResult(
            output=output,
            stats=self._stats,
        )

    def _assess_bias(self, input_data: BiasAssessmentInput) -> BiasAssessmentOutput:
        """Use LLM to assess risk of bias."""
        prompt = self._build_assessment_prompt(input_data)
        messages = [
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "user", "content": prompt},
        ]

        response = self.llm_call(messages, temperature=0.1)
        return self._parse_response(input_data.study_id, response.content)

    def _get_system_prompt(self) -> str:
        """System prompt for RoB 2.0 assessment."""
        return """You are an expert systematic review methodologist specializing in risk of bias assessment.

Your task is to assess a randomized trial using the Cochrane Risk of Bias 2.0 (RoB 2.0) tool.

ASSESS THESE 5 DOMAINS (each as "low", "some_concerns", or "high"):

1. RANDOMIZATION PROCESS
   - Was the allocation sequence random?
   - Was allocation concealment adequate?
   - Were baseline differences concerning?
   Markers: "randomized", "computer-generated", "sealed envelopes", "central allocation"

2. DEVIATIONS FROM INTENDED INTERVENTIONS
   - Were participants/personnel aware of assignment?
   - Were there protocol deviations?
   - Was appropriate analysis used?
   Markers: "double-blind", "blinded", "intention-to-treat", "per-protocol"

3. MISSING OUTCOME DATA
   - Were outcome data available for all randomized?
   - Were dropout reasons balanced?
   - Could missingness affect results?
   Markers: "completers", "dropout", "lost to follow-up", "imputation"

4. MEASUREMENT OF THE OUTCOME
   - Could outcome measurement be influenced by intervention?
   - Were assessors blinded?
   - Were outcome measures appropriate?
   Markers: "blinded outcome assessment", "objective measure", "validated instrument"

5. SELECTION OF THE REPORTED RESULT
   - Was the trial pre-registered?
   - Were all outcomes reported?
   - Was the analysis plan followed?
   Markers: "protocol", "pre-registered", "CONSORT", "all pre-specified"

ALSO DETECT LINGUISTIC MARKERS:
- blinding: Any mention of blinding/masking
- intention_to_treat: ITT analysis mentioned
- power_analysis: Sample size calculation mentioned

OUTPUT FORMAT (JSON):
{
    "randomization": "low" | "some_concerns" | "high",
    "deviations": "low" | "some_concerns" | "high",
    "missing_data": "low" | "some_concerns" | "high",
    "measurement": "low" | "some_concerns" | "high",
    "selection": "low" | "some_concerns" | "high",
    "linguistic_markers": {
        "blinding": true/false,
        "intention_to_treat": true/false,
        "power_analysis": true/false
    },
    "domain_justifications": {
        "randomization": "Brief justification",
        "deviations": "Brief justification",
        "missing_data": "Brief justification",
        "measurement": "Brief justification",
        "selection": "Brief justification"
    }
}

Respond ONLY with valid JSON. No explanatory text."""

    def _build_assessment_prompt(self, input_data: BiasAssessmentInput) -> str:
        """Build assessment prompt from input data."""
        parts = [
            f"Study ID: {input_data.study_id}",
            f"Title: {input_data.title}",
            f"Abstract: {input_data.abstract}",
        ]

        if input_data.methods:
            parts.append(f"Methods: {input_data.methods}")

        return "\n\n".join(parts)

    def _parse_response(self, study_id: str, content: str) -> BiasAssessmentOutput:
        """Parse LLM response into BiasAssessmentOutput."""
        try:
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            data = json.loads(content)

            # Map string values to RiskOfBias enum
            def to_rob(value: str) -> RiskOfBias:
                mapping = {
                    "low": RiskOfBias.LOW,
                    "some_concerns": RiskOfBias.SOME_CONCERNS,
                    "high": RiskOfBias.HIGH,
                }
                return mapping.get(value.lower(), RiskOfBias.SOME_CONCERNS)

            assessment = RiskOfBiasAssessment(
                randomization=to_rob(data["randomization"]),
                deviations=to_rob(data["deviations"]),
                missing_data=to_rob(data["missing_data"]),
                measurement=to_rob(data["measurement"]),
                selection=to_rob(data["selection"]),
            )

            return BiasAssessmentOutput(
                study_id=study_id,
                assessment=assessment,
                linguistic_markers=data.get("linguistic_markers", {
                    "blinding": False,
                    "intention_to_treat": False,
                    "power_analysis": False,
                }),
                domain_justifications=data.get("domain_justifications", {}),
            )

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse bias assessment response: {e}")
            # Return conservative high-risk assessment on failure
            return BiasAssessmentOutput(
                study_id=study_id,
                assessment=RiskOfBiasAssessment(
                    randomization=RiskOfBias.HIGH,
                    deviations=RiskOfBias.HIGH,
                    missing_data=RiskOfBias.HIGH,
                    measurement=RiskOfBias.HIGH,
                    selection=RiskOfBias.HIGH,
                ),
                linguistic_markers={
                    "blinding": False,
                    "intention_to_treat": False,
                    "power_analysis": False,
                },
                domain_justifications={
                    "randomization": "Failed to parse assessment",
                    "deviations": "Failed to parse assessment",
                    "missing_data": "Failed to parse assessment",
                    "measurement": "Failed to parse assessment",
                    "selection": "Failed to parse assessment",
                },
            )
