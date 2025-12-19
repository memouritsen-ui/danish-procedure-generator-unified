"""
Cached LLM Provider Wrapper.

Wraps any LLM provider with transparent response caching to:
1. Reduce API costs during development
2. Speed up repeated operations
3. Enable offline development with cached responses

NO MOCKS - Uses real SQLite-based caching via LLMCache.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from procedurewriter.llm.cache import LLMCache, compute_cache_key
from procedurewriter.llm.providers import LLMProvider, LLMProviderType, LLMResponse


class CachedLLMProvider(LLMProvider):
    """
    LLM provider wrapper that adds transparent caching.

    Wraps any LLMProvider and caches responses based on:
    - messages content
    - model name
    - temperature

    Usage:
        provider = OpenAIProvider(api_key="...")
        cached = CachedLLMProvider(provider, cache_dir=Path("./cache"))

        # First call hits API
        response1 = cached.chat_completion(messages, model="gpt-4", temperature=0.2)

        # Second identical call returns cached response
        response2 = cached.chat_completion(messages, model="gpt-4", temperature=0.2)
    """

    def __init__(
        self,
        provider: LLMProvider,
        *,
        cache_dir: Path | None = None,
        enabled: bool = True,
    ) -> None:
        """
        Initialize cached provider wrapper.

        Args:
            provider: Underlying LLM provider to wrap
            cache_dir: Directory for cache storage
            enabled: Whether caching is enabled (default True)
        """
        self._provider = provider
        self._cache = LLMCache(cache_dir=cache_dir)
        self._enabled = enabled

    def chat_completion(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        timeout: float = 60.0,
    ) -> LLMResponse:
        """
        Get chat completion, using cache when possible.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model identifier
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            timeout: Request timeout in seconds

        Returns:
            LLMResponse from cache or provider
        """
        if not self._enabled:
            return self._provider.chat_completion(
                messages, model, temperature, max_tokens, timeout
            )

        # Compute cache key
        cache_key = compute_cache_key(messages, model, temperature)

        # Check cache
        cached = self._cache.get(cache_key)
        if cached is not None:
            return self._dict_to_response(cached)

        # Cache miss - call provider
        response = self._provider.chat_completion(
            messages, model, temperature, max_tokens, timeout
        )

        # Store in cache
        self._cache.set(cache_key, self._response_to_dict(response))

        return response

    def is_available(self) -> bool:
        """Delegate to underlying provider."""
        return self._provider.is_available()

    @property
    def provider_type(self) -> LLMProviderType:
        """Delegate to underlying provider."""
        return self._provider.provider_type

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache usage statistics."""
        return self._cache.get_stats()

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable caching."""
        self._enabled = enabled

    def clear_cache(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()

    @staticmethod
    def _response_to_dict(response: LLMResponse) -> dict[str, Any]:
        """Convert LLMResponse to dict for caching."""
        return {
            "content": response.content,
            "model": response.model,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "total_tokens": response.total_tokens,
        }

    @staticmethod
    def _dict_to_response(data: dict[str, Any]) -> LLMResponse:
        """Convert cached dict back to LLMResponse."""
        return LLMResponse(
            content=data["content"],
            model=data["model"],
            input_tokens=data["input_tokens"],
            output_tokens=data["output_tokens"],
            total_tokens=data.get("total_tokens", data["input_tokens"] + data["output_tokens"]),
        )
