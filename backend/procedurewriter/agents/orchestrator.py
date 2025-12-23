"""
Agent Orchestrator - Coordinates the multi-agent workflow.

Responsible for:
1. Running agents in sequence: Research → Validate → Write → Edit → Quality
2. Managing quality loop (re-run if score < threshold)
3. Aggregating costs and statistics
4. Handling errors gracefully
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from procedurewriter.agents.base import AgentStats
from procedurewriter.agents.editor import EditorAgent
from procedurewriter.agents.models import (
    EditorInput,
    ParadoxResolverInput,
    PipelineInput,
    PipelineOutput,
    QualityInput,
    ResearcherInput,
    SourceReference,
    ValidatorInput,
    WriterInput,
)
from procedurewriter.agents.quality import QualityAgent
from procedurewriter.agents.paradox_resolver import ParadoxResolverAgent
from procedurewriter.agents.researcher import ResearcherAgent
from procedurewriter.agents.validator import ValidatorAgent
from procedurewriter.agents.writer import WriterAgent
from procedurewriter.pipeline.events import EventEmitter, EventType

# Import provider-specific exceptions with fallbacks
try:
    from openai import APIError as OpenAIError
except ImportError:
    OpenAIError = type(None)  # type: ignore[misc,assignment]

try:
    from anthropic import APIError as AnthropicError
except ImportError:
    AnthropicError = type(None)  # type: ignore[misc,assignment]

if TYPE_CHECKING:
    from procedurewriter.llm.providers import LLMProvider

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorStats:
    """Aggregated statistics from all agents."""
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    agent_stats: dict[str, AgentStats] = field(default_factory=dict)
    iterations: int = 0
    execution_time_seconds: float = 0.0

    def add_agent_stats(self, agent_name: str, stats: AgentStats) -> None:
        """Add stats from an agent run."""
        self.total_input_tokens += stats.input_tokens
        self.total_output_tokens += stats.output_tokens
        self.total_cost_usd += stats.cost_usd
        self.agent_stats[agent_name] = stats


class AgentOrchestrator:
    """
    Orchestrates the multi-agent procedure generation workflow.

    Flow:
        1. Researcher: Find and rank PubMed sources
        2. Writer: Generate initial procedure content
        3. Validator: Validate claims against sources
        4. Editor: Improve prose and Danish quality
        5. Quality: Score and determine if revision needed

    If quality score < threshold, loop back to Writer with revision suggestions.
    """

    def __init__(
        self,
        llm: LLMProvider,
        model: str | None = None,
        pubmed_client: object | None = None,
        emitter: EventEmitter | None = None,
    ):
        """
        Initialize the orchestrator with agents.

        Args:
            llm: LLM provider for all agents
            model: Model to use (defaults to provider's default)
            pubmed_client: Optional PubMed client (for research step)
            emitter: Optional event emitter for SSE streaming
        """
        self._llm = llm
        self._model = model
        self._pubmed = pubmed_client
        self._emitter = emitter

        # Initialize agents
        self._researcher = ResearcherAgent(llm, model, pubmed_client)
        self._paradox = ParadoxResolverAgent(llm, model)
        self._validator = ValidatorAgent(llm, model)
        self._writer = WriterAgent(llm, model)
        self._editor = EditorAgent(llm, model)
        self._quality = QualityAgent(llm, model)

        self._stats = OrchestratorStats()

    def _emit(self, event_type: EventType, data: dict[str, Any]) -> None:
        """Emit an event if emitter is configured."""
        if self._emitter:
            self._emitter.emit(event_type, data)

    def run(
        self,
        input_data: PipelineInput,
        sources: list[SourceReference] | None = None,
    ) -> PipelineOutput:
        """
        Run the complete agent pipeline.

        Args:
            input_data: Pipeline input with procedure title and settings
            sources: Optional pre-fetched sources (skips researcher step)

        Returns:
            PipelineOutput with generated procedure or error
        """
        start_time = time.time()
        self._stats = OrchestratorStats()

        logger.info(f"Starting pipeline for: {input_data.procedure_title}")

        try:
            evidence_flags: list[str] = list(input_data.evidence_flags or [])
            # Step 1: Research (or use provided sources)
            if sources:
                logger.info(f"Using {len(sources)} pre-fetched sources")
                current_sources = sources
                self._emit(EventType.SOURCES_FOUND, {
                    "count": len(sources),
                    "source": "pre-fetched",
                })
            else:
                self._emit(EventType.AGENT_START, {"agent": "Researcher"})
                logger.info("Running Researcher agent...")
                research_result = self._researcher.execute(
                    ResearcherInput(
                        procedure_title=input_data.procedure_title,
                        context=input_data.context,
                    )
                )
                self._stats.add_agent_stats("Researcher", research_result.stats)
                self._emit(EventType.AGENT_COMPLETE, {
                    "agent": "Researcher",
                    "success": research_result.output.success,
                    "cost_usd": research_result.stats.cost_usd,
                })

                if not research_result.output.success:
                    self._emit(EventType.ERROR, {
                        "stage": "research",
                        "error": research_result.output.error,
                    })
                    return self._error_output(
                        f"Research failed: {research_result.output.error}"
                    )

                current_sources = research_result.output.sources
                for flag in research_result.output.evidence_flags:
                    if flag not in evidence_flags:
                        evidence_flags.append(flag)
                logger.info(f"Found {len(current_sources)} sources")
                self._emit(EventType.SOURCES_FOUND, {
                    "count": len(current_sources),
                    "source": "researcher",
                })

            # Quality loop
            current_content = ""
            quality_score = 0
            stop_reason: str | None = None
            revision_suggestions: list[str] = []
            adaptation_note: str | None = None

            # Paradox resolution (international evidence vs Danish guidelines)
            if current_sources:
                self._emit(EventType.AGENT_START, {"agent": "ParadoxResolver"})
                paradox_result = self._paradox.execute(
                    ParadoxResolverInput(
                        procedure_title=input_data.procedure_title,
                        context=input_data.context,
                        sources=current_sources,
                    )
                )
                self._stats.add_agent_stats("ParadoxResolver", paradox_result.stats)
                self._emit(EventType.AGENT_COMPLETE, {
                    "agent": "ParadoxResolver",
                    "success": paradox_result.output.success,
                    "cost_usd": paradox_result.stats.cost_usd,
                })

                if paradox_result.output.success and paradox_result.output.adaptation_note:
                    adaptation_note = paradox_result.output.adaptation_note

            for iteration in range(1, input_data.max_iterations + 1):
                self._stats.iterations = iteration
                logger.info(f"Iteration {iteration}/{input_data.max_iterations}")
                self._emit(EventType.ITERATION_START, {
                    "iteration": iteration,
                    "max_iterations": input_data.max_iterations,
                })

                # Step 2: Write procedure
                self._emit(EventType.AGENT_START, {"agent": "Writer"})
                logger.info("Running Writer agent...")
                base_style_guide = input_data.style_guide or ""
                if input_data.evidence_summary:
                    base_style_guide = (
                        base_style_guide
                        + "\n\nEVIDENS-SYNTES:\n"
                        + input_data.evidence_summary
                    ).strip()

                style_guide = base_style_guide
                if revision_suggestions:
                    style_guide = (
                        style_guide
                        + "\n\nRevision notes:\n- "
                        + "\n- ".join(revision_suggestions)
                    ).strip()
                if adaptation_note:
                    style_guide = (
                        style_guide
                        + "\n\nClinical Adaptation Note:\n"
                        + adaptation_note
                    ).strip()

                writer_result = self._writer.execute(
                    WriterInput(
                        procedure_title=input_data.procedure_title,
                        context=input_data.context,
                        sources=current_sources,
                        outline=input_data.outline,
                        style_guide=style_guide or None,
                        evidence_flags=evidence_flags or None,
                    )
                )
                self._stats.add_agent_stats(f"Writer_iter{iteration}", writer_result.stats)
                self._emit(EventType.AGENT_COMPLETE, {
                    "agent": "Writer",
                    "success": writer_result.output.success,
                    "cost_usd": writer_result.stats.cost_usd,
                })

                if not writer_result.output.success:
                    self._emit(EventType.ERROR, {
                        "stage": "writer",
                        "error": writer_result.output.error,
                    })
                    return self._error_output(
                        f"Writing failed: {writer_result.output.error}"
                    )

                current_content = writer_result.output.content_markdown
                citations_used = writer_result.output.citations_used

                # Step 3: Validate claims (chunked for long procedures)
                self._emit(EventType.AGENT_START, {"agent": "Validator"})
                logger.info("Running Validator agent...")
                # Extract claims and chunk for validation
                claim_chunks = self._extract_claims(current_content)

                validator_total_cost = 0.0
                last_validator_stats = None
                if claim_chunks:
                    for chunk_idx, claims in enumerate(claim_chunks):
                        if chunk_idx > 0:
                            logger.info(f"Validating chunk {chunk_idx + 1}/{len(claim_chunks)}")

                        validator_result = self._validator.execute(
                            ValidatorInput(
                                procedure_title=input_data.procedure_title,
                                claims=claims,
                                sources=current_sources,
                            )
                        )
                        validator_total_cost += validator_result.stats.cost_usd
                        last_validator_stats = validator_result.stats

                    if last_validator_stats:
                        self._stats.add_agent_stats(f"Validator_iter{iteration}", last_validator_stats)
                else:
                    logger.warning("No claims found to validate in content")

                self._emit(EventType.AGENT_COMPLETE, {
                    "agent": "Validator",
                    "success": True,
                    "cost_usd": validator_total_cost,
                    "chunks_validated": len(claim_chunks),
                })

                # Step 4: Edit content
                self._emit(EventType.AGENT_START, {"agent": "Editor"})
                logger.info("Running Editor agent...")
                editor_result = self._editor.execute(
                    EditorInput(
                        procedure_title=input_data.procedure_title,
                        content_markdown=current_content,
                        sources=current_sources,
                        style_guide=base_style_guide or None,
                    )
                )
                self._stats.add_agent_stats(f"Editor_iter{iteration}", editor_result.stats)
                self._emit(EventType.AGENT_COMPLETE, {
                    "agent": "Editor",
                    "success": editor_result.output.success,
                    "cost_usd": editor_result.stats.cost_usd,
                })

                if editor_result.output.success:
                    current_content = editor_result.output.edited_content

                # Step 5: Quality check
                self._emit(EventType.AGENT_START, {"agent": "Quality"})
                logger.info("Running Quality agent...")
                quality_result = self._quality.execute(
                    QualityInput(
                        procedure_title=input_data.procedure_title,
                        content_markdown=current_content,
                        sources=current_sources,
                        citations_used=citations_used,
                    )
                )
                self._stats.add_agent_stats(f"Quality_iter{iteration}", quality_result.stats)

                quality_score = quality_result.output.overall_score
                logger.info(f"Quality score: {quality_score}/10")

                self._emit(EventType.QUALITY_CHECK, {
                    "score": quality_score,
                    "passes": quality_result.output.passes_threshold,
                    "iteration": iteration,
                })
                self._emit(EventType.AGENT_COMPLETE, {
                    "agent": "Quality",
                    "success": True,
                    "cost_usd": quality_result.stats.cost_usd,
                })

                # Emit running cost update
                self._emit(EventType.COST_UPDATE, {
                    "total_cost_usd": self._stats.total_cost_usd,
                    "total_tokens": self._stats.total_input_tokens + self._stats.total_output_tokens,
                })

                # Check if we pass threshold
                if quality_result.output.passes_threshold:
                    logger.info("Quality threshold met!")
                    break

                # Stop early if manual policy or cost cap reached
                if input_data.quality_loop_policy == "manual":
                    stop_reason = "manual"
                    logger.info("Quality loop stopped: manual approval required")
                    break
                if (
                    input_data.quality_loop_policy == "auto"
                    and input_data.quality_loop_max_cost_usd is not None
                    and self._stats.total_cost_usd >= input_data.quality_loop_max_cost_usd
                ):
                    stop_reason = "cost_cap"
                    logger.info("Quality loop stopped: cost cap reached")
                    break

                # Prepare for next iteration with specific suggestions
                revision_suggestions = quality_result.output.revision_suggestions

                # Generate specific fallback suggestions based on low-scoring criteria
                if not revision_suggestions:
                    revision_suggestions = self._generate_fallback_suggestions(
                        quality_result.output.criteria,
                        quality_result.output.overall_score
                    )

                logger.info(f"Quality below threshold, revising with {len(revision_suggestions)} suggestions")

            # Calculate final stats
            self._stats.execution_time_seconds = time.time() - start_time

            # Emit completion
            self._emit(EventType.COMPLETE, {
                "success": True,
                "quality_score": quality_score,
                "iterations_used": self._stats.iterations,
                "total_cost_usd": self._stats.total_cost_usd,
                "execution_time_seconds": self._stats.execution_time_seconds,
            })

            return PipelineOutput(
                success=True,
                procedure_markdown=current_content,
                sources=current_sources,
                quality_score=quality_score,
                iterations_used=self._stats.iterations,
                total_input_tokens=self._stats.total_input_tokens,
                total_output_tokens=self._stats.total_output_tokens,
                total_cost_usd=self._stats.total_cost_usd,
                quality_loop_stop_reason=stop_reason,
            )

        except (OpenAIError, AnthropicError, OSError, KeyError, AttributeError, TypeError) as e:
            # LLM API, network, or response parsing errors - return failure output
            logger.error(f"Pipeline failed: {e}")
            self._emit(EventType.ERROR, {
                "stage": "pipeline",
                "error": str(e),
            })
            return self._error_output(str(e))

    def _extract_claims(
        self,
        content: str,
        *,
        max_claims_per_chunk: int = 25,
    ) -> list[list[str]]:
        """Extract factual claims from content and chunk for validation.

        Args:
            content: Markdown content with citations
            max_claims_per_chunk: Maximum claims per validation batch
                                  (prevents token overflow in validator)

        Returns:
            List of claim chunks. Each chunk is a list of claim strings.
            Empty list if no claims found.

        Note:
            All claims are extracted - no arbitrary limit.
            Claims are chunked to respect validator's token budget.
        """
        import re

        all_claims: list[str] = []
        # Split into sentences
        sentences = re.split(r"(?<=[.!?])\s+", content)

        for sentence in sentences:
            # Include sentences that have citations
            if re.search(r"\[[a-zA-Z0-9_-]+\]", sentence):
                # Clean up the sentence
                clean = sentence.strip()
                if len(clean) > 20:  # Skip very short fragments
                    all_claims.append(clean)

        if not all_claims:
            return []

        # Chunk claims for validation
        chunks: list[list[str]] = []
        for i in range(0, len(all_claims), max_claims_per_chunk):
            chunk = all_claims[i:i + max_claims_per_chunk]
            chunks.append(chunk)

        logger.info(
            "Extracted %d claims in %d chunks (max %d per chunk)",
            len(all_claims), len(chunks), max_claims_per_chunk
        )
        return chunks

    def _generate_fallback_suggestions(
        self,
        criteria: list,
        overall_score: int
    ) -> list[str]:
        """Generate specific revision suggestions based on low-scoring criteria.

        Args:
            criteria: List of QualityCriterion from quality assessment
            overall_score: Overall quality score (1-10)

        Returns:
            List of specific revision suggestions
        """
        suggestions = []

        # Map criteria names to specific improvement suggestions
        CRITERIA_SUGGESTIONS = {
            "Faglig korrekthed": [
                "Verificer alle medicinske påstande mod primære kilder",
                "Tjek doser og intervaller mod gældende retningslinjer",
            ],
            "Klinisk specificitet (TINTINALLI-NIVEAU)": [
                "Tilføj PRÆCISE doser med mg/kg og max-doser",
                "Beskriv ANATOMISKE landmarks detaljeret",
                "Tilføj PÆDIATRISKE og GERIATRISKE variationer",
                "Angiv MONITORERING-parametre og intervaller",
            ],
            "Citationsdækning": [
                "Tilføj kildehenvisning til alle faktuelle påstande",
                "Prioriter højkvalitets kilder (guidelines, systematic reviews)",
            ],
            "Klarhed og trin-for-trin": [
                "Omstrukturer til nummererede trin i logisk rækkefølge",
                "Fjern tvetydigheder og uklare formuleringer",
            ],
            "Fuldstændighed": [
                "Tilføj afsnit om komplikationer og deres håndtering",
                "Inkluder komplet udstyrsliste",
                "Beskriv patientpositionering",
            ],
            "Dansk sprogkvalitet": [
                "Gennemgå for konsistent dansk terminologi",
                "Erstat engelske termer med danske ækvivalenter",
            ],
        }

        # Find low-scoring criteria (score < 7)
        for criterion in criteria:
            if hasattr(criterion, 'score') and criterion.score < 7:
                criterion_name = criterion.name if hasattr(criterion, 'name') else str(criterion)

                # Find matching suggestions
                for key, suggestion_list in CRITERIA_SUGGESTIONS.items():
                    if key.lower() in criterion_name.lower():
                        suggestions.extend(suggestion_list[:2])  # Take first 2 suggestions
                        break

        # Add notes from low-scoring criteria as suggestions
        for criterion in criteria:
            if hasattr(criterion, 'score') and criterion.score < 7:
                if hasattr(criterion, 'notes') and criterion.notes:
                    suggestions.append(f"Kvalitetsnote: {criterion.notes}")

        # Fallback if still no suggestions
        if not suggestions:
            if overall_score < 5:
                suggestions = [
                    "Omfattende revision påkrævet - gennemgå alle sektioner",
                    "Tilføj præcise doser og anatomiske detaljer",
                    "Sikr at alle påstande har kildehenvisning",
                ]
            else:
                suggestions = [
                    "Forbedre klinisk specificitet med præcise doser",
                    "Tilføj pædiatriske/geriatriske variationer",
                    "Udvid komplikationsafsnit",
                ]

        return suggestions[:5]  # Limit to 5 suggestions

    def _error_output(self, error: str) -> PipelineOutput:
        """Create error output."""
        return PipelineOutput(
            success=False,
            error=error,
            iterations_used=self._stats.iterations,
            total_input_tokens=self._stats.total_input_tokens,
            total_output_tokens=self._stats.total_output_tokens,
            total_cost_usd=self._stats.total_cost_usd,
        )

    def get_stats(self) -> OrchestratorStats:
        """Get aggregated statistics."""
        return self._stats
