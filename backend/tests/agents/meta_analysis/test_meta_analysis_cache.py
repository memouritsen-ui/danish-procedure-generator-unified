"""Tests for MetaAnalysisCache - document-level caching for PICO extractions.

Document-level caching uses SHA-256 hash of abstract text as cache key,
enabling reuse of PICO extractions across pipeline runs.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from procedurewriter.agents.meta_analysis.models import PICOData


class TestMetaAnalysisCacheBasics:
    """Basic functionality tests for MetaAnalysisCache."""

    def test_cache_class_exists(self) -> None:
        """MetaAnalysisCache should be importable."""
        from procedurewriter.agents.meta_analysis.cache import MetaAnalysisCache

        assert MetaAnalysisCache is not None

    def test_cache_initialization(self, tmp_path: Path) -> None:
        """MetaAnalysisCache should initialize with cache directory."""
        from procedurewriter.agents.meta_analysis.cache import MetaAnalysisCache

        cache = MetaAnalysisCache(cache_dir=tmp_path)
        assert cache.cache_dir == tmp_path

    def test_cache_creates_directory_if_missing(self, tmp_path: Path) -> None:
        """MetaAnalysisCache should create cache directory if it doesn't exist."""
        from procedurewriter.agents.meta_analysis.cache import MetaAnalysisCache

        cache_dir = tmp_path / "nonexistent" / "cache"
        cache = MetaAnalysisCache(cache_dir=cache_dir)
        assert cache_dir.exists()


class TestCacheKeyGeneration:
    """Tests for cache key generation using SHA-256 hash."""

    def test_compute_cache_key_deterministic(self, tmp_path: Path) -> None:
        """Same abstract should produce same cache key."""
        from procedurewriter.agents.meta_analysis.cache import MetaAnalysisCache

        cache = MetaAnalysisCache(cache_dir=tmp_path)
        abstract = "This is a study about hypertension treatment."

        key1 = cache.compute_cache_key(abstract)
        key2 = cache.compute_cache_key(abstract)

        assert key1 == key2

    def test_compute_cache_key_different_abstracts(self, tmp_path: Path) -> None:
        """Different abstracts should produce different cache keys."""
        from procedurewriter.agents.meta_analysis.cache import MetaAnalysisCache

        cache = MetaAnalysisCache(cache_dir=tmp_path)

        key1 = cache.compute_cache_key("Study about diabetes")
        key2 = cache.compute_cache_key("Study about cancer")

        assert key1 != key2

    def test_compute_cache_key_is_32_char_hex(self, tmp_path: Path) -> None:
        """Cache key should be 32-character hex string (truncated SHA-256)."""
        from procedurewriter.agents.meta_analysis.cache import MetaAnalysisCache

        cache = MetaAnalysisCache(cache_dir=tmp_path)
        key = cache.compute_cache_key("Any abstract text")

        assert len(key) == 32
        assert all(c in "0123456789abcdef" for c in key)

    def test_compute_cache_key_includes_study_id(self, tmp_path: Path) -> None:
        """Cache key should include study_id for disambiguation."""
        from procedurewriter.agents.meta_analysis.cache import MetaAnalysisCache

        cache = MetaAnalysisCache(cache_dir=tmp_path)
        abstract = "Same abstract text"

        key1 = cache.compute_cache_key(abstract, study_id="Study1")
        key2 = cache.compute_cache_key(abstract, study_id="Study2")

        assert key1 != key2


class TestCacheOperations:
    """Tests for cache get/set operations."""

    def _create_sample_pico(self) -> PICOData:
        """Create sample PICOData for testing."""
        return PICOData(
            population="Adults with hypertension",
            intervention="ACE inhibitors",
            comparison="Placebo",
            outcome="Blood pressure reduction",
            confidence=0.92,
            population_mesh=["Hypertension", "Adult"],
            intervention_mesh=["Angiotensin-Converting Enzyme Inhibitors"],
            outcome_mesh=["Blood Pressure"],
        )

    def test_cache_miss_returns_none(self, tmp_path: Path) -> None:
        """Cache should return None for missing entries."""
        from procedurewriter.agents.meta_analysis.cache import MetaAnalysisCache

        cache = MetaAnalysisCache(cache_dir=tmp_path)
        result = cache.get("nonexistent_key")

        assert result is None

    def test_cache_set_and_get(self, tmp_path: Path) -> None:
        """Cache should store and retrieve PICOData."""
        from procedurewriter.agents.meta_analysis.cache import MetaAnalysisCache

        cache = MetaAnalysisCache(cache_dir=tmp_path)
        pico = self._create_sample_pico()

        cache.set("test_key", pico)
        result = cache.get("test_key")

        assert result is not None
        assert result.population == pico.population
        assert result.confidence == pico.confidence

    def test_cache_persists_across_instances(self, tmp_path: Path) -> None:
        """Cache should persist across MetaAnalysisCache instances."""
        from procedurewriter.agents.meta_analysis.cache import MetaAnalysisCache

        pico = self._create_sample_pico()

        # First instance sets value
        cache1 = MetaAnalysisCache(cache_dir=tmp_path)
        cache1.set("persist_key", pico)

        # New instance should find the cached value
        cache2 = MetaAnalysisCache(cache_dir=tmp_path)
        result = cache2.get("persist_key")

        assert result is not None
        assert result.population == pico.population

    def test_cache_stores_all_pico_fields(self, tmp_path: Path) -> None:
        """Cache should preserve all PICOData fields including MeSH terms."""
        from procedurewriter.agents.meta_analysis.cache import MetaAnalysisCache

        cache = MetaAnalysisCache(cache_dir=tmp_path)
        pico = self._create_sample_pico()

        cache.set("full_key", pico)
        result = cache.get("full_key")

        assert result.population_mesh == pico.population_mesh
        assert result.intervention_mesh == pico.intervention_mesh
        assert result.outcome_mesh == pico.outcome_mesh


class TestLowConfidenceExclusion:
    """Tests ensuring low-confidence extractions are NOT cached."""

    def test_should_cache_returns_true_for_high_confidence(self, tmp_path: Path) -> None:
        """should_cache returns True for confidence >= 0.85."""
        from procedurewriter.agents.meta_analysis.cache import MetaAnalysisCache

        cache = MetaAnalysisCache(cache_dir=tmp_path)
        pico = PICOData(
            population="P",
            intervention="I",
            comparison="C",
            outcome="O",
            confidence=0.85,
        )

        assert cache.should_cache(pico) is True

    def test_should_cache_returns_false_for_low_confidence(self, tmp_path: Path) -> None:
        """should_cache returns False for confidence < 0.85."""
        from procedurewriter.agents.meta_analysis.cache import MetaAnalysisCache

        cache = MetaAnalysisCache(cache_dir=tmp_path)
        pico = PICOData(
            population="P",
            intervention="I",
            comparison="C",
            outcome="O",
            confidence=0.84,
        )

        assert cache.should_cache(pico) is False

    def test_set_rejects_low_confidence_by_default(self, tmp_path: Path) -> None:
        """set() should reject low-confidence extractions unless force=True."""
        from procedurewriter.agents.meta_analysis.cache import MetaAnalysisCache

        cache = MetaAnalysisCache(cache_dir=tmp_path)
        low_conf_pico = PICOData(
            population="P",
            intervention="I",
            comparison="C",
            outcome="O",
            confidence=0.70,
        )

        # Should not cache low confidence by default
        cache.set("low_conf_key", low_conf_pico)
        result = cache.get("low_conf_key")

        assert result is None

    def test_set_allows_low_confidence_with_force(self, tmp_path: Path) -> None:
        """set() with force=True should cache low-confidence extractions."""
        from procedurewriter.agents.meta_analysis.cache import MetaAnalysisCache

        cache = MetaAnalysisCache(cache_dir=tmp_path)
        low_conf_pico = PICOData(
            population="P",
            intervention="I",
            comparison="C",
            outcome="O",
            confidence=0.70,
        )

        cache.set("forced_key", low_conf_pico, force=True)
        result = cache.get("forced_key")

        assert result is not None
        assert result.confidence == 0.70


class TestCacheWithExtractor:
    """Integration tests with PICOExtractor."""

    def test_cache_integration_with_extractor(self, tmp_path: Path) -> None:
        """Cache should work with PICOExtractor output."""
        from procedurewriter.agents.meta_analysis.cache import MetaAnalysisCache

        cache = MetaAnalysisCache(cache_dir=tmp_path)

        # Simulate extractor output
        pico = PICOData(
            population="Voksne med hypertension",
            intervention="ACE-hæmmere",
            comparison="Placebo",
            outcome="Blodtrykssænkning",
            confidence=0.88,
            population_mesh=["Hypertension", "Adult"],
            intervention_mesh=["Angiotensin-Converting Enzyme Inhibitors"],
            outcome_mesh=["Blood Pressure"],
        )

        abstract = "Dette RCT sammenlignede ACE-hæmmere med placebo..."
        key = cache.compute_cache_key(abstract, study_id="Hansen2022")

        cache.set(key, pico)
        cached = cache.get(key)

        assert cached is not None
        assert cached.population == "Voksne med hypertension"


class TestCacheStats:
    """Tests for cache statistics."""

    def test_get_stats_initial(self, tmp_path: Path) -> None:
        """Initial cache stats should show zero hits/misses."""
        from procedurewriter.agents.meta_analysis.cache import MetaAnalysisCache

        cache = MetaAnalysisCache(cache_dir=tmp_path)
        stats = cache.get_stats()

        assert stats["hits"] == 0
        assert stats["misses"] == 0

    def test_get_stats_after_operations(self, tmp_path: Path) -> None:
        """Cache stats should reflect get operations."""
        from procedurewriter.agents.meta_analysis.cache import MetaAnalysisCache

        cache = MetaAnalysisCache(cache_dir=tmp_path)
        pico = PICOData(
            population="P",
            intervention="I",
            comparison="C",
            outcome="O",
            confidence=0.90,
        )

        cache.set("key", pico)
        cache.get("key")  # hit
        cache.get("nonexistent")  # miss

        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1

    def test_clear_cache(self, tmp_path: Path) -> None:
        """clear() should remove all cached entries."""
        from procedurewriter.agents.meta_analysis.cache import MetaAnalysisCache

        cache = MetaAnalysisCache(cache_dir=tmp_path)
        pico = PICOData(
            population="P",
            intervention="I",
            comparison="C",
            outcome="O",
            confidence=0.90,
        )

        cache.set("key1", pico)
        cache.set("key2", pico)

        cache.clear()

        assert cache.get("key1") is None
        assert cache.get("key2") is None
