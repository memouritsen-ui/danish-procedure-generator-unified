"""
Source Scoring Tests

Tests use REAL source metadata patterns.
NO MOCKS for external data.
"""
from datetime import datetime

from procedurewriter.pipeline.source_scoring import (
    SourceScore,
    calculate_quality_indicators,
    calculate_recency_score,
    rank_sources,
    score_source,
)


class TestRecencyScoring:
    """Test recency score calculation."""

    def test_current_year_gets_max_score(self):
        """Current year sources get 1.0 recency score."""
        current_year = datetime.now().year
        score, reason = calculate_recency_score(current_year)
        assert score == 1.0
        assert "Current year" in reason

    def test_one_year_old_high_score(self):
        """One year old sources get 0.95."""
        score, _ = calculate_recency_score(datetime.now().year - 1)
        assert score == 0.95

    def test_two_years_old_score(self):
        """Two year old sources get 0.90."""
        score, _ = calculate_recency_score(datetime.now().year - 2)
        assert score == 0.90

    def test_five_year_old_moderate_score(self):
        """Five year old sources get ~0.75."""
        score, reason = calculate_recency_score(datetime.now().year - 5)
        assert 0.74 <= score <= 0.76
        assert "Moderately recent" in reason

    def test_ten_year_old_lower_score(self):
        """Ten year old sources get ~0.50."""
        score, reason = calculate_recency_score(datetime.now().year - 10)
        assert 0.49 <= score <= 0.51
        assert "Older source" in reason

    def test_unknown_year_default(self):
        """Unknown year gets default 0.5."""
        score, reason = calculate_recency_score(None)
        assert score == 0.5
        assert "unknown" in reason.lower()

    def test_very_old_source_minimum(self):
        """Very old sources (30+ years) get minimum score."""
        score, reason = calculate_recency_score(1990)
        assert score >= 0.25
        assert "Historical" in reason

    def test_future_year_max_score(self):
        """Future year gets max score (edge case)."""
        score, _ = calculate_recency_score(datetime.now().year + 1)
        assert score == 1.0

    def test_custom_reference_year(self):
        """Custom reference year works correctly."""
        score, _ = calculate_recency_score(2020, reference_year=2020)
        assert score == 1.0

        score, _ = calculate_recency_score(2019, reference_year=2020)
        assert score == 0.95


class TestQualityIndicators:
    """Test quality indicator calculation."""

    def test_base_score(self):
        """Empty source gets base score of 0.5."""
        score, reasons = calculate_quality_indicators({})
        assert score == 0.5
        assert len(reasons) == 0

    def test_doi_adds_bonus(self):
        """DOI presence adds score."""
        source_with_doi = {"doi": "10.1234/test"}
        source_without = {}

        score_with, reasons_with = calculate_quality_indicators(source_with_doi)
        score_without, _ = calculate_quality_indicators(source_without)

        assert score_with > score_without
        assert score_with == 0.6  # 0.5 base + 0.1 DOI
        assert any("DOI" in r for r in reasons_with)

    def test_abstract_adds_bonus(self):
        """Abstract presence adds score."""
        source = {"abstract": "This is a test abstract."}
        score, reasons = calculate_quality_indicators(source)

        assert score == 0.55  # 0.5 base + 0.05 abstract
        assert any("abstract" in r for r in reasons)

    def test_abstract_in_extra(self):
        """Abstract in extra dict adds score."""
        source = {"extra": {"abstract": "This is a test abstract."}}
        score, reasons = calculate_quality_indicators(source)

        assert score == 0.55
        assert any("abstract" in r for r in reasons)

    def test_reputable_domain_sst(self):
        """Danish Health Authority domain gets bonus."""
        source = {"url": "https://www.sst.dk/da/viden/guidelines/test"}
        score, reasons = calculate_quality_indicators(source)

        assert score == 0.7  # 0.5 base + 0.2 sst.dk
        assert any("sst.dk" in r for r in reasons)

    def test_reputable_domain_cochrane(self):
        """Cochrane domain gets bonus."""
        source = {"url": "https://www.cochrane.org/reviews/CD001234"}
        score, reasons = calculate_quality_indicators(source)

        assert score == 0.7  # 0.5 base + 0.2 cochrane
        assert any("cochrane" in r for r in reasons)

    def test_pubmed_indexed_bonus(self):
        """PubMed indexed sources get bonus."""
        source = {"kind": "pubmed", "pmid": "12345678"}
        score, reasons = calculate_quality_indicators(source)

        assert score == 0.55  # 0.5 base + 0.05 pubmed
        assert any("PubMed" in r for r in reasons)

    def test_danish_guideline_kind_bonus(self):
        """Danish guideline kind gets bonus."""
        source = {"kind": "danish_guideline"}
        score, reasons = calculate_quality_indicators(source)

        assert score == 0.6  # 0.5 base + 0.1 danish_guideline
        assert any("Danish guideline" in r for r in reasons)

    def test_score_capped_at_one(self):
        """Quality score never exceeds 1.0."""
        source = {
            "doi": "10.1234/test",
            "abstract": "Test abstract",
            "url": "https://cochrane.org/review",
            "kind": "danish_guideline",
            "pmid": "12345",
        }
        score, _ = calculate_quality_indicators(source)
        assert score <= 1.0

    def test_multiple_bonuses_accumulate(self):
        """Multiple quality indicators accumulate."""
        source = {"doi": "10.1234/test", "abstract": "Test"}
        score, reasons = calculate_quality_indicators(source)

        assert score == 0.65  # 0.5 + 0.1 + 0.05
        assert len(reasons) == 2


class TestCompositeScoring:
    """Test full source scoring."""

    def test_basic_source_scoring(self):
        """Basic source gets scored correctly."""
        source = {
            "source_id": "SRC001",
            "title": "Test Source",
            "year": datetime.now().year,
        }
        result = score_source(source)

        assert isinstance(result, SourceScore)
        assert result.source_id == "SRC001"
        assert result.recency_year == datetime.now().year
        assert result.recency_score == 1.0
        assert result.composite_score > 0
        assert len(result.reasoning) > 0

    def test_high_quality_danish_guideline(self):
        """High quality recent Danish guideline with quality bonuses."""
        source = {
            "source_id": "SRC001",
            "url": "https://sst.dk/da/viden/guidelines/test",
            "kind": "danish_guideline",
            "year": datetime.now().year,
            "doi": "10.1234/test",
            "abstract": "Test",
        }
        result = score_source(source)

        # Quality score is now combined (metadata + content) / 2
        # Metadata: base 0.5 + sst.dk 0.2 + DOI 0.1 + abstract 0.05 + kind 0.1 = 0.95
        # Content: 0.5 (no content available)
        # Combined: (0.95 + 0.5) / 2 = 0.725
        assert result.quality_score >= 0.70
        assert "sst.dk" in str(result.reasoning)
        assert "DOI" in str(result.reasoning)
        # Recency should be max since current year
        assert result.recency_score == 1.0

    def test_old_unclassified_source_low_score(self):
        """Old unclassified source scores lower."""
        source = {
            "source_id": "SRC002",
            "url": "https://unknown-journal.com/article",
            "year": 2005,
        }
        result = score_source(source)

        # New formula with weights:
        # Provenance: 100/1000 * 35 = 3.5 pts (unclassified is now priority 100)
        # Recency: ~0.25 (20 years old) * 20 = 5 pts
        # Quality: 0.5 * 25 = 12.5 pts
        # Relevance: 0.5 * 20 = 10 pts
        # Total: ~31 pts
        assert result.composite_score < 35
        assert result.evidence_level == "unclassified"

    def test_pubmed_systematic_review(self):
        """PubMed systematic review has correct quality indicators."""
        source = {
            "source_id": "SRC003",
            "kind": "pubmed",
            "pmid": "12345678",
            "doi": "10.1234/test",
            "year": datetime.now().year - 2,
            "extra": {"publication_types": ["Systematic Review"]},
        }
        result = score_source(source)

        # Quality is now combined (metadata + content) / 2
        # Metadata: base 0.5 + DOI 0.1 + PubMed 0.05 = 0.65
        # Content: 0.5 (no content)
        # Combined: (0.65 + 0.5) / 2 = 0.575
        assert result.quality_score >= 0.55
        assert "DOI" in str(result.reasoning)
        assert "PubMed" in str(result.reasoning)
        # Recency should be 0.90 (2 years old)
        assert result.recency_score == 0.90
        assert result.composite_score > 0

    def test_reasoning_includes_all_components(self):
        """Reasoning includes provenance, recency, and quality components."""
        source = {
            "source_id": "SRC004",
            "url": "https://nice.org.uk/guidance",
            "year": 2022,
            "doi": "10.1234/test",
        }
        result = score_source(source)

        reasoning_text = " ".join(result.reasoning)
        assert "Provenance" in reasoning_text  # Changed from "Evidence level"
        assert "Recency" in reasoning_text
        assert "quality" in reasoning_text.lower()  # Combined quality
        assert "Total" in reasoning_text

    def test_score_without_year(self):
        """Source without year gets default recency score."""
        source = {"source_id": "SRC005", "title": "No Year Source"}
        result = score_source(source)

        assert result.recency_year is None
        assert result.recency_score == 0.5
        assert "unknown" in str(result.reasoning).lower()


class TestSourceRanking:
    """Test source ranking functionality."""

    def test_ranking_orders_by_score(self):
        """Ranking puts highest scores first."""
        sources = [
            {"source_id": "low", "year": 2000},
            {
                "source_id": "high",
                "url": "https://sst.dk",
                "kind": "danish_guideline",
                "year": 2024,
            },
            {"source_id": "mid", "year": 2020, "doi": "10.1234/test"},
        ]
        ranked = rank_sources(sources)

        assert ranked[0].source_id == "high"
        assert ranked[-1].source_id == "low"
        # Verify descending order
        for i in range(len(ranked) - 1):
            assert ranked[i].composite_score >= ranked[i + 1].composite_score

    def test_ranking_empty_list(self):
        """Empty source list returns empty ranking."""
        ranked = rank_sources([])
        assert ranked == []

    def test_ranking_single_source(self):
        """Single source list returns single ranked item."""
        sources = [{"source_id": "only", "year": 2023}]
        ranked = rank_sources(sources)

        assert len(ranked) == 1
        assert ranked[0].source_id == "only"

    def test_ranking_preserves_all_sources(self):
        """All sources are preserved in ranking."""
        sources = [
            {"source_id": f"SRC{i}", "year": 2020 + i} for i in range(10)
        ]
        ranked = rank_sources(sources)

        assert len(ranked) == 10
        source_ids = {s.source_id for s in ranked}
        assert source_ids == {f"SRC{i}" for i in range(10)}


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_missing_source_id_uses_default(self):
        """Missing source_id uses 'unknown'."""
        source = {"year": 2023}
        result = score_source(source)
        assert result.source_id == "unknown"

    def test_none_values_handled(self):
        """None values in source don't cause errors."""
        source = {
            "source_id": "test",
            "url": None,
            "year": None,
            "doi": None,
            "title": None,
        }
        result = score_source(source)
        assert result.composite_score > 0

    def test_empty_source_dict(self):
        """Empty source dict doesn't crash."""
        result = score_source({})
        assert result.source_id == "unknown"
        assert result.composite_score > 0

    def test_extra_fields_ignored(self):
        """Extra unknown fields are ignored."""
        source = {
            "source_id": "test",
            "year": 2023,
            "unknown_field": "should be ignored",
            "another_field": 12345,
        }
        result = score_source(source)
        assert result.composite_score > 0
