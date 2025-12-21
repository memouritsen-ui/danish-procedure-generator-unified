"""Stage 02: Retrieve - Fetch sources using expanded search terms.

The Retrieve stage fetches sources from multiple tiers:
1. Danish guideline library (highest priority)
2. International guidelines (NICE, WHO)
3. Systematic reviews (Cochrane, PubMed)
4. Primary research (PubMed general)

Sources are downloaded to run_dir/raw/ for subsequent chunking.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from procedurewriter.pipeline.events import EventType
from procedurewriter.pipeline.stages.base import PipelineStage

if TYPE_CHECKING:
    from procedurewriter.pipeline.events import EventEmitter

logger = logging.getLogger(__name__)


@dataclass
class SourceInfo:
    """Information about a retrieved source.

    This is a simplified version of SourceReference for pipeline use.
    """

    source_id: str
    title: str
    source_type: str
    url: str | None = None
    year: int | str | None = None
    pmid: str | None = None
    doi: str | None = None
    abstract: str | None = None
    authors: list[str] = field(default_factory=list)
    relevance_score: float = 0.5
    evidence_tier: str | None = None
    raw_content_path: Path | None = None


@dataclass
class RetrieveInput:
    """Input for the Retrieve stage."""

    run_id: str
    run_dir: Path
    procedure_title: str
    search_terms: list[str]
    max_sources: int = 20
    emitter: EventEmitter | None = None


@dataclass
class RetrieveOutput:
    """Output from the Retrieve stage."""

    run_id: str
    run_dir: Path
    procedure_title: str
    sources: list[SourceInfo]
    raw_content_dir: Path
    total_sources: int
    search_terms_used: list[str] = field(default_factory=list)


class RetrieveStage(PipelineStage[RetrieveInput, RetrieveOutput]):
    """Stage 02: Retrieve - Fetch sources using search terms."""

    @property
    def name(self) -> str:
        """Return the stage name."""
        return "retrieve"

    def execute(self, input_data: RetrieveInput) -> RetrieveOutput:
        """Execute the retrieve stage.

        Fetches sources using provided search terms, downloads content
        to raw directory, and returns source references.

        Args:
            input_data: Retrieve input containing search terms

        Returns:
            Retrieve output with source list and paths
        """
        # Emit progress event if emitter provided
        if input_data.emitter is not None:
            input_data.emitter.emit(
                EventType.PROGRESS,
                {
                    "message": f"Retrieving sources for {input_data.procedure_title}",
                    "stage": "retrieve",
                },
            )

        # Ensure raw content directory exists
        raw_content_dir = input_data.run_dir / "raw"
        raw_content_dir.mkdir(parents=True, exist_ok=True)

        # Fetch sources using search terms
        sources = self._fetch_sources(
            input_data.search_terms,
            input_data.max_sources,
            raw_content_dir=raw_content_dir,
        )

        logger.info(
            f"Retrieved {len(sources)} sources for '{input_data.procedure_title}'"
        )

        return RetrieveOutput(
            run_id=input_data.run_id,
            run_dir=input_data.run_dir,
            procedure_title=input_data.procedure_title,
            sources=sources,
            raw_content_dir=raw_content_dir,
            total_sources=len(sources),
            search_terms_used=input_data.search_terms,
        )

    def _fetch_sources(
        self,
        search_terms: list[str],
        max_sources: int,
        raw_content_dir: Path | None = None,
    ) -> list[SourceInfo]:
        """Fetch sources from multiple tiers.

        This method can be overridden or mocked for testing.
        In production, it integrates with the ResearcherAgent.

        Args:
            search_terms: List of search terms to use
            max_sources: Maximum number of sources to fetch
            raw_content_dir: Directory to save raw content

        Returns:
            List of SourceInfo objects
        """
        sources: list[SourceInfo] = []

        # Tier 1: Danish guideline library
        danish_sources = self._search_danish_library(search_terms, max_sources // 3)
        sources.extend(danish_sources)

        # Tier 2: PubMed systematic reviews
        if len(sources) < max_sources:
            remaining = max_sources - len(sources)
            pubmed_sources = self._search_pubmed(search_terms, remaining)
            sources.extend(pubmed_sources)

        # Limit to max_sources
        sources = sources[:max_sources]

        # Save raw content if directory provided
        if raw_content_dir is not None:
            for source in sources:
                self._save_source_content(source, raw_content_dir)

        return sources

    def _search_danish_library(
        self, search_terms: list[str], max_results: int
    ) -> list[SourceInfo]:
        """Search local Danish guideline library.

        Args:
            search_terms: Search terms to use
            max_results: Maximum results to return

        Returns:
            List of SourceInfo from Danish library
        """
        sources: list[SourceInfo] = []

        # Default library path
        library_path = Path.home() / "guideline_harvester" / "library"

        if not library_path.exists():
            logger.debug(f"Danish library not found at {library_path}")
            return sources

        try:
            # Build keyword set from search terms
            keywords = set()
            for term in search_terms:
                keywords.update(term.lower().split())

            # Search JSON metadata files
            for json_file in library_path.glob("**/metadata.json"):
                if len(sources) >= max_results:
                    break

                try:
                    import json

                    with open(json_file, encoding="utf-8") as f:
                        meta = json.load(f)

                    title = meta.get("title", "").lower()
                    content = meta.get("content", "").lower()

                    # Check keyword matches
                    matches = sum(1 for kw in keywords if kw in title or kw in content)

                    if matches >= 1:
                        source_id = f"dk_{hashlib.md5(str(json_file).encode()).hexdigest()[:8]}"
                        sources.append(
                            SourceInfo(
                                source_id=source_id,
                                title=meta.get("title", json_file.parent.name),
                                url=f"file://{json_file.parent}",
                                source_type="danish_guideline",
                                evidence_tier="danish_guideline",
                                authors=meta.get("authors", []),
                                abstract=meta.get("abstract", "")[:500],
                                relevance_score=min(0.9, 0.5 + matches * 0.1),
                            )
                        )
                except Exception as e:
                    logger.debug(f"Error reading {json_file}: {e}")

        except Exception as e:
            logger.warning(f"Danish library search error: {e}")

        return sources

    def _search_pubmed(
        self, search_terms: list[str], max_results: int
    ) -> list[SourceInfo]:
        """Search PubMed for systematic reviews and guidelines.

        Args:
            search_terms: Search terms to use
            max_results: Maximum results to return

        Returns:
            List of SourceInfo from PubMed
        """
        sources: list[SourceInfo] = []

        try:
            from procedurewriter.pipeline.pubmed import PubMedClient
            from procedurewriter.pipeline.fetcher import CachedHttpClient

            # Create clients
            cache_dir = Path.home() / ".cache" / "procedurewriter"
            cache_dir.mkdir(parents=True, exist_ok=True)
            http_client = CachedHttpClient(cache_dir=cache_dir)
            pubmed = PubMedClient(http_client)

            # Search with systematic review filter
            for term in search_terms[:2]:
                if len(sources) >= max_results:
                    break

                query = f"{term} AND (systematic review[pt] OR guideline[pt])"
                pmids, _ = pubmed.search(query, retmax=max_results)

                if pmids:
                    articles = pubmed.fetch_articles(pmids)
                    for article in articles:
                        if len(sources) >= max_results:
                            break

                        sources.append(
                            SourceInfo(
                                source_id=f"pm_{article.get('pmid', '')}",
                                title=article.get("title", ""),
                                pmid=article.get("pmid"),
                                doi=article.get("doi"),
                                url=f"https://pubmed.ncbi.nlm.nih.gov/{article.get('pmid', '')}/",
                                source_type="systematic_review",
                                evidence_tier="systematic_review",
                                authors=article.get("authors", []),
                                abstract=article.get("abstract", ""),
                                year=article.get("year"),
                                relevance_score=0.7,
                            )
                        )

        except ImportError:
            logger.debug("PubMed client not available")
        except Exception as e:
            logger.warning(f"PubMed search error: {e}")

        return sources

    def _save_source_content(self, source: SourceInfo, raw_dir: Path) -> None:
        """Save source content to raw directory.

        Args:
            source: Source to save
            raw_dir: Directory to save to
        """
        try:
            # Create a file for the source metadata
            source_file = raw_dir / f"{source.source_id}.json"

            import json

            content = {
                "source_id": source.source_id,
                "title": source.title,
                "url": source.url,
                "source_type": source.source_type,
                "pmid": source.pmid,
                "doi": source.doi,
                "abstract": source.abstract,
                "authors": source.authors,
                "year": source.year,
            }

            with open(source_file, "w", encoding="utf-8") as f:
                json.dump(content, f, indent=2, ensure_ascii=False)

            source.raw_content_path = source_file

        except Exception as e:
            logger.warning(f"Error saving source {source.source_id}: {e}")
