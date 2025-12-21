"""Scopus/EMBASE search integration.

Scopus is Elsevier's abstract and citation database that includes:
- EMBASE (biomedical and pharmacological)
- MEDLINE (overlaps with PubMed)
- Unique content not in PubMed

EMBASE is particularly strong for:
- European literature
- Drug/pharmacology content
- Conference abstracts
- Non-English publications

API Documentation: https://dev.elsevier.com/documentation/ScopusSearchAPI.wadl
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Protocol

from procedurewriter.db import get_secret

logger = logging.getLogger(__name__)


class ScopusSearchError(Exception):
    """Raised when Scopus search fails."""
    pass


@dataclass(frozen=True)
class ScopusArticle:
    """Represents an article from Scopus/EMBASE."""

    scopus_id: str
    title: str
    abstract: str | None
    authors: list[str]
    journal: str | None
    year: int | None
    doi: str | None
    pmid: str | None  # Some Scopus records have PubMed IDs
    document_type: str | None  # Article, Review, Conference Paper, etc.
    source_type: str  # "scopus" or "embase"
    citation_count: int | None


class HttpClientProtocol(Protocol):
    """Protocol for HTTP clients."""

    def get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        ...


class ScopusClient:
    """Client for Elsevier Scopus Search API.

    Provides access to EMBASE content through Scopus search.
    """

    BASE_URL = "https://api.elsevier.com/content/search/scopus"

    def __init__(
        self,
        http: HttpClientProtocol | None = None,
        api_key: str | None = None,
        db_path: str | None = None,
    ) -> None:
        """Initialize Scopus client.

        Args:
            http: HTTP client for making requests
            api_key: Elsevier API key (or fetched from DB/env)
            db_path: Path to database for fetching stored key
        """
        self._http = http
        self._api_key = (
            api_key
            or os.environ.get("ELSEVIER_API_KEY")
            or os.environ.get("SCOPUS_API_KEY")
        )

        # Try to get from database if not provided
        if not self._api_key and db_path:
            self._api_key = get_secret(db_path, name="elsevier_api_key")

    @property
    def is_available(self) -> bool:
        """Check if Scopus search is available."""
        return bool(self._http and self._api_key)

    def search(
        self,
        query: str,
        *,
        max_results: int = 25,
        start: int = 0,
        sort: str = "-citedby-count",  # Most cited first
        subj_areas: list[str] | None = None,
        doc_types: list[str] | None = None,
        date_range: tuple[int, int] | None = None,
    ) -> list[ScopusArticle]:
        """Search Scopus for articles.

        Args:
            query: Search query (Scopus syntax)
            max_results: Maximum results to return
            start: Starting index for pagination
            sort: Sort order (e.g., "-citedby-count", "-pubyear")
            subj_areas: Subject area codes (e.g., ["MEDI", "PHAR"])
            doc_types: Document types (e.g., ["ar", "re"] for articles, reviews)
            date_range: Year range tuple (start_year, end_year)

        Returns:
            List of ScopusArticle objects
        """
        if not self.is_available:
            logger.warning("Scopus client not available (missing HTTP client or API key)")
            return []

        # Build query with filters
        full_query = self._build_query(query, subj_areas, doc_types, date_range)

        params = {
            "query": full_query,
            "count": str(min(max_results, 25)),  # API max is 25 per request
            "start": str(start),
            "sort": sort,
            "view": "COMPLETE",  # Get full metadata
        }

        headers = {
            "X-ELS-APIKey": self._api_key,
            "Accept": "application/json",
        }

        try:
            response = self._http.get(self.BASE_URL, params=params, headers=headers)

            if response.status_code == 401:
                logger.error("Scopus API key invalid or unauthorized")
                return []
            if response.status_code == 429:
                logger.warning("Scopus API rate limit exceeded")
                return []
            if response.status_code != 200:
                logger.warning(f"Scopus API returned {response.status_code}")
                return []

            data = response.json()
            return self._parse_results(data)

        except Exception as e:
            logger.error(f"Scopus search failed: {e}")
            return []

    def search_systematic_reviews(
        self,
        topic: str,
        max_results: int = 15,
    ) -> list[ScopusArticle]:
        """Search specifically for systematic reviews and meta-analyses.

        Args:
            topic: Medical topic to search
            max_results: Maximum results

        Returns:
            List of systematic review articles
        """
        # Scopus query for systematic reviews
        query = (
            f'TITLE-ABS-KEY("{topic}") AND '
            f'(TITLE("systematic review") OR TITLE("meta-analysis") OR '
            f'DOCTYPE("re"))  AND SUBJAREA(MEDI OR PHAR OR HEAL)'
        )

        return self.search(
            query,
            max_results=max_results,
            doc_types=["re"],  # Reviews
            date_range=(2015, 2026),  # Recent reviews
        )

    def search_clinical_trials(
        self,
        topic: str,
        max_results: int = 20,
    ) -> list[ScopusArticle]:
        """Search for randomized controlled trials.

        Args:
            topic: Medical topic to search
            max_results: Maximum results

        Returns:
            List of RCT articles
        """
        query = (
            f'TITLE-ABS-KEY("{topic}") AND '
            f'(TITLE("randomized") OR TITLE("randomised") OR '
            f'TITLE("clinical trial") OR TITLE("RCT")) AND '
            f'SUBJAREA(MEDI OR PHAR OR HEAL)'
        )

        return self.search(
            query,
            max_results=max_results,
            date_range=(2018, 2026),  # Recent trials
        )

    def search_embase_exclusive(
        self,
        topic: str,
        max_results: int = 20,
    ) -> list[ScopusArticle]:
        """Search for EMBASE-exclusive content (not in PubMed).

        EMBASE has ~50% unique content not in PubMed, especially:
        - European publications
        - Conference abstracts
        - Drug/pharmacy literature

        Args:
            topic: Medical topic
            max_results: Maximum results

        Returns:
            Articles likely unique to EMBASE
        """
        # Search EMBASE subject areas, exclude if has PMID
        query = (
            f'TITLE-ABS-KEY("{topic}") AND '
            f'SUBJAREA(PHAR OR HEAL) AND '
            f'NOT PMID(*)'  # Exclude records with PubMed IDs
        )

        return self.search(query, max_results=max_results)

    def _build_query(
        self,
        base_query: str,
        subj_areas: list[str] | None,
        doc_types: list[str] | None,
        date_range: tuple[int, int] | None,
    ) -> str:
        """Build full Scopus query with filters."""
        parts = [base_query]

        if subj_areas:
            areas = " OR ".join(subj_areas)
            parts.append(f"SUBJAREA({areas})")

        if doc_types:
            types = " OR ".join(f'DOCTYPE("{t}")' for t in doc_types)
            parts.append(f"({types})")

        if date_range:
            start_year, end_year = date_range
            parts.append(f"PUBYEAR > {start_year - 1} AND PUBYEAR < {end_year + 1}")

        return " AND ".join(parts)

    def _parse_results(self, data: dict[str, Any]) -> list[ScopusArticle]:
        """Parse Scopus API response into ScopusArticle objects."""
        articles = []

        search_results = data.get("search-results", {})
        entries = search_results.get("entry", [])

        for entry in entries:
            # Skip error entries
            if entry.get("error"):
                continue

            try:
                # Extract authors
                authors = []
                author_data = entry.get("author", [])
                if isinstance(author_data, list):
                    for a in author_data[:10]:  # Limit to first 10 authors
                        name = a.get("authname", "")
                        if name:
                            authors.append(name)

                # Extract year
                year = None
                cover_date = entry.get("prism:coverDate", "")
                if cover_date and len(cover_date) >= 4:
                    try:
                        year = int(cover_date[:4])
                    except ValueError:
                        pass

                # Determine if EMBASE-exclusive (no PMID)
                pmid = entry.get("pubmed-id")
                source_type = "scopus" if pmid else "embase"

                article = ScopusArticle(
                    scopus_id=entry.get("dc:identifier", "").replace("SCOPUS_ID:", ""),
                    title=entry.get("dc:title", ""),
                    abstract=entry.get("dc:description"),
                    authors=authors,
                    journal=entry.get("prism:publicationName"),
                    year=year,
                    doi=entry.get("prism:doi"),
                    pmid=pmid,
                    document_type=entry.get("subtypeDescription"),
                    source_type=source_type,
                    citation_count=int(entry.get("citedby-count", 0) or 0),
                )
                articles.append(article)

            except Exception as e:
                logger.warning(f"Failed to parse Scopus entry: {e}")
                continue

        return articles


def create_scopus_client(
    http: HttpClientProtocol | None = None,
    db_path: str | None = None,
) -> ScopusClient:
    """Factory function to create a configured Scopus client.

    Args:
        http: HTTP client
        db_path: Database path for API key lookup

    Returns:
        Configured ScopusClient
    """
    return ScopusClient(http=http, db_path=db_path)
