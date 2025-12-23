"""
LLM Provider Abstraction Layer

Supports multiple LLM providers (OpenAI, Anthropic, Ollama) with a unified interface.
Provider selection is done via PROCEDUREWRITER_LLM_PROVIDER environment variable.

Usage:
    from procedurewriter.llm import get_llm_client, LLMResponse

    client = get_llm_client()
    response = client.chat_completion(
        messages=[{"role": "user", "content": "Hello"}],
        model="gpt-5.2",  # Gold-standard model for medical procedures
        temperature=0.2,
    )
    print(response.content)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class LLMProviderType(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"


@dataclass
class LLMResponse:
    """Unified response from any LLM provider."""
    content: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    raw_response: Any = None

    @property
    def cost_usd(self) -> float:
        """Estimate cost based on model and token usage."""
        # Pricing per 1M tokens (as of Dec 2024 / Jan 2025)
        pricing = {
            # OpenAI - GPT-5 series (gold standard)
            "gpt-5.2": (15.00, 60.00),  # GPT-5.2 pricing estimate
            "gpt-5": (15.00, 60.00),  # GPT-5 series base pricing
            "gpt-5.1": (15.00, 60.00),  # GPT-5.1 pricing estimate
            # OpenAI - GPT-4 series (legacy)
            "gpt-4o": (2.50, 10.00),
            "gpt-4o-mini": (0.15, 0.60),
            "gpt-4-turbo": (10.00, 30.00),
            "gpt-4": (30.00, 60.00),
            "gpt-3.5-turbo": (0.50, 1.50),
            # Anthropic
            "claude-opus-4-5-20251101": (15.00, 75.00),  # Claude Opus 4.5 (current)
            "claude-opus-4-5-20250929": (15.00, 75.00),
            "claude-sonnet-4-5-20250929": (3.00, 15.00),
            "claude-3-5-sonnet-20241022": (3.00, 15.00),
            "claude-3-5-haiku-20241022": (1.00, 5.00),
            "claude-3-opus-20240229": (15.00, 75.00),
            "claude-3-sonnet-20240229": (3.00, 15.00),
            "claude-3-haiku-20240307": (0.25, 1.25),
            # Ollama (local, free)
            "llama3": (0.0, 0.0),
            "llama3.1": (0.0, 0.0),
            "mistral": (0.0, 0.0),
            "mistral-small": (0.0, 0.0),
            "mixtral": (0.0, 0.0),
        }

        # Find matching model or default to GPT-5.2 pricing (the gold standard)
        model_key = self.model.lower()
        for key, (input_price, output_price) in pricing.items():
            if key in model_key:
                input_cost = (self.input_tokens / 1_000_000) * input_price
                output_cost = (self.output_tokens / 1_000_000) * output_price
                return input_cost + output_cost

        # Default to GPT-5.2 pricing for unknown models (assume high-end usage)
        return (self.input_tokens / 1_000_000) * 15.00 + (self.output_tokens / 1_000_000) * 60.00


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def chat_completion(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        timeout: float = 60.0,
    ) -> LLMResponse:
        """
        Send a chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model identifier
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens in response
            timeout: Request timeout in seconds

        Returns:
            LLMResponse with content and usage info
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is configured and available."""
        pass

    @property
    @abstractmethod
    def provider_type(self) -> LLMProviderType:
        """Return the provider type."""
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI API provider."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self._api_key = api_key
        self._base_url = base_url
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            from openai import OpenAI
            # Use generous default timeout - individual calls can override
            self._client = OpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                timeout=300.0,  # 5 minutes default for GPT-5.x with reasoning
                max_retries=2,
            )
        return self._client

    def chat_completion(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        timeout: float = 300.0,  # 5 minutes default for GPT-5.x with reasoning
    ) -> LLMResponse:
        client = self._get_client()

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "timeout": timeout,  # Pass timeout to the API call
        }
        if max_tokens:
            # GPT-5 series and newer models use max_completion_tokens instead of max_tokens
            if "gpt-5" in model.lower() or "o1" in model.lower() or "o3" in model.lower():
                kwargs["max_completion_tokens"] = max_tokens
            else:
                kwargs["max_tokens"] = max_tokens

        response = client.chat.completions.create(**kwargs)

        content = response.choices[0].message.content or ""
        usage = response.usage

        return LLMResponse(
            content=content,
            model=response.model,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
            raw_response=response,
        )

    def is_available(self) -> bool:
        return bool(self._api_key)

    @property
    def provider_type(self) -> LLMProviderType:
        return LLMProviderType.OPENAI


class AnthropicProvider(LLMProvider):
    """Anthropic API provider."""

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            from anthropic import Anthropic
            self._client = Anthropic(api_key=self._api_key)
        return self._client

    def chat_completion(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        timeout: float = 60.0,
    ) -> LLMResponse:
        client = self._get_client()

        # Convert messages format: separate system from user/assistant
        system_content = ""
        api_messages: list[dict[str, str]] = []

        for msg in messages:
            if msg["role"] == "system":
                system_content = msg["content"]
            else:
                api_messages.append({"role": msg["role"], "content": msg["content"]})

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": api_messages,
            "max_tokens": max_tokens or 4096,
        }
        if system_content:
            kwargs["system"] = system_content
        if temperature > 0:
            kwargs["temperature"] = temperature

        response = client.messages.create(**kwargs)

        content = ""
        if response.content:
            content = response.content[0].text if hasattr(response.content[0], "text") else str(response.content[0])

        return LLMResponse(
            content=content,
            model=response.model,
            input_tokens=response.usage.input_tokens if response.usage else 0,
            output_tokens=response.usage.output_tokens if response.usage else 0,
            total_tokens=(response.usage.input_tokens + response.usage.output_tokens) if response.usage else 0,
            raw_response=response,
        )

    def is_available(self) -> bool:
        return bool(self._api_key)

    @property
    def provider_type(self) -> LLMProviderType:
        return LLMProviderType.ANTHROPIC


class OllamaProvider(LLMProvider):
    """Ollama local API provider."""

    def __init__(self, base_url: str = "http://localhost:11434"):
        self._base_url = base_url.rstrip("/")
        self._available: bool | None = None

    def chat_completion(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        timeout: float = 60.0,
    ) -> LLMResponse:
        import httpx

        url = f"{self._base_url}/api/chat"

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        content = data.get("message", {}).get("content", "")

        # Ollama provides token counts in some versions
        prompt_eval_count = data.get("prompt_eval_count", 0)
        eval_count = data.get("eval_count", 0)

        return LLMResponse(
            content=content,
            model=data.get("model", model),
            input_tokens=prompt_eval_count,
            output_tokens=eval_count,
            total_tokens=prompt_eval_count + eval_count,
            raw_response=data,
        )

    def is_available(self) -> bool:
        if self._available is not None:
            return self._available

        import httpx
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self._base_url}/api/tags")
                self._available = response.status_code == 200
        except (httpx.HTTPError, OSError):
            # Ollama server unavailable or network error
            self._available = False

        return self._available

    @property
    def provider_type(self) -> LLMProviderType:
        return LLMProviderType.OLLAMA


def get_llm_client(
    provider: LLMProviderType | str | None = None,
    *,
    openai_api_key: str | None = None,
    openai_base_url: str | None = None,
    anthropic_api_key: str | None = None,
    ollama_base_url: str | None = None,
    enable_cache: bool = True,
    cache_dir: Path | None = None,
) -> LLMProvider:
    """
    Get an LLM client for the specified provider.

    Args:
        provider: Provider type (openai, anthropic, ollama) or None for auto-detect
        openai_api_key: OpenAI API key
        openai_base_url: OpenAI base URL (for Azure or custom endpoints)
        anthropic_api_key: Anthropic API key
        ollama_base_url: Ollama server URL
        enable_cache: Whether to enable response caching (default: True)
        cache_dir: Custom cache directory (default: ~/.cache/procedurewriter/llm)

    Returns:
        Configured LLM provider (wrapped with caching if enabled)

    Raises:
        ValueError: If provider is not configured or unavailable
    """
    import os

    # Get from env if not provided
    if provider is None:
        provider = os.environ.get("PROCEDUREWRITER_LLM_PROVIDER", "openai")

    if isinstance(provider, str):
        provider = LLMProviderType(provider.lower())

    client: LLMProvider

    if provider == LLMProviderType.OPENAI:
        api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
        base_url = openai_base_url or os.environ.get("OPENAI_BASE_URL")
        client = OpenAIProvider(api_key=api_key, base_url=base_url)
        if not client.is_available():
            raise ValueError("OpenAI provider requires OPENAI_API_KEY")

    elif provider == LLMProviderType.ANTHROPIC:
        api_key = anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
        client = AnthropicProvider(api_key=api_key)
        if not client.is_available():
            raise ValueError("Anthropic provider requires ANTHROPIC_API_KEY")

    elif provider == LLMProviderType.OLLAMA:
        base_url = ollama_base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        client = OllamaProvider(base_url=base_url)
        if not client.is_available():
            raise ValueError(f"Ollama server not available at {base_url}")

    else:
        raise ValueError(f"Unknown provider: {provider}")

    # Wrap with caching if enabled
    if enable_cache:
        from procedurewriter.llm.cached_provider import CachedLLMProvider
        client = CachedLLMProvider(client, cache_dir=cache_dir, enabled=True)

    return client


# Default models per provider - GPT-5.2 is required for gold-standard output
DEFAULT_MODELS = {
    LLMProviderType.OPENAI: "gpt-5.2",
    LLMProviderType.ANTHROPIC: "claude-opus-4-5-20251101",
    LLMProviderType.OLLAMA: "llama3.1",
}


def get_default_model(provider: LLMProviderType) -> str:
    """Get the default model for a provider."""
    return DEFAULT_MODELS.get(provider, "gpt-5.2")
