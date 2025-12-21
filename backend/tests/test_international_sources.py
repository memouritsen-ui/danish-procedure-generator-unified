"""Tests for international source retrieval (SerpAPI Google Scholar)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest


class TestInternationalSourceDataclass:
    """Test the InternationalSource dataclass structure."""

    def test_international_source_has_required_fields(self):
        """InternationalSource should have url, title, source_type, and evidence_tier."""
        from procedurewriter.pipeline.international_sources import InternationalSource

        source = InternationalSource(
            url="https://www.nice.org.uk/guidance/ng39",
            title="Anaphylaxis guideline",
            source_type="nice_guideline",
            evidence_tier=1,
        )

        assert source.url == "https://www.nice.org.uk/guidance/ng39"
        assert source.title == "Anaphylaxis guideline"
        assert source.source_type == "nice_guideline"
        assert source.evidence_tier == 1

    def test_international_source_has_optional_abstract(self):
        """InternationalSource should support optional abstract field."""
        from procedurewriter.pipeline.international_sources import InternationalSource

        source = InternationalSource(
            url="https://www.nice.org.uk/guidance/ng39",
            title="Anaphylaxis guideline",
            source_type="nice_guideline",
            evidence_tier=1,
            abstract="This guideline covers the assessment and referral...",
        )

        assert source.abstract == "This guideline covers the assessment and referral..."

    def test_international_source_has_optional_publication_year(self):
        """InternationalSource should support optional publication_year field."""
        from procedurewriter.pipeline.international_sources import InternationalSource

        source = InternationalSource(
            url="https://www.nice.org.uk/guidance/ng39",
            title="Anaphylaxis guideline",
            source_type="nice_guideline",
            evidence_tier=1,
            publication_year=2020,
        )

        assert source.publication_year == 2020


class TestSourceTierEnum:
    """Test the SourceTier enum for evidence hierarchy."""

    def test_source_tier_has_international_gold_standard(self):
        """SourceTier should have TIER_1_INTERNATIONAL value."""
        from procedurewriter.pipeline.international_sources import SourceTier

        assert SourceTier.TIER_1_INTERNATIONAL.value == 1

    def test_source_tier_has_academic_evidence(self):
        """SourceTier should have TIER_2_ACADEMIC value."""
        from procedurewriter.pipeline.international_sources import SourceTier

        assert SourceTier.TIER_2_ACADEMIC.value == 2

    def test_source_tier_has_technique_sources(self):
        """SourceTier should have TIER_3_TECHNIQUE value."""
        from procedurewriter.pipeline.international_sources import SourceTier

        assert SourceTier.TIER_3_TECHNIQUE.value == 3

    def test_source_tier_has_danish_context(self):
        """SourceTier should have TIER_4_DANISH value."""
        from procedurewriter.pipeline.international_sources import SourceTier

        assert SourceTier.TIER_4_DANISH.value == 4


class TestSerpApiScholarClient:
    """Test SerpAPI Google Scholar client behavior."""

    SAMPLE_SERPAPI_RESPONSE = b"""
    {
      "organic_results": [
        {
          "title": "NICE guidance NG39",
          "link": "https://www.nice.org.uk/guidance/ng39",
          "snippet": "NICE guideline for anaphylaxis",
          "publication_info": {"summary": "2020 NICE"}
        },
        {
          "title": "Cochrane review on adrenaline",
          "link": "https://www.cochranelibrary.com/cdsr/doi/10.1002/14651858.CD009616.pub2/full",
          "snippet": "Cochrane systematic review",
          "publication_info": {"summary": "2012"}
        },
        {
          "title": "Unrelated article",
          "link": "https://example.com/article",
          "snippet": "Not relevant"
        }
      ]
    }
    """

    def test_serpapi_client_parses_nice_and_cochrane(self):
        """SerpAPI client should return NICE + Cochrane sources only."""
        from procedurewriter.pipeline.international_sources import SerpApiScholarClient

        http = DummyHttpClient(DummyResponse(status_code=200, content=self.SAMPLE_SERPAPI_RESPONSE))
        client = SerpApiScholarClient(http_client=http, api_key="test-key", strict_mode=True)
        results = client.search("anaphylaxis", max_results=5)

        assert len(results) == 2
        assert results[0].source_type in {"nice_guideline", "cochrane_review"}
        assert results[1].source_type in {"nice_guideline", "cochrane_review"}
        assert all("nice.org.uk" in r.url or "cochranelibrary.com" in r.url for r in results)

    def test_serpapi_client_strict_requires_key(self):
        """Strict mode should require SerpAPI key."""
        from procedurewriter.pipeline.international_sources import InternationalSourceError, SerpApiScholarClient

        http = DummyHttpClient(DummyResponse(status_code=200, content=b"{}"))
        client = SerpApiScholarClient(http_client=http, api_key=None, strict_mode=True)

        with pytest.raises(InternationalSourceError):
            client.search("anaphylaxis", max_results=1)


class TestInternationalSourceAggregator:
    """Test aggregator that combines SerpAPI results."""

    def test_aggregator_can_be_instantiated(self):
        """InternationalSourceAggregator should be instantiable."""
        from procedurewriter.pipeline.international_sources import InternationalSourceAggregator

        aggregator = InternationalSourceAggregator()
        assert aggregator is not None

    def test_aggregator_search_all_returns_sources_sorted_by_tier(self):
        """search_all should return sources sorted by evidence tier (1 first)."""
        from procedurewriter.pipeline.international_sources import InternationalSourceAggregator

        http = DummyHttpClient(
            DummyResponse(status_code=200, content=TestSerpApiScholarClient.SAMPLE_SERPAPI_RESPONSE)
        )
        aggregator = InternationalSourceAggregator(
            http_client=http,
            serpapi_api_key="test-key",
            serpapi_base_url="https://serpapi.com/search.json",
            serpapi_engine="google_scholar",
        )
        results = aggregator.search_all("anaphylaxis", max_per_tier=2)

        assert isinstance(results, list)
        if len(results) >= 2:
            for i in range(len(results) - 1):
                assert results[i].evidence_tier <= results[i + 1].evidence_tier

    def test_aggregator_reports_candidate_counts(self):
        """search_all_with_stats should return NICE/Cochrane counts."""
        from procedurewriter.pipeline.international_sources import InternationalSourceAggregator

        http = DummyHttpClient(
            DummyResponse(status_code=200, content=TestSerpApiScholarClient.SAMPLE_SERPAPI_RESPONSE)
        )
        aggregator = InternationalSourceAggregator(
            http_client=http,
            serpapi_api_key="test-key",
            serpapi_base_url="https://serpapi.com/search.json",
        )
        results, stats = aggregator.search_all_with_stats("anaphylaxis", max_per_tier=2)

        assert isinstance(results, list)
        assert stats["nice_candidates"] == 1
        assert stats["cochrane_candidates"] == 1
        assert stats["scholar_candidates"] == 2


# Test helpers for API clients
@dataclass
class DummyResponse:
    status_code: int
    content: bytes


class DummyHttpClient:
    def __init__(self, response: DummyResponse):
        self.response = response
        self.last_url: str | None = None
        self.last_params: dict[str, Any] | None = None
        self.last_headers: dict[str, str] | None = None

    def get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> DummyResponse:
        self.last_url = url
        self.last_params = params
        self.last_headers = headers
        return self.response
