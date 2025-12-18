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
from typing import TYPE_CHECKING

from procedurewriter.agents.base import AgentStats
from procedurewriter.agents.editor import EditorAgent
from procedurewriter.agents.models import (
    EditorInput,
    PipelineInput,
    PipelineOutput,
    QualityInput,
    ResearcherInput,
    SourceReference,
    ValidatorInput,
    WriterInput,
)
from procedurewriter.agents.quality import QualityAgent
from procedurewriter.agents.researcher import ResearcherAgent
from procedurewriter.agents.validator import ValidatorAgent
from procedurewriter.agents.writer import WriterAgent

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
        llm: "LLMProvider",
        model: str | None = None,
        pubmed_client: object | None = None,
    ):
        """
        Initialize the orchestrator with agents.

        Args:
            llm: LLM provider for all agents
            model: Model to use (defaults to provider's default)
            pubmed_client: Optional PubMed client (for research step)
        """
        self._llm = llm
        self._model = model
        self._pubmed = pubmed_client

        # Initialize agents
        self._researcher = ResearcherAgent(llm, model, pubmed_client)
        self._validator = ValidatorAgent(llm, model)
        self._writer = WriterAgent(llm, model)
        self._editor = EditorAgent(llm, model)
        self._quality = QualityAgent(llm, model)

        self._stats = OrchestratorStats()

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
            # Step 1: Research (or use provided sources)
            if sources:
                logger.info(f"Using {len(sources)} pre-fetched sources")
                current_sources = sources
            else:
                logger.info("Running Researcher agent...")
                research_result = self._researcher.execute(
                    ResearcherInput(
                        procedure_title=input_data.procedure_title,
                        context=input_data.context,
                    )
                )
                self._stats.add_agent_stats("Researcher", research_result.stats)

                if not research_result.output.success:
                    return self._error_output(
                        f"Research failed: {research_result.output.error}"
                    )

                current_sources = research_result.output.sources
                logger.info(f"Found {len(current_sources)} sources")

            # Quality loop
            current_content = ""
            quality_score = 0
            revision_suggestions: list[str] = []

            for iteration in range(1, input_data.max_iterations + 1):
                self._stats.iterations = iteration
                logger.info(f"Iteration {iteration}/{input_data.max_iterations}")

                # Step 2: Write procedure
                logger.info("Running Writer agent...")
                writer_result = self._writer.execute(
                    WriterInput(
                        procedure_title=input_data.procedure_title,
                        context=input_data.context,
                        sources=current_sources,
                        outline=(
                            revision_suggestions if revision_suggestions else None
                        ),
                    )
                )
                self._stats.add_agent_stats(f"Writer_iter{iteration}", writer_result.stats)

                if not writer_result.output.success:
                    return self._error_output(
                        f"Writing failed: {writer_result.output.error}"
                    )

                current_content = writer_result.output.content_markdown
                citations_used = writer_result.output.citations_used

                # Step 3: Validate claims
                logger.info("Running Validator agent...")
                # Extract claims from content (simple: each sentence with citation)
                claims = self._extract_claims(current_content)
                validator_result = self._validator.execute(
                    ValidatorInput(
                        procedure_title=input_data.procedure_title,
                        claims=claims,
                        sources=current_sources,
                    )
                )
                self._stats.add_agent_stats(f"Validator_iter{iteration}", validator_result.stats)

                # Step 4: Edit content
                logger.info("Running Editor agent...")
                editor_result = self._editor.execute(
                    EditorInput(
                        procedure_title=input_data.procedure_title,
                        content_markdown=current_content,
                        sources=current_sources,
                    )
                )
                self._stats.add_agent_stats(f"Editor_iter{iteration}", editor_result.stats)

                if editor_result.output.success:
                    current_content = editor_result.output.edited_content

                # Step 5: Quality check
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

                # Check if we pass threshold
                if quality_result.output.passes_threshold:
                    logger.info("Quality threshold met!")
                    break

                # Prepare for next iteration
                revision_suggestions = quality_result.output.revision_suggestions
                if not revision_suggestions:
                    revision_suggestions = ["Forbedre overordnet kvalitet"]

                logger.info(f"Quality below threshold, revising with {len(revision_suggestions)} suggestions")

            # Calculate final stats
            self._stats.execution_time_seconds = time.time() - start_time

            return PipelineOutput(
                success=True,
                procedure_markdown=current_content,
                sources=current_sources,
                quality_score=quality_score,
                iterations_used=self._stats.iterations,
                total_input_tokens=self._stats.total_input_tokens,
                total_output_tokens=self._stats.total_output_tokens,
                total_cost_usd=self._stats.total_cost_usd,
            )

        except Exception as e:
            logger.exception(f"Pipeline failed: {e}")
            return self._error_output(str(e))

    def _extract_claims(self, content: str) -> list[str]:
        """Extract factual claims from content (sentences with citations)."""
        import re

        claims = []
        # Split into sentences
        sentences = re.split(r"(?<=[.!?])\s+", content)

        for sentence in sentences:
            # Include sentences that have citations
            if re.search(r"\[[a-zA-Z0-9_-]+\]", sentence):
                # Clean up the sentence
                clean = sentence.strip()
                if len(clean) > 20:  # Skip very short fragments
                    claims.append(clean)

        return claims[:20]  # Limit to 20 claims to avoid token bloat

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
