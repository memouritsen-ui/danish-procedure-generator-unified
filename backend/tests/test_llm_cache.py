"""Tests for LLM response caching."""
from __future__ import annotations

from pathlib import Path

import pytest

from procedurewriter.llm.cache import LLMCache, compute_cache_key


class TestComputeCacheKey:
    """Tests for cache key computation."""

    def test_same_input_same_key(self) -> None:
        """Identical inputs should produce identical cache keys."""
        messages = [{"role": "user", "content": "Hello"}]
        key1 = compute_cache_key(messages, "gpt-4", 0.2)
        key2 = compute_cache_key(messages, "gpt-4", 0.2)
        assert key1 == key2

    def test_different_content_different_key(self) -> None:
        """Different message content should produce different keys."""
        messages1 = [{"role": "user", "content": "Hello"}]
        messages2 = [{"role": "user", "content": "Hi"}]
        key1 = compute_cache_key(messages1, "gpt-4", 0.2)
        key2 = compute_cache_key(messages2, "gpt-4", 0.2)
        assert key1 != key2

    def test_different_model_different_key(self) -> None:
        """Different model should produce different keys."""
        messages = [{"role": "user", "content": "Hello"}]
        key1 = compute_cache_key(messages, "gpt-4", 0.2)
        key2 = compute_cache_key(messages, "gpt-3.5-turbo", 0.2)
        assert key1 != key2

    def test_different_temperature_different_key(self) -> None:
        """Different temperature should produce different keys."""
        messages = [{"role": "user", "content": "Hello"}]
        key1 = compute_cache_key(messages, "gpt-4", 0.2)
        key2 = compute_cache_key(messages, "gpt-4", 0.7)
        assert key1 != key2

    def test_key_is_hex_string(self) -> None:
        """Cache key should be a valid hex string."""
        messages = [{"role": "user", "content": "Test"}]
        key = compute_cache_key(messages, "gpt-4", 0.2)
        assert isinstance(key, str)
        assert len(key) == 32  # SHA-256 truncated to 32 chars
        assert all(c in "0123456789abcdef" for c in key)


class TestLLMCache:
    """Tests for LLMCache class."""

    def test_get_miss_returns_none(self, tmp_path: Path) -> None:
        """Cache miss should return None."""
        cache = LLMCache(cache_dir=tmp_path)
        result = cache.get("nonexistent_key")
        assert result is None

    def test_set_and_get(self, tmp_path: Path) -> None:
        """Set then get should return the cached value."""
        cache = LLMCache(cache_dir=tmp_path)
        response_data = {
            "content": "Hello there!",
            "input_tokens": 10,
            "output_tokens": 5,
            "model": "gpt-4",
        }
        cache.set("test_key", response_data)
        result = cache.get("test_key")
        assert result == response_data

    def test_cache_persists_across_instances(self, tmp_path: Path) -> None:
        """Cache should persist when a new instance is created."""
        response_data = {"content": "Cached response", "input_tokens": 10, "output_tokens": 5}

        cache1 = LLMCache(cache_dir=tmp_path)
        cache1.set("persist_key", response_data)

        cache2 = LLMCache(cache_dir=tmp_path)
        result = cache2.get("persist_key")
        assert result == response_data

    def test_cache_stats_hits_and_misses(self, tmp_path: Path) -> None:
        """Cache stats should track hits and misses."""
        cache = LLMCache(cache_dir=tmp_path)
        cache.set("key1", {"content": "one"})
        cache.get("key1")  # hit
        cache.get("key2")  # miss

        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["entries"] == 1

    def test_clear_cache(self, tmp_path: Path) -> None:
        """Clear should remove all cached entries."""
        cache = LLMCache(cache_dir=tmp_path)
        cache.set("key1", {"content": "one"})
        cache.set("key2", {"content": "two"})

        cache.clear()

        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert cache.get_stats()["entries"] == 0

    def test_overwrite_existing_key(self, tmp_path: Path) -> None:
        """Setting same key twice should overwrite."""
        cache = LLMCache(cache_dir=tmp_path)
        cache.set("key1", {"content": "first"})
        cache.set("key1", {"content": "second"})

        result = cache.get("key1")
        assert result["content"] == "second"

    def test_get_size_bytes(self, tmp_path: Path) -> None:
        """Should return database file size."""
        cache = LLMCache(cache_dir=tmp_path)
        cache.set("key1", {"content": "some data"})

        size = cache.get_size_bytes()
        assert size > 0
