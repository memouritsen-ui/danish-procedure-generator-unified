"""
Researcher Agent - Searches PubMed and ranks sources.

Responsible for:
1. Generating effective search terms from procedure title
2. Querying PubMed via NCBI API
3. Ranking and filtering sources by relevance
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from procedurewriter.agents.base import AgentResult, BaseAgent
from procedurewriter.agents.models import ResearcherInput, ResearcherOutput, SourceReference

if TYPE_CHECKING:
    from procedurewriter.llm.providers import LLMProvider


SYSTEM_PROMPT = """You are a medical research assistant specializing in Danish emergency medicine procedures.

Your task is to generate effective PubMed search terms for finding authoritative sources on a medical procedure.

Guidelines:
1. Generate 3-5 search terms, from broad to specific
2. Include MeSH terms when applicable
3. Prioritize Danish/Scandinavian guidelines when relevant
4. Focus on emergency medicine, acute care, clinical procedures

Output format: JSON array of search terms
Example: ["anaphylaxis treatment", "epinephrine anaphylaxis emergency", "anaphylaxis guidelines 2023"]"""


RANKING_PROMPT = """You are evaluating PubMed search results for relevance to a medical procedure.

Procedure: {procedure}

For each source, assign a relevance score from 0.0 to 1.0:
- 1.0: Directly addresses the procedure, recent guideline, high-quality evidence
- 0.7-0.9: Highly relevant, good evidence level
- 0.4-0.6: Moderately relevant, useful background
- 0.1-0.3: Tangentially relevant
- 0.0: Not relevant

Sources to evaluate:
{sources}

Output format: JSON array with source_id and relevance_score for each source.
Example: [{{"source_id": "src_123", "relevance_score": 0.85}}, ...]"""


class ResearcherAgent(BaseAgent[ResearcherInput, ResearcherOutput]):
    """Agent that searches PubMed and ranks sources for procedure generation."""

    @property
    def name(self) -> str:
        return "Researcher"

    def __init__(
        self,
        llm: LLMProvider,
        model: str | None = None,
        pubmed_client: object | None = None,
    ):
        """
        Initialize the researcher agent.

        Args:
            llm: LLM provider for search term generation and ranking
            model: Model to use
            pubmed_client: Optional PubMed client for testing
        """
        super().__init__(llm, model)
        self._pubmed = pubmed_client

    def execute(self, input_data: ResearcherInput) -> AgentResult[ResearcherOutput]:
        """
        Search for and rank relevant sources.

        Args:
            input_data: Contains procedure title and search parameters

        Returns:
            AgentResult with ranked sources
        """
        self.reset_stats()

        try:
            # Step 1: Generate search terms (or use provided)
            if input_data.search_terms:
                search_terms = input_data.search_terms
            else:
                search_terms = self._generate_search_terms(input_data.procedure_title)

            # Step 2: Search PubMed
            sources = self._search_pubmed(search_terms, input_data.max_sources)

            # Step 3: Rank sources by relevance
            if sources:
                sources = self._rank_sources(input_data.procedure_title, sources)

            output = ResearcherOutput(
                success=True,
                sources=sources,
                search_terms_used=search_terms,
                total_results_found=len(sources),
            )

        except Exception as e:
            output = ResearcherOutput(
                success=False,
                error=str(e),
                sources=[],
                search_terms_used=[],
                total_results_found=0,
            )

        return AgentResult(output=output, stats=self.get_stats())

    def _generate_search_terms(self, procedure_title: str) -> list[str]:
        """Generate PubMed search terms using LLM."""
        response = self.llm_call(
            messages=[
                self._make_system_message(SYSTEM_PROMPT),
                self._make_user_message(f"Generate search terms for: {procedure_title}"),
            ],
            temperature=0.3,
            max_tokens=200,
        )

        # Parse JSON array from response
        try:
            # Extract JSON from response (handle markdown code blocks)
            content = response.content.strip()
            if "```" in content:
                match = re.search(r"\[.*?\]", content, re.DOTALL)
                if match:
                    content = match.group()
            terms = json.loads(content)
            if isinstance(terms, list):
                return [str(t) for t in terms[:5]]
        except (json.JSONDecodeError, TypeError):
            pass

        # Fallback: use procedure title as search term
        return [procedure_title]

    def _search_pubmed(
        self, search_terms: list[str], max_results: int
    ) -> list[SourceReference]:
        """Search PubMed and return sources."""
        # NOTE: In production, this would call the actual PubMed client
        # For now, return empty list - integration point for pipeline
        if self._pubmed is not None:
            # Use injected client for testing
            return self._pubmed.search(search_terms, max_results)  # type: ignore

        # Placeholder for pipeline integration
        # The orchestrator will inject real PubMed results
        return []

    def _rank_sources(
        self, procedure: str, sources: list[SourceReference]
    ) -> list[SourceReference]:
        """Rank sources by relevance using LLM."""
        if not sources:
            return sources

        # Format sources for LLM
        sources_text = "\n".join(
            f"- {s.source_id}: {s.title} ({s.year or 'n/a'})"
            for s in sources
        )

        response = self.llm_call(
            messages=[
                self._make_system_message("You are a medical research assistant."),
                self._make_user_message(
                    RANKING_PROMPT.format(procedure=procedure, sources=sources_text)
                ),
            ],
            temperature=0.1,
            max_tokens=500,
        )

        # Parse rankings and update sources
        try:
            content = response.content.strip()
            if "```" in content:
                match = re.search(r"\[.*?\]", content, re.DOTALL)
                if match:
                    content = match.group()
            rankings = json.loads(content)

            # Create mapping of source_id to score
            scores = {r["source_id"]: r["relevance_score"] for r in rankings}

            # Update and sort sources
            for source in sources:
                if source.source_id in scores:
                    source.relevance_score = scores[source.source_id]

            sources.sort(key=lambda s: s.relevance_score, reverse=True)

        except (json.JSONDecodeError, KeyError, TypeError):
            # Keep original order if parsing fails
            pass

        return sources
