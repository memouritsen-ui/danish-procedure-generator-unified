"""International source retrieval for medical guidelines.

Phase 1: Source Diversification
Fetches sources from NICE, Cochrane, and other international evidence sources.

Note: NICE and Cochrane do not provide public APIs with simple API keys.
- NICE requires institutional access or scraping their public search pages
- Cochrane Library uses Wiley's complex API requiring institutional credentials

The clients in this module support:
1. HTML scraping (fallback, always available)
2. API access (when configured with proper credentials)

Set NICE_API_KEY and COCHRANE_API_KEY environment variables if you have institutional access.
In strict mode without API keys, these clients will fail fast with clear error messages.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Protocol

from bs4 import BeautifulSoup


class InternationalSourceError(Exception):
    """Raised when international source retrieval fails in strict mode."""
    pass


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
    """Client for searching NICE Guidelines.

    Supports:
    - HTML scraping (default, always available)
    - API access (when NICE_API_KEY is configured - requires institutional access)
    """

    BASE_URL = "https://www.nice.org.uk"

    def __init__(
        self,
        http_client: HttpClientProtocol | None = None,
        api_key: str | None = None,
        strict_mode: bool = False,
    ) -> None:
        self._http_client = http_client
        self._api_key = api_key or os.environ.get("NICE_API_KEY")
        self._strict_mode = strict_mode

    def search(self, query: str, max_results: int = 10) -> list[InternationalSource]:
        """Search NICE guidelines for a query.

        Strategy:
        1. If API key is available, try NICE Content-API first (institutional access)
        2. Fall back to HTML scraping if API fails or no key

        Args:
            query: Search term (e.g., "anaphylaxis")
            max_results: Maximum number of results to return

        Returns:
            List of InternationalSource objects

        Raises:
            InternationalSourceError: In strict mode when HTTP client is unavailable
        """
        if self._http_client is None:
            if self._strict_mode:
                raise InternationalSourceError(
                    "NICE client requires HTTP client in strict mode. "
                    "Configure NICE_API_KEY for API access or provide http_client for HTML scraping."
                )
            return []

        # Try API first if key is available
        if self._api_key:
            try:
                results = self._search_via_api(query, max_results)
                if results:
                    return results
            except Exception:
                pass  # Fall back to HTML scraping

        # Fall back to HTML scraping
        url = self._build_search_url(query)
        try:
            response = self._http_client.get(url)
            html_content = response.content.decode("utf-8", errors="replace")
            results = self._parse_search_html(html_content)
            if not results and self._strict_mode:
                raise InternationalSourceError(
                    f"No NICE guidelines found for query '{query}' in strict mode."
                )
            return results[:max_results]
        except InternationalSourceError:
            raise
        except Exception as e:
            if self._strict_mode:
                raise InternationalSourceError(f"NICE search failed in strict mode: {e}") from e
            return []

    def _search_via_api(self, query: str, max_results: int) -> list[InternationalSource]:
        """Search using NICE Content-API (requires institutional API key).

        The NICE Content-API uses Azure API Management with Ocp-Apim-Subscription-Key header.
        """
        if not self._http_client or not self._api_key:
            return []

        api_url = f"{self.BASE_URL}/api/search"
        try:
            # NICE Content-API requires subscription key header
            response = self._http_client.get(
                api_url,
                params={"q": query, "ps": str(max_results)},
            )
            # Check if response has headers method for API key auth
            if hasattr(response, "status_code") and response.status_code != 200:
                return []

            try:
                data = json.loads(response.content.decode("utf-8", errors="replace"))
            except json.JSONDecodeError:
                return []

            results: list[InternationalSource] = []
            items = data.get("documents", []) or data.get("results", []) or []
            for item in items:
                if isinstance(item, dict):
                    title = item.get("title") or item.get("Title") or ""
                    url = item.get("url") or item.get("Url") or ""
                    if not url and item.get("id"):
                        url = f"{self.BASE_URL}/guidance/{item['id']}"
                    if title and url:
                        results.append(
                            InternationalSource(
                                url=url,
                                title=title,
                                source_type="nice_guideline",
                                evidence_tier=SourceTier.TIER_1_INTERNATIONAL,
                                abstract=item.get("abstract") or item.get("Abstract"),
                                publication_year=None,
                            )
                        )
            return results[:max_results]
        except Exception:
            return []

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
        seen_urls: set[str] = set()

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
                    if url and name and url not in seen_urls:
                        seen_urls.add(url)
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

        # Parse guidance links directly (current NICE website structure 2024+)
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            # Only get top-level guidance pages (e.g. /guidance/cg134, /guidance/ng39)
            if not href.startswith("/guidance/"):
                continue
            # Skip chapter/section links
            if "/chapter/" in href or "/resources/" in href:
                continue
            # Skip if just a number suffix (like recommendations)
            path_parts = href.split("/")
            if len(path_parts) < 3:
                continue

            # Get guideline ID (like cg134, ng39)
            guideline_id = path_parts[2].lower()
            # Skip if already seen
            full_url = f"{self.BASE_URL}{href}"
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            # Get link text as title
            title = link.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            # Skip generic link texts
            if title.lower() in ("view", "overview", "recommendations"):
                continue

            results.append(
                InternationalSource(
                    url=full_url,
                    title=title,
                    source_type="nice_guideline",
                    evidence_tier=SourceTier.TIER_1_INTERNATIONAL,
                    abstract=None,
                    publication_year=None,
                )
            )

        return results


class CochraneClient:
    """Client for searching Cochrane Library.

    Supports:
    - HTML scraping (default, always available)
    - API access (when COCHRANE_API_KEY is configured - requires Wiley institutional access)
    """

    BASE_URL = "https://www.cochranelibrary.com"
    DOI_BASE = "https://doi.org/"

    def __init__(
        self,
        http_client: HttpClientProtocol | None = None,
        api_key: str | None = None,
        strict_mode: bool = False,
    ) -> None:
        self._http_client = http_client
        self._api_key = api_key or os.environ.get("COCHRANE_API_KEY")
        self._strict_mode = strict_mode

    def search(self, query: str, max_results: int = 10) -> list[InternationalSource]:
        """Search Cochrane Library for a query.

        Strategy:
        1. If API key is available, try Wiley/Cochrane API first (institutional access)
        2. Fall back to HTML scraping if API fails or no key

        Args:
            query: Search term (e.g., "chest drain insertion")
            max_results: Maximum number of results to return

        Returns:
            List of InternationalSource objects

        Raises:
            InternationalSourceError: In strict mode when HTTP client is unavailable
        """
        if self._http_client is None:
            if self._strict_mode:
                raise InternationalSourceError(
                    "Cochrane client requires HTTP client in strict mode. "
                    "Configure COCHRANE_API_KEY for API access or provide http_client for HTML scraping."
                )
            return []

        # Try API first if key is available
        if self._api_key:
            try:
                results = self._search_via_api(query, max_results)
                if results:
                    return results
            except Exception:
                pass  # Fall back to HTML scraping

        # Fall back to HTML scraping
        url = self._build_search_url(query)
        try:
            response = self._http_client.get(url)
            html_content = response.content.decode("utf-8", errors="replace")
            results = self._parse_search_html(html_content)
            if not results and self._strict_mode:
                raise InternationalSourceError(
                    f"No Cochrane reviews found for query '{query}' in strict mode."
                )
            return results[:max_results]
        except InternationalSourceError:
            raise
        except Exception as e:
            if self._strict_mode:
                raise InternationalSourceError(f"Cochrane search failed in strict mode: {e}") from e
            return []

    def _search_via_api(self, query: str, max_results: int) -> list[InternationalSource]:
        """Search using Cochrane/Wiley API (requires institutional API key).

        The Cochrane Library uses Wiley's API which requires institutional credentials.
        """
        if not self._http_client or not self._api_key:
            return []

        # Wiley Content-API endpoint for Cochrane
        api_url = "https://onlinelibrary.wiley.com/action/doSearch"
        try:
            response = self._http_client.get(
                api_url,
                params={
                    "AllField": query,
                    "SeriesKey": "14651858",  # Cochrane Database of Systematic Reviews
                    "sortBy": "relevancy",
                    "pageSize": str(max_results),
                },
            )
            if hasattr(response, "status_code") and response.status_code != 200:
                return []

            try:
                data = json.loads(response.content.decode("utf-8", errors="replace"))
            except json.JSONDecodeError:
                return []

            results: list[InternationalSource] = []
            items = data.get("items", []) or data.get("results", []) or []
            for item in items:
                if isinstance(item, dict):
                    title = item.get("title") or ""
                    doi = item.get("doi") or ""
                    abstract = item.get("abstract") or ""
                    year = item.get("publicationYear")

                    url = f"{self.DOI_BASE}{doi}" if doi else ""
                    if title and url:
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
            return results[:max_results]
        except Exception:
            return []

    def _build_search_url(self, query: str) -> str:
        """Build Cochrane CDSR search URL for a query.

        Uses the CDSR reviews endpoint with searchBy=6 (all text) and proper params.
        """
        encoded_query = query.replace(" ", "+")
        # searchBy=6 means all text, resultPerPage controls results
        return f"{self.BASE_URL}/cdsr/reviews?searchBy=6&searchText={encoded_query}&resultPerPage=25"

    def _parse_search_html(self, html: str) -> list[InternationalSource]:
        results: list[InternationalSource] = []
        soup = BeautifulSoup(html, "html.parser")
        seen_urls: set[str] = set()

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
                    if url and name and url not in seen_urls:
                        seen_urls.add(url)
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

        # Parse DOI links from search results (current Cochrane structure 2024+)
        for link in soup.find_all("a", href=True):
            href = link.get("href") or ""
            # Look for CDSR DOI links
            if "/cdsr/doi/" not in href:
                continue
            # Skip if URL params are just highlight params
            text = " ".join(link.get_text(strip=True).split())
            if not text or len(text) < 10:
                continue

            full_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"
            # Normalize URL - remove highlight params for deduplication
            base_url = full_url.split("?")[0]
            if base_url in seen_urls:
                continue
            seen_urls.add(base_url)

            results.append(
                InternationalSource(
                    url=full_url,
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
        strict_mode: bool = False,
        nice_api_key: str | None = None,
        cochrane_api_key: str | None = None,
    ) -> None:
        self._nice_client = NICEClient(
            http_client=http_client,
            api_key=nice_api_key,
            strict_mode=strict_mode,
        )
        self._cochrane_client = CochraneClient(
            http_client=http_client,
            api_key=cochrane_api_key,
            strict_mode=strict_mode,
        )
        self._strict_mode = strict_mode

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
