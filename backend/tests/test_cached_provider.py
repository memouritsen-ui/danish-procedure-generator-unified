"""Tests for cached LLM provider wrapper."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from procedurewriter.llm.cached_provider import CachedLLMProvider
from procedurewriter.llm.providers import LLMProviderType, LLMResponse


class TestCachedLLMProvider:
    """Tests for CachedLLMProvider wrapper."""

    def _create_mock_provider(self) -> MagicMock:
        """Create a mock LLM provider."""
        mock = MagicMock()
        mock.provider_type = LLMProviderType.OPENAI
        mock.is_available.return_value = True
        return mock

    def test_cache_miss_calls_provider(self, tmp_path: Path) -> None:
        """First call should invoke the underlying provider."""
        mock_provider = self._create_mock_provider()
        mock_provider.chat_completion.return_value = LLMResponse(
            content="Hello!",
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            model="test-model",
        )

        cached = CachedLLMProvider(mock_provider, cache_dir=tmp_path)
        messages = [{"role": "user", "content": "Hi"}]

        result = cached.chat_completion(messages, model="test-model", temperature=0.2)

        mock_provider.chat_completion.assert_called_once()
        assert result.content == "Hello!"

    def test_cache_hit_skips_provider(self, tmp_path: Path) -> None:
        """Second identical call should return cached result without calling provider."""
        mock_provider = self._create_mock_provider()
        mock_provider.chat_completion.return_value = LLMResponse(
            content="Hello!",
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            model="test-model",
        )

        cached = CachedLLMProvider(mock_provider, cache_dir=tmp_path)
        messages = [{"role": "user", "content": "Hi"}]

        # First call - cache miss
        result1 = cached.chat_completion(messages, model="test-model", temperature=0.2)
        # Second call - cache hit
        result2 = cached.chat_completion(messages, model="test-model", temperature=0.2)

        # Provider should only be called once
        assert mock_provider.chat_completion.call_count == 1
        assert result1.content == result2.content

    def test_different_messages_not_cached(self, tmp_path: Path) -> None:
        """Different messages should not use cached result."""
        mock_provider = self._create_mock_provider()
        mock_provider.chat_completion.return_value = LLMResponse(
            content="Response",
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            model="test-model",
        )

        cached = CachedLLMProvider(mock_provider, cache_dir=tmp_path)

        cached.chat_completion([{"role": "user", "content": "A"}], model="m", temperature=0.2)
        cached.chat_completion([{"role": "user", "content": "B"}], model="m", temperature=0.2)

        assert mock_provider.chat_completion.call_count == 2

    def test_cache_disabled_always_calls_provider(self, tmp_path: Path) -> None:
        """When caching is disabled, always call provider."""
        mock_provider = self._create_mock_provider()
        mock_provider.chat_completion.return_value = LLMResponse(
            content="Response",
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            model="test-model",
        )

        cached = CachedLLMProvider(mock_provider, cache_dir=tmp_path, enabled=False)
        messages = [{"role": "user", "content": "Hi"}]

        cached.chat_completion(messages, model="test-model", temperature=0.2)
        cached.chat_completion(messages, model="test-model", temperature=0.2)

        assert mock_provider.chat_completion.call_count == 2

    def test_get_cache_stats(self, tmp_path: Path) -> None:
        """Cache stats should reflect usage."""
        mock_provider = self._create_mock_provider()
        mock_provider.chat_completion.return_value = LLMResponse(
            content="Response",
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            model="test-model",
        )

        cached = CachedLLMProvider(mock_provider, cache_dir=tmp_path)
        messages = [{"role": "user", "content": "Hi"}]

        cached.chat_completion(messages, model="m", temperature=0.2)  # miss
        cached.chat_completion(messages, model="m", temperature=0.2)  # hit

        stats = cached.get_cache_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1

    def test_provider_type_delegated(self, tmp_path: Path) -> None:
        """provider_type should delegate to underlying provider."""
        mock_provider = self._create_mock_provider()
        cached = CachedLLMProvider(mock_provider, cache_dir=tmp_path)

        assert cached.provider_type == LLMProviderType.OPENAI

    def test_is_available_delegated(self, tmp_path: Path) -> None:
        """is_available should delegate to underlying provider."""
        mock_provider = self._create_mock_provider()
        mock_provider.is_available.return_value = True
        cached = CachedLLMProvider(mock_provider, cache_dir=tmp_path)

        assert cached.is_available() is True
        mock_provider.is_available.assert_called_once()

    def test_set_enabled(self, tmp_path: Path) -> None:
        """set_enabled should toggle caching."""
        mock_provider = self._create_mock_provider()
        mock_provider.chat_completion.return_value = LLMResponse(
            content="Response",
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            model="test-model",
        )

        cached = CachedLLMProvider(mock_provider, cache_dir=tmp_path, enabled=True)
        messages = [{"role": "user", "content": "Hi"}]

        # First call with caching enabled
        cached.chat_completion(messages, model="m", temperature=0.2)
        cached.chat_completion(messages, model="m", temperature=0.2)  # hit
        assert mock_provider.chat_completion.call_count == 1

        # Disable caching
        cached.set_enabled(False)
        cached.chat_completion(messages, model="m", temperature=0.2)  # should call provider
        assert mock_provider.chat_completion.call_count == 2

    def test_clear_cache(self, tmp_path: Path) -> None:
        """clear_cache should remove all cached entries."""
        mock_provider = self._create_mock_provider()
        mock_provider.chat_completion.return_value = LLMResponse(
            content="Response",
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            model="test-model",
        )

        cached = CachedLLMProvider(mock_provider, cache_dir=tmp_path)
        messages = [{"role": "user", "content": "Hi"}]

        # Cache something
        cached.chat_completion(messages, model="m", temperature=0.2)
        assert mock_provider.chat_completion.call_count == 1

        # Clear and try again
        cached.clear_cache()
        cached.chat_completion(messages, model="m", temperature=0.2)
        assert mock_provider.chat_completion.call_count == 2  # Called again after clear
