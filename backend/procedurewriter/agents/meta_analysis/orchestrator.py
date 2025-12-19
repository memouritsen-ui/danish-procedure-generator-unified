"""Meta-analysis orchestrator coordinating the full pipeline.

Orchestrates: PICO extraction → Screening → Bias assessment → Synthesis
Uses lazy imports for sub-agents to avoid circular dependencies.
Integrates with EventEmitter for real-time progress updates.
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from procedurewriter.agents.base import AgentResult, BaseAgent
from procedurewriter.agents.meta_analysis.screener_agent import PICOQuery
from procedurewriter.llm.providers import LLMProvider
from procedurewriter.pipeline.events import EventEmitter, EventType

if TYPE_CHECKING:
    from procedurewriter.agents.meta_analysis.bias_agent import BiasAssessmentAgent
    from procedurewriter.agents.meta_analysis.pico_extractor import PICOExtractor
    from procedurewriter.agents.meta_analysis.screener_agent import StudyScreenerAgent
    from procedurewriter.agents.meta_analysis.synthesizer_agent import (
        EvidenceSynthesizerAgent,
        SynthesisOutput,
    )

logger = logging.getLogger(__name__)


# =============================================================================
# Input/Output Models
# =============================================================================


class StudySource(BaseModel):
    """Source data for a single study."""
    study_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    abstract: str = Field(..., min_length=1)
    methods: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    sample_size: int | None = None
    effect_size: float | None = None
    variance: float | None = None
    ci_lower: float | None = None
    ci_upper: float | None = None


class OrchestratorInput(BaseModel):
    """Input for meta-analysis orchestration."""
    query: PICOQuery
    study_sources: list[dict[str, Any]]
    outcome_of_interest: str = Field(..., min_length=1)
    run_id: str | None = None


class OrchestratorOutput(BaseModel):
    """Output from meta-analysis orchestration."""
    synthesis: Any  # SynthesisOutput - use Any to avoid import issues
    included_study_ids: list[str]
    excluded_study_ids: list[str]
    exclusion_reasons: dict[str, str]
    manual_review_needed: list[str]


# =============================================================================
# Orchestrator Implementation
# =============================================================================


class MetaAnalysisOrchestrator(BaseAgent[OrchestratorInput, OrchestratorOutput]):
    """Orchestrator for complete meta-analysis pipeline.

    Coordinates the following stages:
    1. PICO extraction from study abstracts
    2. Screening against user's PICO query
    3. Bias assessment using RoB 2.0
    4. Evidence synthesis with DerSimonian-Laird

    Uses lazy imports to avoid circular dependencies and reduce
    initial load time when only specific agents are needed.
    """

    def __init__(
        self,
        llm: LLMProvider,
        model: str | None = None,
        emitter: EventEmitter | None = None,
    ) -> None:
        """Initialize meta-analysis orchestrator.

        Args:
            llm: LLM provider for all sub-agents.
            model: Model name override.
            emitter: Optional event emitter for progress updates.
        """
        super().__init__(llm, model)
        self._emitter = emitter

        # Lazy-loaded sub-agents
        self._pico_extractor: PICOExtractor | None = None
        self._screener: StudyScreenerAgent | None = None
        self._bias_agent: BiasAssessmentAgent | None = None
        self._synthesizer: EvidenceSynthesizerAgent | None = None

    @property
    def name(self) -> str:
        return "meta_analysis_orchestrator"

    # =========================================================================
    # Lazy-loaded Sub-agents
    # =========================================================================

    @property
    def pico_extractor(self) -> PICOExtractor:
        """Get or create PICO extractor (lazy import)."""
        if self._pico_extractor is None:
            from procedurewriter.agents.meta_analysis.pico_extractor import (
                PICOExtractor,
            )
            self._pico_extractor = PICOExtractor(self._llm, self._model)
        return self._pico_extractor

    @property
    def screener(self) -> StudyScreenerAgent:
        """Get or create study screener (lazy import)."""
        if self._screener is None:
            from procedurewriter.agents.meta_analysis.screener_agent import (
                StudyScreenerAgent,
            )
            self._screener = StudyScreenerAgent(self._llm, self._model)
        return self._screener

    @property
    def bias_agent(self) -> BiasAssessmentAgent:
        """Get or create bias assessment agent (lazy import)."""
        if self._bias_agent is None:
            from procedurewriter.agents.meta_analysis.bias_agent import (
                BiasAssessmentAgent,
            )
            self._bias_agent = BiasAssessmentAgent(self._llm, self._model)
        return self._bias_agent

    @property
    def synthesizer(self) -> EvidenceSynthesizerAgent:
        """Get or create evidence synthesizer (lazy import)."""
        if self._synthesizer is None:
            from procedurewriter.agents.meta_analysis.synthesizer_agent import (
                EvidenceSynthesizerAgent,
            )
            self._synthesizer = EvidenceSynthesizerAgent(self._llm, self._model)
        return self._synthesizer

    # =========================================================================
    # Event Emission
    # =========================================================================

    def _emit(self, event_type: EventType, data: dict[str, Any]) -> None:
        """Emit event if emitter is available."""
        if self._emitter is not None:
            self._emitter.emit(event_type, data)

    # =========================================================================
    # Execution
    # =========================================================================

    def execute(self, input_data: OrchestratorInput) -> AgentResult[OrchestratorOutput]:
        """Execute full meta-analysis pipeline.

        Args:
            input_data: Studies and PICO query for analysis.

        Returns:
            AgentResult containing OrchestratorOutput with synthesis results.
        """
        from procedurewriter.agents.meta_analysis.bias_agent import BiasAssessmentInput
        from procedurewriter.agents.meta_analysis.models import (
            StatisticalMetrics,
            StudyResult,
        )
        from procedurewriter.agents.meta_analysis.pico_extractor import (
            PICOExtractionInput,
        )
        from procedurewriter.agents.meta_analysis.screener_agent import ScreeningInput
        from procedurewriter.agents.meta_analysis.synthesizer_agent import (
            SynthesisInput,
        )

        included_studies: list[StudyResult] = []
        excluded_study_ids: list[str] = []
        exclusion_reasons: dict[str, str] = {}
        manual_review_needed: list[str] = []

        # Process each study through the pipeline
        for study_source in input_data.study_sources:
            study_id = study_source.get("study_id", "unknown")
            title = study_source.get("title", "")
            abstract = study_source.get("abstract", "")
            methods = study_source.get("methods")

            # Stage 1: PICO Extraction
            pico_input = PICOExtractionInput(
                study_id=study_id,
                title=title,
                abstract=abstract,
            )
            pico_result = self.pico_extractor.execute(pico_input)
            pico_data = pico_result.output

            self._emit(EventType.PICO_EXTRACTED, {
                "study_id": study_id,
                "pico": {
                    "population": pico_data.population,
                    "intervention": pico_data.intervention,
                    "comparison": pico_data.comparison,
                    "outcome": pico_data.outcome,
                    "confidence": pico_data.confidence,
                },
            })

            # Stage 2: Screening
            screening_input = ScreeningInput(
                study_id=study_id,
                pico_data=pico_data,
                query=input_data.query,
            )
            screening_result = self.screener.execute(screening_input)
            decision = screening_result.output

            if decision.needs_manual_verification:
                manual_review_needed.append(study_id)

            if decision.decision == "Exclude":
                excluded_study_ids.append(study_id)
                exclusion_reasons[study_id] = decision.reason
                continue

            # Stage 3: Bias Assessment
            bias_input = BiasAssessmentInput(
                study_id=study_id,
                title=title,
                abstract=abstract,
                methods=methods,
            )
            bias_result = self.bias_agent.execute(bias_input)

            self._emit(EventType.BIAS_ASSESSED, {
                "study_id": study_id,
                "overall_risk": bias_result.output.assessment.overall.value,
            })

            # Create StudyResult for synthesis
            # Use provided effect size/variance or defaults
            effect_size = study_source.get("effect_size", 0.5)
            variance = study_source.get("variance", 0.04)
            ci_lower = study_source.get("ci_lower", effect_size - 1.96 * (variance ** 0.5))
            ci_upper = study_source.get("ci_upper", effect_size + 1.96 * (variance ** 0.5))

            study_result = StudyResult(
                study_id=study_id,
                title=title,
                authors=study_source.get("authors", []),
                year=study_source.get("year", 2024),
                source=study_source.get("source", "pubmed"),
                sample_size=study_source.get("sample_size", 100),
                pico=pico_data,
                risk_of_bias=bias_result.output.assessment,
                statistics=StatisticalMetrics(
                    effect_size=effect_size,
                    effect_size_type="OR",
                    variance=variance,
                    confidence_interval_lower=ci_lower,
                    confidence_interval_upper=ci_upper,
                    weight=0.0,  # Will be computed during synthesis
                ),
                detected_language=pico_data.detected_language,
            )
            included_studies.append(study_result)

        # Stage 4: Evidence Synthesis
        synthesis_input = SynthesisInput(
            studies=included_studies,
            outcome_of_interest=input_data.outcome_of_interest,
        )
        synthesis_result = self.synthesizer.execute(synthesis_input)

        self._emit(EventType.SYNTHESIS_COMPLETE, {
            "included_studies": len(included_studies),
            "pooled_effect": synthesis_result.output.pooled_estimate.pooled_effect,
            "i_squared": synthesis_result.output.heterogeneity.i_squared,
        })

        output = OrchestratorOutput(
            synthesis=synthesis_result.output,
            included_study_ids=[s.study_id for s in included_studies],
            excluded_study_ids=excluded_study_ids,
            exclusion_reasons=exclusion_reasons,
            manual_review_needed=manual_review_needed,
        )

        return AgentResult(
            output=output,
            stats=self._stats,
        )

    async def execute_async(
        self, input_data: OrchestratorInput
    ) -> AgentResult[OrchestratorOutput]:
        """Execute pipeline asynchronously.

        Wraps sync execute in asyncio.to_thread for non-blocking execution.

        Args:
            input_data: Studies and PICO query for analysis.

        Returns:
            AgentResult containing OrchestratorOutput.
        """
        return await asyncio.to_thread(self.execute, input_data)
