"""International source retrieval for medical guidelines.

Phase 1: Source Diversification
Fetches sources from NICE, Cochrane, and other international evidence sources.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Protocol

from bs4 import BeautifulSoup


class SourceTier(IntEnum):
    """Evidence tier hierarchy for source prioritization.

    Lower tier = higher priority.
    """

    TIER_1_INTERNATIONAL = 1  # NICE, WHO, Cochrane
    TIER_2_ACADEMIC = 2  # PubMed systematic reviews, RCTs
    TIER_3_TECHNIQUE = 3  # Medscape, StatPearls
    TIER_4_DANISH = 4  # Danish regional guidelines


@dataclass(frozen=True)
class InternationalSource:
    """Represents a source from international medical literature."""

    url: str
    title: str
    source_type: str  # e.g., "nice_guideline", "cochrane_review"
    evidence_tier: int

    # Optional fields
    abstract: str | None = None
    publication_year: int | None = None


class HttpClientProtocol(Protocol):
    """Protocol for HTTP clients (allows dependency injection for testing)."""

    def get(self, url: str, *, params: dict[str, Any] | None = None) -> Any:
        """Perform HTTP GET request."""
        ...


class NICEClient:
    """Client for searching NICE Guidelines."""

    BASE_URL = "https://www.nice.org.uk"

    def __init__(self, http_client: HttpClientProtocol | None = None) -> None:
        self._http_client = http_client

    def search(self, query: str, max_results: int = 10) -> list[InternationalSource]:
        """Search NICE guidelines for a query.

        Args:
            query: Search term (e.g., "anaphylaxis")
            max_results: Maximum number of results to return

        Returns:
            List of InternationalSource objects
        """
        if self._http_client is None:
            return []

        url = self._build_search_url(query)
        response = self._http_client.get(url)
        html_content = response.content.decode("utf-8", errors="replace")
        results = self._parse_search_html(html_content)
        return results[:max_results]

    def _build_search_url(self, query: str) -> str:
        """Build NICE search URL for a query."""
        encoded_query = query.replace(" ", "+")
        return f"{self.BASE_URL}/search?q={encoded_query}"

    def _parse_search_html(self, html: str) -> list[InternationalSource]:
        """Parse NICE search results HTML.

        Args:
            html: Raw HTML content from NICE search page

        Returns:
            List of InternationalSource objects extracted from HTML
        """
        results: list[InternationalSource] = []
        soup = BeautifulSoup(html, "html.parser")

        # Try JSON-LD first (more stable)
        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            try:
                data = json.loads(script.string or "")
            except json.JSONDecodeError:
                continue
            items = data.get("itemListElement") if isinstance(data, dict) else None
            if isinstance(items, list):
                for item in items:
                    url = item.get("url") if isinstance(item, dict) else None
                    name = item.get("name") if isinstance(item, dict) else None
                    if url and name:
                        results.append(
                            InternationalSource(
                                url=url,
                                title=name,
                                source_type="nice_guideline",
                                evidence_tier=SourceTier.TIER_1_INTERNATIONAL,
                                abstract=None,
                                publication_year=None,
                            )
                        )

        if results:
            return results

        # Fallback: regex-based parsing of cards
        article_pattern = re.compile(
            r'<article[^>]*class="card"[^>]*data-url="([^"]*)"[^>]*>.*?'
            r'<a[^>]*>([^<]+)</a>.*?'
            r'Published:\s*(\d{1,2}\s+\w+\s+(\d{4}))'
            r'.*?<p[^>]*class="card__snippet"[^>]*>\s*([^<]+)',
            re.DOTALL | re.IGNORECASE,
        )

        for match in article_pattern.finditer(html):
            url_path = match.group(1).strip()
            title = match.group(2).strip()
            year_str = match.group(4)
            snippet = match.group(5).strip()

            snippet = " ".join(snippet.split())
            try:
                year = int(year_str)
            except ValueError:
                year = None

            full_url = f"{self.BASE_URL}{url_path}" if url_path.startswith("/") else url_path

            results.append(
                InternationalSource(
                    url=full_url,
                    title=title,
                    source_type="nice_guideline",
                    evidence_tier=SourceTier.TIER_1_INTERNATIONAL,
                    abstract=snippet,
                    publication_year=year,
                )
            )

        return results


class CochraneClient:
    """Client for searching Cochrane Library."""

    BASE_URL = "https://www.cochranelibrary.com"
    DOI_BASE = "https://doi.org/"

    def __init__(self, http_client: HttpClientProtocol | None = None) -> None:
        self._http_client = http_client

    def search(self, query: str, max_results: int = 10) -> list[InternationalSource]:
        """Search Cochrane Library for a query.

        Args:
            query: Search term (e.g., "chest drain insertion")
            max_results: Maximum number of results to return

        Returns:
            List of InternationalSource objects
        """
        if self._http_client is None:
            return []

        url = self._build_search_url(query)
        response = self._http_client.get(url)
        html_content = response.content.decode("utf-8", errors="replace")
        results = self._parse_search_html(html_content)
        return results[:max_results]

    def _build_search_url(self, query: str) -> str:
        encoded_query = query.replace(" ", "+")
        return f"{self.BASE_URL}/search?text={encoded_query}"

    def _parse_search_html(self, html: str) -> list[InternationalSource]:
        results: list[InternationalSource] = []
        soup = BeautifulSoup(html, "html.parser")

        # JSON-LD parsing for item lists
        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            try:
                data = json.loads(script.string or "")
            except json.JSONDecodeError:
                continue
            items = data.get("itemListElement") if isinstance(data, dict) else None
            if isinstance(items, list):
                for item in items:
                    url = item.get("url") if isinstance(item, dict) else None
                    name = item.get("name") if isinstance(item, dict) else None
                    if url and name:
                        results.append(
                            InternationalSource(
                                url=url,
                                title=name,
                                source_type="cochrane_review",
                                evidence_tier=SourceTier.TIER_1_INTERNATIONAL,
                                abstract=None,
                                publication_year=None,
                            )
                        )

        if results:
            return results

        # Fallback: parse search result links
        for link in soup.find_all("a", href=True):
            href = link.get("href") or ""
            text = " ".join(link.get_text(strip=True).split())
            if not text:
                continue
            if "/cdsr/" in href and "doi" in href:
                url = href if href.startswith("http") else f"{self.BASE_URL}{href}"
                results.append(
                    InternationalSource(
                        url=url,
                        title=text,
                        source_type="cochrane_review",
                        evidence_tier=SourceTier.TIER_1_INTERNATIONAL,
                    )
                )
        return results

    def _parse_search_response(self, json_str: str) -> list[InternationalSource]:
        """Parse Cochrane search JSON response.

        Args:
            json_str: Raw JSON string from Cochrane API

        Returns:
            List of InternationalSource objects
        """
        results: list[InternationalSource] = []

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return []

        items = data.get("results", [])
        for item in items:
            title = item.get("title", "")
            doi = item.get("doi", "")
            year = item.get("publicationYear")
            abstract = item.get("abstract", "")

            # Build URL from DOI
            url = f"{self.DOI_BASE}{doi}" if doi else ""

            results.append(
                InternationalSource(
                    url=url,
                    title=title,
                    source_type="cochrane_review",
                    evidence_tier=SourceTier.TIER_1_INTERNATIONAL,
                    abstract=abstract if abstract else None,
                    publication_year=year,
                )
            )

        return results


class InternationalSourceAggregator:
    """Aggregates sources from multiple international clients."""

    def __init__(
        self,
        http_client: HttpClientProtocol | None = None,
    ) -> None:
        self._nice_client = NICEClient(http_client=http_client)
        self._cochrane_client = CochraneClient(http_client=http_client)

    def search_all(
        self, query: str, max_per_tier: int = 5
    ) -> list[InternationalSource]:
        """Search all international sources and return sorted by tier.

        Args:
            query: Search term
            max_per_tier: Maximum results per evidence tier

        Returns:
            List of InternationalSource sorted by evidence_tier (1 first)
        """
        all_sources: list[InternationalSource] = []

        # Tier 1: International guidelines
        nice_results = self._nice_client.search(query, max_results=max_per_tier)
        all_sources.extend(nice_results[:max_per_tier])

        cochrane_results = self._cochrane_client.search(query, max_results=max_per_tier)
        all_sources.extend(cochrane_results[:max_per_tier])

        # Sort by evidence tier
        all_sources.sort(key=lambda s: s.evidence_tier)

        return all_sources
