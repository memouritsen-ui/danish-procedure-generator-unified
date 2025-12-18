"""
LLM Provider Module

Provides a unified interface for multiple LLM providers (OpenAI, Anthropic, Ollama).

Usage:
    from procedurewriter.llm import get_llm_client, LLMResponse, LLMProviderType

    # Auto-detect from PROCEDUREWRITER_LLM_PROVIDER env var
    client = get_llm_client()

    # Or explicitly specify provider
    client = get_llm_client(LLMProviderType.ANTHROPIC)

    # Make a request
    response = client.chat_completion(
        messages=[
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello!"},
        ],
        model="gpt-4o-mini",
        temperature=0.2,
    )

    print(response.content)
    print(f"Cost: ${response.cost_usd:.4f}")
"""

from procedurewriter.llm.providers import (
    DEFAULT_MODELS,
    AnthropicProvider,
    LLMProvider,
    LLMProviderType,
    LLMResponse,
    OllamaProvider,
    OpenAIProvider,
    get_default_model,
    get_llm_client,
)
from procedurewriter.llm.cost_tracker import (
    CostEntry,
    CostSummary,
    CostTracker,
    get_session_tracker,
    reset_session_tracker,
)

__all__ = [
    # Providers
    "LLMProvider",
    "LLMProviderType",
    "LLMResponse",
    "OpenAIProvider",
    "AnthropicProvider",
    "OllamaProvider",
    "get_llm_client",
    "get_default_model",
    "DEFAULT_MODELS",
    # Cost tracking
    "CostEntry",
    "CostSummary",
    "CostTracker",
    "get_session_tracker",
    "reset_session_tracker",
]
