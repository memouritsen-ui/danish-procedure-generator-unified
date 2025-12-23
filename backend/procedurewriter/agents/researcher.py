"""
Researcher Agent - Active Multi-Source Medical Research.

Implements tiered evidence search strategy:
1. Danish Guidelines (priority 1000) - Local library
2. International Guidelines (NICE, WHO) - Direct API
3. Systematic Reviews (Cochrane, PubMed) - API + SerpAPI
4. Primary Research (PubMed) - NCBI API

Evidence hierarchy follows config/evidence_hierarchy.yaml.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from procedurewriter.agents.base import AgentResult, BaseAgent
from procedurewriter.agents.models import ResearcherInput, ResearcherOutput, SourceReference

# Import provider-specific exceptions with fallbacks
try:
    from openai import APIError as OpenAIError
except ImportError:
    OpenAIError = type(None)  # type: ignore[misc,assignment]

try:
    from anthropic import APIError as AnthropicError
except ImportError:
    AnthropicError = type(None)  # type: ignore[misc,assignment]

try:
    from httpx import HTTPStatusError
except ImportError:
    HTTPStatusError = type(None)  # type: ignore[misc,assignment]

if TYPE_CHECKING:
    from procedurewriter.llm.providers import LLMProvider

logger = logging.getLogger(__name__)

# Evidence tier priorities (from evidence_hierarchy.yaml)
EVIDENCE_TIERS = {
    "danish_guideline": 1000,
    "nordic_guideline": 900,
    "european_guideline": 850,
    "international_guideline": 800,  # NICE, WHO
    "systematic_review": 700,  # Cochrane
    "practice_guideline": 650,
    "rct": 500,
    "observational": 300,
    "case_report": 150,
    "unclassified": 100,
}

SYSTEM_PROMPT = """You are a medical research assistant specializing in Danish emergency medicine procedures.

Your task is to generate effective search terms for finding authoritative sources on a medical procedure.

Guidelines:
1. Generate 5-7 search terms, from broad to specific
2. Include MeSH terms when applicable
3. Prioritize Danish/Scandinavian terminology
4. Focus on emergency medicine, acute care, clinical procedures
5. Include systematic review and guideline filters

Output format: JSON array of search terms
Example: ["anaphylaxis treatment guidelines", "anafylaksi behandling", "epinephrine anaphylaxis systematic review", "anaphylaxis emergency management", "adrenalin anafylaktisk shock"]"""


RANKING_PROMPT = """You are evaluating medical sources for relevance to a procedure.

Procedure: {procedure}

For each source, assign a relevance score from 0.0 to 1.0:
- 1.0: Directly addresses the procedure, recent guideline, high-quality evidence
- 0.7-0.9: Highly relevant, good evidence level
- 0.4-0.6: Moderately relevant, useful background
- 0.1-0.3: Tangentially relevant
- 0.0: Not relevant

Consider:
- How directly does it address the procedure?
- Is it from a recognized authority (Danish health board, NICE, Cochrane)?
- Is it recent (guidelines within 5 years)?
- Is it evidence level appropriate (systematic reviews > RCTs > observational)?

Sources to evaluate:
{sources}

Output format: JSON array with source_id and relevance_score for each source.
Example: [{{"source_id": "src_123", "relevance_score": 0.85}}, ...]"""


class ResearcherAgent(BaseAgent[ResearcherInput, ResearcherOutput]):
    """
    Agent that actively searches multiple sources for procedure evidence.

    Implements tiered search strategy:
    1. Danish guideline library (highest priority)
    2. International guidelines (NICE API)
    3. Systematic reviews (PubMed + Cochrane)
    4. Primary research (PubMed general)

    Each tier is searched in sequence. Higher-tier sources get priority
    scores based on evidence_hierarchy.yaml.
    """

    @property
    def name(self) -> str:
        return "Researcher"

    def __init__(
        self,
        llm: LLMProvider,
        model: str | None = None,
        pubmed_client: object | None = None,
        http_client: object | None = None,
        library_path: Path | str | None = None,
        serpapi_key: str | None = None,
    ):
        """
        Initialize the researcher agent with real search clients.

        Args:
            llm: LLM provider for search term generation and ranking
            model: Model to use for LLM calls
            pubmed_client: PubMed client (created lazily if not provided)
            http_client: HTTP client for API calls (created lazily if not provided)
            library_path: Path to Danish guideline library
            serpapi_key: SerpAPI key for Cochrane/Google Scholar
        """
        super().__init__(llm, model)

        # Store injected clients (or None for lazy creation)
        self._http = http_client
        self._pubmed = pubmed_client

        # Danish guideline library path
        self._library_path = Path(library_path) if library_path else Path.home() / "guideline_harvester" / "library"

        # SerpAPI key for Cochrane searches
        self._serpapi_key = serpapi_key

        logger.info(f"ResearcherAgent initialized with library at {self._library_path}")

    def _get_http_client(self) -> Any:
        """Get or create HTTP client lazily."""
        if self._http is None:
            from procedurewriter.pipeline.fetcher import CachedHttpClient
            from procedurewriter.settings import settings
            cache_dir = Path(settings.cache_dir) if hasattr(settings, 'cache_dir') else Path.home() / ".cache" / "procedurewriter"
            cache_dir.mkdir(parents=True, exist_ok=True)
            self._http = CachedHttpClient(cache_dir=cache_dir)
        return self._http

    def _get_pubmed_client(self) -> Any:
        """Get or create PubMed client lazily."""
        if self._pubmed is None:
            from procedurewriter.pipeline.pubmed import PubMedClient
            self._pubmed = PubMedClient(self._get_http_client())
        return self._pubmed

    def execute(self, input_data: ResearcherInput) -> AgentResult[ResearcherOutput]:
        """
        Execute tiered evidence search strategy.

        Args:
            input_data: Contains procedure title and search parameters

        Returns:
            AgentResult with ranked sources from multiple tiers
        """
        self.reset_stats()
        all_sources: list[SourceReference] = []

        try:
            # Step 1: Generate search terms
            if input_data.search_terms:
                search_terms = input_data.search_terms
            else:
                search_terms = self._generate_search_terms(input_data.procedure_title)

            logger.info(f"Searching for: {input_data.procedure_title}")
            logger.info(f"Search terms: {search_terms}")

            # Step 2: Tiered search strategy
            # Tier 1: Danish guideline library (priority 1000)
            danish_sources = self._search_danish_library(
                input_data.procedure_title,
                search_terms
            )
            for src in danish_sources:
                src.evidence_tier = "danish_guideline"
            all_sources.extend(danish_sources)
            logger.info(f"Danish library: {len(danish_sources)} sources")

            # Tier 2: NICE guidelines (priority 800)
            nice_sources = self._search_nice_api(search_terms)
            for src in nice_sources:
                src.evidence_tier = "international_guideline"
            all_sources.extend(nice_sources)
            logger.info(f"NICE API: {len(nice_sources)} sources")

            # Tier 3: PubMed systematic reviews (priority 700)
            systematic_sources = self._search_pubmed_systematic(
                search_terms,
                max_results=input_data.max_sources // 3
            )
            for src in systematic_sources:
                src.evidence_tier = "systematic_review"
            all_sources.extend(systematic_sources)
            logger.info(f"PubMed systematic: {len(systematic_sources)} sources")

            # Tier 4: Cochrane reviews via SerpAPI (priority 700)
            if self._serpapi_key:
                cochrane_sources = self._search_cochrane(
                    search_terms,
                    max_results=5
                )
                for src in cochrane_sources:
                    src.evidence_tier = "systematic_review"
                all_sources.extend(cochrane_sources)
                logger.info(f"Cochrane: {len(cochrane_sources)} sources")

            # Tier 5: PubMed general search (priority varies)
            if len(all_sources) < input_data.max_sources:
                remaining = input_data.max_sources - len(all_sources)
                general_sources = self._search_pubmed_general(
                    search_terms,
                    max_results=remaining
                )
                all_sources.extend(general_sources)
                logger.info(f"PubMed general: {len(general_sources)} sources")

            # Step 3: Rank all sources by relevance
            if all_sources:
                all_sources = self._rank_sources(input_data.procedure_title, all_sources)

            # Step 4: Apply evidence tier priorities
            all_sources = self._apply_tier_priorities(all_sources)

            # Limit to max_sources
            all_sources = all_sources[:input_data.max_sources]

            output = ResearcherOutput(
                success=True,
                sources=all_sources,
                search_terms_used=search_terms,
                total_results_found=len(all_sources),
            )

            logger.info(f"Research complete: {len(all_sources)} total sources")

        except (OpenAIError, AnthropicError, HTTPStatusError, OSError) as e:
            # LLM API, HTTP, or network errors - return failure output
            logger.error(f"Research failed with LLM/network error: {e}")
            output = ResearcherOutput(
                success=False,
                error=str(e),
                sources=[],
                search_terms_used=search_terms if 'search_terms' in locals() else [],
                total_results_found=0,
            )
        except Exception as e:
            # Unexpected error - log and re-raise to expose bugs
            logger.exception(f"Unexpected error during research: {e}")
            raise

        return AgentResult(output=output, stats=self.get_stats())

    def _generate_search_terms(self, procedure_title: str) -> list[str]:
        """Generate search terms using LLM for multi-source search."""
        # GPT-5.x models may use reasoning tokens - set generous limit
        response = self.llm_call(
            messages=[
                self._make_system_message(SYSTEM_PROMPT),
                self._make_user_message(f"Generate search terms for: {procedure_title}"),
            ],
            temperature=0.3,
            max_tokens=4000,
        )

        try:
            content = response.content.strip()
            if "```" in content:
                match = re.search(r"\[.*?\]", content, re.DOTALL)
                if match:
                    content = match.group()
            terms = json.loads(content)
            if isinstance(terms, list):
                return [str(t) for t in terms[:7]]
        except (json.JSONDecodeError, TypeError):
            pass

        # Fallback: generate basic terms from title
        base = procedure_title.lower()
        return [
            procedure_title,
            f"{base} guidelines",
            f"{base} systematic review",
            f"{base} treatment",
        ]

    def _search_danish_library(
        self,
        procedure_title: str,
        search_terms: list[str]
    ) -> list[SourceReference]:
        """
        Search local Danish guideline library.

        The library contains 40k+ Danish medical guidelines at:
        ~/guideline_harvester/library/
        """
        sources: list[SourceReference] = []

        if not self._library_path.exists():
            logger.warning(f"Danish library not found at {self._library_path}")
            return sources

        try:
            # Search metadata files
            metadata_dir = self._library_path / "metadata"
            if not metadata_dir.exists():
                metadata_dir = self._library_path

            # Simple keyword matching in filenames and content
            keywords = set()
            for term in search_terms:
                keywords.update(term.lower().split())
            keywords.add(procedure_title.lower())

            # Search PDF metadata/index files
            for json_file in metadata_dir.glob("*.json"):
                try:
                    with open(json_file, encoding="utf-8") as f:
                        meta = json.load(f)

                    title = meta.get("title", "").lower()
                    content = meta.get("content", "").lower()

                    # Check keyword matches
                    matches = sum(1 for kw in keywords if kw in title or kw in content)
                    if matches >= 2:  # At least 2 keyword matches
                        source = SourceReference(
                            source_id=f"DK_{json_file.stem}",
                            title=meta.get("title", json_file.stem),
                            url=meta.get("url", f"file://{json_file}"),
                            year=meta.get("year"),
                            authors=meta.get("authors", []),
                            abstract=meta.get("abstract", "")[:500],
                            source_type="danish_guideline",
                            relevance_score=min(0.9, 0.5 + matches * 0.1),
                        )
                        sources.append(source)

                except (json.JSONDecodeError, IOError):
                    continue

            # Also search text/html files directly
            for txt_file in list(self._library_path.glob("**/*.txt"))[:100]:
                try:
                    content = txt_file.read_text(encoding="utf-8", errors="ignore")[:2000].lower()
                    matches = sum(1 for kw in keywords if kw in content)
                    if matches >= 2:
                        source = SourceReference(
                            source_id=f"DK_{txt_file.stem[:20]}",
                            title=txt_file.stem.replace("_", " ").title(),
                            url=f"file://{txt_file}",
                            source_type="danish_guideline",
                            relevance_score=0.7,
                        )
                        sources.append(source)
                except IOError:
                    continue

        except (OSError, json.JSONDecodeError, KeyError, HTTPStatusError) as e:
            # File I/O, HTTP, or JSON parsing errors - return partial results
            logger.warning(f"Danish library search error: {e}")

        return sources[:10]  # Limit Danish sources

    def _search_nice_api(self, search_terms: list[str]) -> list[SourceReference]:
        """
        Search NICE Content API directly (free, no SerpAPI needed).

        NICE API: https://api.nice.org.uk/services/search/
        """
        sources: list[SourceReference] = []

        try:
            # Use first 3 search terms
            for term in search_terms[:3]:
                url = "https://api.nice.org.uk/services/search/"
                params = {
                    "q": term,
                    "ps": "5",  # Page size
                    "om": "json",
                }

                response = self._get_http_client().get(url, params=params)
                if response.status_code != 200:
                    continue

                data = response.json()
                results = data.get("results", [])

                for item in results:
                    # Extract NICE guidance info
                    title = item.get("title", "")
                    guid = item.get("guid", "")

                    source = SourceReference(
                        source_id=f"NICE_{guid}",
                        title=title,
                        url=item.get("url", f"https://www.nice.org.uk/guidance/{guid}"),
                        year=item.get("lastModified", "")[:4] if item.get("lastModified") else None,
                        abstract=item.get("description", "")[:500],
                        source_type="international_guideline",
                        relevance_score=0.75,
                    )

                    # Avoid duplicates
                    if not any(s.source_id == source.source_id for s in sources):
                        sources.append(source)

        except (OSError, json.JSONDecodeError, KeyError, TypeError, HTTPStatusError) as e:
            # Network, HTTP, or response parsing errors - return partial results
            logger.warning(f"NICE API search error: {e}")

        return sources[:8]

    def _search_pubmed_systematic(
        self,
        search_terms: list[str],
        max_results: int = 5
    ) -> list[SourceReference]:
        """
        Search PubMed specifically for systematic reviews and meta-analyses.
        """
        sources: list[SourceReference] = []

        try:
            # Add systematic review filter to search
            for term in search_terms[:2]:
                query = f"{term} AND (systematic review[pt] OR meta-analysis[pt])"

                pmids, _ = self._get_pubmed_client().search(query, retmax=max_results)

                if pmids:
                    articles = self._get_pubmed_client().fetch(pmids)

                    for article in articles:
                        source = SourceReference(
                            source_id=f"PMID_{article.get('pmid', '')}",
                            title=article.get("title", ""),
                            url=f"https://pubmed.ncbi.nlm.nih.gov/{article.get('pmid', '')}/",
                            year=article.get("year"),
                            authors=article.get("authors", []),
                            abstract=article.get("abstract", "")[:500],
                            source_type="systematic_review",
                            relevance_score=0.7,
                        )

                        if not any(s.source_id == source.source_id for s in sources):
                            sources.append(source)

        except (OSError, json.JSONDecodeError, KeyError, TypeError, HTTPStatusError) as e:
            # Network, HTTP, or response parsing errors - return partial results
            logger.warning(f"PubMed systematic search error: {e}")

        return sources[:max_results]

    def _search_cochrane(
        self,
        search_terms: list[str],
        max_results: int = 5
    ) -> list[SourceReference]:
        """
        Search Cochrane Library via SerpAPI.
        """
        sources: list[SourceReference] = []

        if not self._serpapi_key:
            return sources

        try:
            for term in search_terms[:2]:
                url = "https://serpapi.com/search"
                params = {
                    "api_key": self._serpapi_key,
                    "engine": "google",
                    "q": f"site:cochranelibrary.com {term}",
                    "num": str(max_results),
                }

                response = self._get_http_client().get(url, params=params)
                if response.status_code != 200:
                    continue

                data = response.json()
                organic = data.get("organic_results", [])

                for item in organic:
                    source = SourceReference(
                        source_id=f"COCHRANE_{hash(item.get('link', '')) % 10000}",
                        title=item.get("title", ""),
                        url=item.get("link", ""),
                        abstract=item.get("snippet", "")[:500],
                        source_type="systematic_review",
                        relevance_score=0.75,
                    )

                    if not any(s.source_id == source.source_id for s in sources):
                        sources.append(source)

        except (OSError, json.JSONDecodeError, KeyError, TypeError, HTTPStatusError) as e:
            # Network, HTTP, or response parsing errors - return partial results
            logger.warning(f"Cochrane search error: {e}")

        return sources[:max_results]

    def _search_pubmed_general(
        self,
        search_terms: list[str],
        max_results: int = 10
    ) -> list[SourceReference]:
        """
        General PubMed search for primary research.
        """
        sources: list[SourceReference] = []

        try:
            for term in search_terms[:3]:
                pmids, _ = self._get_pubmed_client().search(term, retmax=max_results // 2)

                if pmids:
                    articles = self._get_pubmed_client().fetch(pmids)

                    for article in articles:
                        # Classify evidence tier based on publication type
                        pub_types = article.get("publication_types", [])
                        source_type = self._classify_publication_type(pub_types)

                        source = SourceReference(
                            source_id=f"PMID_{article.get('pmid', '')}",
                            title=article.get("title", ""),
                            url=f"https://pubmed.ncbi.nlm.nih.gov/{article.get('pmid', '')}/",
                            year=article.get("year"),
                            authors=article.get("authors", []),
                            abstract=article.get("abstract", "")[:500],
                            source_type=source_type,
                            relevance_score=0.5,
                        )

                        if not any(s.source_id == source.source_id for s in sources):
                            sources.append(source)

        except (OSError, json.JSONDecodeError, KeyError, TypeError, HTTPStatusError) as e:
            # Network, HTTP, or response parsing errors - return partial results
            logger.warning(f"PubMed general search error: {e}")

        return sources[:max_results]

    def _classify_publication_type(self, pub_types: list[str]) -> str:
        """Classify publication into evidence tier based on PubMed publication types."""
        pub_types_lower = [pt.lower() for pt in pub_types]

        if any("meta-analysis" in pt or "systematic review" in pt for pt in pub_types_lower):
            return "systematic_review"
        elif any("guideline" in pt or "practice guideline" in pt for pt in pub_types_lower):
            return "practice_guideline"
        elif any("randomized controlled" in pt or "clinical trial" in pt for pt in pub_types_lower):
            return "rct"
        elif any("cohort" in pt or "observational" in pt or "case-control" in pt for pt in pub_types_lower):
            return "observational"
        elif any("case report" in pt for pt in pub_types_lower):
            return "case_report"
        else:
            return "unclassified"

    def _rank_sources(
        self,
        procedure: str,
        sources: list[SourceReference]
    ) -> list[SourceReference]:
        """Rank sources by relevance using LLM."""
        if not sources:
            return sources

        # Format sources for LLM
        sources_text = "\n".join(
            f"- {s.source_id}: {s.title} ({s.year or 'n/a'}) [{s.source_type}]"
            for s in sources
        )

        response = self.llm_call(
            messages=[
                self._make_system_message("You are a medical research assistant evaluating source relevance."),
                self._make_user_message(
                    RANKING_PROMPT.format(procedure=procedure, sources=sources_text)
                ),
            ],
            temperature=0.1,
            max_tokens=16000,  # GPT-5.x may use reasoning tokens
        )

        try:
            content = response.content.strip()
            if "```" in content:
                match = re.search(r"\[.*?\]", content, re.DOTALL)
                if match:
                    content = match.group()
            rankings = json.loads(content)

            # Update scores
            scores = {r["source_id"]: r["relevance_score"] for r in rankings}
            for source in sources:
                if source.source_id in scores:
                    source.relevance_score = scores[source.source_id]

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Ranking parse error: {e}")

        return sources

    def _apply_tier_priorities(
        self,
        sources: list[SourceReference]
    ) -> list[SourceReference]:
        """
        Apply evidence tier priorities to final ranking.

        Combines LLM relevance score with evidence tier priority.
        """
        for source in sources:
            tier = source.evidence_tier or source.source_type or "unclassified"
            tier_priority = EVIDENCE_TIERS.get(tier, 100)

            # Combined score: 60% relevance, 40% tier priority
            # Normalize tier priority to 0-1 range
            normalized_priority = tier_priority / 1000

            combined_score = (
                0.6 * source.relevance_score +
                0.4 * normalized_priority
            )
            source.relevance_score = combined_score

        # Sort by combined score
        sources.sort(key=lambda s: s.relevance_score, reverse=True)

        return sources
