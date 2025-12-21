"""International source retrieval for medical guidelines.

Phase 1: Source Diversification
Fetches sources from NICE, Cochrane, and other international evidence sources.

International discovery uses SerpAPI (Google Scholar) to locate NICE and
Cochrane sources without direct NICE/Cochrane API keys.

SerpAPI requirements:
- Set SERPAPI_API_KEY (or PROCEDUREWRITER_SERPAPI_API_KEY)
- Uses the Google Scholar engine to find NICE/Cochrane URLs

HTML scraping is allowed only when explicitly enabled and not in strict mode.
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

    def get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Perform HTTP GET request."""
        ...


def _extract_year(summary: str | None) -> int | None:
    if not summary:
        return None
    match = re.search(r"\b(19|20)\d{2}\b", summary)
    if not match:
        return None
    try:
        return int(match.group(0))
    except ValueError:
        return None


def _classify_scholar_url(url: str) -> str | None:
    lowered = url.lower()
    if "nice.org.uk" in lowered:
        return "nice_guideline"
    if "cochranelibrary.com" in lowered or "10.1002/14651858" in lowered:
        return "cochrane_review"
    return None


class SerpApiScholarClient:
    """Client for SerpAPI Google Scholar search (NICE + Cochrane discovery)."""

    BASE_URL = "https://serpapi.com/search.json"

    def __init__(
        self,
        http_client: HttpClientProtocol | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        engine: str = "google_scholar",
        strict_mode: bool = False,
    ) -> None:
        self._http_client = http_client
        self._api_key = (
            api_key
            or os.environ.get("SERPAPI_API_KEY")
            or os.environ.get("PROCEDUREWRITER_SERPAPI_API_KEY")
        )
        self._base_url = base_url or self.BASE_URL
        self._engine = engine
        self._strict_mode = strict_mode

    def search(self, query: str, max_results: int = 10) -> list[InternationalSource]:
        if self._http_client is None:
            if self._strict_mode:
                raise InternationalSourceError(
                    "SerpAPI client requires HTTP client in strict mode."
                )
            return []

        if not self._api_key:
            if self._strict_mode:
                raise InternationalSourceError(
                    "SerpAPI key required in strict mode. "
                    "Set SERPAPI_API_KEY or PROCEDUREWRITER_SERPAPI_API_KEY."
                )
            return []

        params = {
            "engine": self._engine,
            "q": query,
            "api_key": self._api_key,
            "num": str(max_results),
        }
        try:
            response = self._http_client.get(self._base_url, params=params)
            if hasattr(response, "status_code") and response.status_code != 200:
                if self._strict_mode:
                    raise InternationalSourceError(
                        f"SerpAPI returned {response.status_code} for query '{query}'."
                    )
                return []

            try:
                data = json.loads(response.content.decode("utf-8", errors="replace"))
            except json.JSONDecodeError:
                if self._strict_mode:
                    raise InternationalSourceError("SerpAPI returned invalid JSON.")
                return []

            results: list[InternationalSource] = []
            for item in data.get("organic_results", []) or []:
                if not isinstance(item, dict):
                    continue
                title = (item.get("title") or "").strip()
                url = (item.get("link") or item.get("link_url") or "").strip()
                if not title or not url:
                    continue
                source_type = _classify_scholar_url(url)
                if not source_type:
                    continue
                summary = None
                publication_info = item.get("publication_info")
                if isinstance(publication_info, dict):
                    summary = publication_info.get("summary")
                abstract = item.get("snippet")
                year = _extract_year(summary) if summary else None
                results.append(
                    InternationalSource(
                        url=url,
                        title=title,
                        source_type=source_type,
                        evidence_tier=SourceTier.TIER_1_INTERNATIONAL,
                        abstract=abstract if abstract else None,
                        publication_year=year,
                    )
                )
            return results[:max_results]
        except InternationalSourceError:
            raise
        except Exception as e:  # noqa: BLE001
            if self._strict_mode:
                raise InternationalSourceError(f"SerpAPI search failed: {e}") from e
            return []


class NICEClient:
    """HTML scraper fallback for NICE Guidelines.

    Used only when allow_html_fallback is enabled and strict_mode is False.
    """

    BASE_URL = "https://www.nice.org.uk"

    def __init__(
        self,
        http_client: HttpClientProtocol | None = None,
        strict_mode: bool = False,
        allow_html_fallback: bool = False,
    ) -> None:
        self._http_client = http_client
        self._strict_mode = strict_mode
        self._allow_html_fallback = allow_html_fallback

    def search(self, query: str, max_results: int = 10) -> list[InternationalSource]:
        """Search NICE guidelines for a query.

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
                    "NICE client requires HTTP client in strict mode."
                )
            return []

        # HTML scraping only if explicitly allowed and not strict
        if not self._allow_html_fallback or self._strict_mode:
            return []

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
    """HTML scraper fallback for Cochrane Library.

    Used only when allow_html_fallback is enabled and strict_mode is False.
    """

    BASE_URL = "https://www.cochranelibrary.com"
    DOI_BASE = "https://doi.org/"

    def __init__(
        self,
        http_client: HttpClientProtocol | None = None,
        strict_mode: bool = False,
        allow_html_fallback: bool = False,
    ) -> None:
        self._http_client = http_client
        self._strict_mode = strict_mode
        self._allow_html_fallback = allow_html_fallback

    def search(self, query: str, max_results: int = 10) -> list[InternationalSource]:
        """Search Cochrane Library for a query.

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
                    "Cochrane client requires HTTP client in strict mode."
                )
            return []

        # HTML scraping only if explicitly allowed and not strict
        if not self._allow_html_fallback or self._strict_mode:
            return []

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


class InternationalSourceAggregator:
    """Aggregates sources from multiple international clients."""

    def __init__(
        self,
        http_client: HttpClientProtocol | None = None,
        strict_mode: bool = False,
        serpapi_api_key: str | None = None,
        serpapi_base_url: str | None = None,
        serpapi_engine: str = "google_scholar",
        allow_html_fallback: bool = False,
    ) -> None:
        self._scholar_client = SerpApiScholarClient(
            http_client=http_client,
            api_key=serpapi_api_key,
            base_url=serpapi_base_url,
            engine=serpapi_engine,
            strict_mode=strict_mode,
        )
        # Optional HTML fallback for non-strict runs
        self._nice_client = NICEClient(
            http_client=http_client,
            strict_mode=False,
            allow_html_fallback=allow_html_fallback,
        )
        self._cochrane_client = CochraneClient(
            http_client=http_client,
            strict_mode=False,
            allow_html_fallback=allow_html_fallback,
        )
        self._strict_mode = strict_mode
        self._allow_html_fallback = allow_html_fallback

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
        results, _ = self.search_all_with_stats(query, max_per_tier=max_per_tier)
        return results

    def search_all_with_stats(
        self, query: str, max_per_tier: int = 5
    ) -> tuple[list[InternationalSource], dict[str, int]]:
        """Search all international sources and return results with stats.

        Returns:
            (sources, stats) where stats include per-tier candidate counts.
        """
        all_sources: list[InternationalSource] = []

        # Tier 1: International guidelines
        scholar_results = self._scholar_client.search(query, max_results=max_per_tier * 3)
        nice_results = [r for r in scholar_results if r.source_type == "nice_guideline"]
        cochrane_results = [r for r in scholar_results if r.source_type == "cochrane_review"]

        if self._allow_html_fallback and not self._strict_mode:
            if not nice_results:
                nice_results = self._nice_client.search(query, max_results=max_per_tier)
            if not cochrane_results:
                cochrane_results = self._cochrane_client.search(query, max_results=max_per_tier)

        all_sources.extend(nice_results[:max_per_tier])
        all_sources.extend(cochrane_results[:max_per_tier])

        # Sort by evidence tier
        all_sources.sort(key=lambda s: s.evidence_tier)

        stats = {
            "nice_candidates": len(nice_results),
            "cochrane_candidates": len(cochrane_results),
            "scholar_candidates": len(scholar_results),
        }

        return all_sources, stats
