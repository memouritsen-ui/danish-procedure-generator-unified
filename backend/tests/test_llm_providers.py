"""Tests for LLM provider abstraction layer."""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from procedurewriter.llm.providers import (
    DEFAULT_MODELS,
    AnthropicProvider,
    LLMProviderType,
    LLMResponse,
    OllamaProvider,
    OpenAIProvider,
    get_default_model,
    get_llm_client,
)


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_cost_calculation_openai_gpt4(self) -> None:
        """Test cost calculation for gpt-4."""
        response = LLMResponse(
            content="test",
            model="gpt-4",
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
        )
        # gpt-4: $30/1M input, $60/1M output
        expected = (1000 / 1_000_000) * 30.00 + (500 / 1_000_000) * 60.00
        assert abs(response.cost_usd - expected) < 0.0001

    def test_cost_calculation_claude_sonnet(self) -> None:
        """Test cost calculation for Claude Sonnet."""
        response = LLMResponse(
            content="test",
            model="claude-3-5-sonnet-20241022",
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
        )
        # claude-3-5-sonnet: $3/1M input, $15/1M output
        expected = (1000 / 1_000_000) * 3.00 + (500 / 1_000_000) * 15.00
        assert abs(response.cost_usd - expected) < 0.0001

    def test_cost_calculation_ollama_free(self) -> None:
        """Test cost calculation for Ollama (local, free)."""
        response = LLMResponse(
            content="test",
            model="llama3.1",
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
        )
        assert response.cost_usd == 0.0

    def test_cost_calculation_unknown_model_uses_default(self) -> None:
        """Test that unknown models use default pricing."""
        response = LLMResponse(
            content="test",
            model="unknown-model-xyz",
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
        )
        # Default: $0.15/1M input, $0.60/1M output
        expected = (1000 / 1_000_000) * 0.15 + (500 / 1_000_000) * 0.60
        assert abs(response.cost_usd - expected) < 0.0001


class TestOpenAIProvider:
    """Tests for OpenAI provider."""

    def test_is_available_with_key(self) -> None:
        """Test provider is available with API key."""
        provider = OpenAIProvider(api_key="test-key")
        assert provider.is_available() is True

    def test_is_available_without_key(self) -> None:
        """Test provider is not available without API key."""
        provider = OpenAIProvider(api_key=None)
        assert provider.is_available() is False

    def test_provider_type(self) -> None:
        """Test provider type is correct."""
        provider = OpenAIProvider(api_key="test-key")
        assert provider.provider_type == LLMProviderType.OPENAI

    @patch("openai.OpenAI")
    def test_chat_completion_calls_openai_api(self, mock_openai_class: MagicMock) -> None:
        """Test chat completion calls OpenAI API correctly."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Hello!"))]
        mock_response.model = "gpt-4o-mini"
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIProvider(api_key="test-key")
        result = provider.chat_completion(
            messages=[{"role": "user", "content": "Hi"}],
            model="gpt-4o-mini",
            temperature=0.5,
        )

        assert result.content == "Hello!"
        assert result.model == "gpt-4o-mini"
        assert result.input_tokens == 10
        assert result.output_tokens == 5


class TestAnthropicProvider:
    """Tests for Anthropic provider."""

    def test_is_available_with_key(self) -> None:
        """Test provider is available with API key."""
        provider = AnthropicProvider(api_key="test-key")
        assert provider.is_available() is True

    def test_is_available_without_key(self) -> None:
        """Test provider is not available without API key."""
        provider = AnthropicProvider(api_key=None)
        assert provider.is_available() is False

    def test_provider_type(self) -> None:
        """Test provider type is correct."""
        provider = AnthropicProvider(api_key="test-key")
        assert provider.provider_type == LLMProviderType.ANTHROPIC

    def test_chat_completion_separates_system_message(self) -> None:
        """Test that system messages are separated for Anthropic API."""
        try:
            import anthropic
        except ImportError:
            pytest.skip("anthropic package not installed")

        with patch.object(anthropic, "Anthropic") as mock_anthropic_class:
            mock_client = MagicMock()
            mock_anthropic_class.return_value = mock_client

            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="Hello from Claude!")]
            mock_response.model = "claude-3-5-sonnet-20241022"
            mock_response.usage = MagicMock(input_tokens=10, output_tokens=5)
            mock_client.messages.create.return_value = mock_response

            provider = AnthropicProvider(api_key="test-key")
            result = provider.chat_completion(
                messages=[
                    {"role": "system", "content": "You are helpful."},
                    {"role": "user", "content": "Hi"},
                ],
                model="claude-3-5-sonnet-20241022",
                temperature=0.5,
            )

            # Check that system was passed separately
            call_kwargs = mock_client.messages.create.call_args[1]
            assert call_kwargs["system"] == "You are helpful."
            assert call_kwargs["messages"] == [{"role": "user", "content": "Hi"}]

            assert result.content == "Hello from Claude!"


class TestOllamaProvider:
    """Tests for Ollama provider."""

    def test_provider_type(self) -> None:
        """Test provider type is correct."""
        provider = OllamaProvider()
        assert provider.provider_type == LLMProviderType.OLLAMA

    def test_default_base_url(self) -> None:
        """Test default Ollama base URL."""
        provider = OllamaProvider()
        assert provider._base_url == "http://localhost:11434"

    def test_custom_base_url(self) -> None:
        """Test custom Ollama base URL."""
        provider = OllamaProvider(base_url="http://custom:8080/")
        assert provider._base_url == "http://custom:8080"  # trailing slash stripped


class TestGetLLMClient:
    """Tests for get_llm_client factory function."""

    def test_get_openai_client(self) -> None:
        """Test getting OpenAI client."""
        client = get_llm_client(
            provider=LLMProviderType.OPENAI,
            openai_api_key="test-key",
        )
        assert isinstance(client, OpenAIProvider)
        assert client.provider_type == LLMProviderType.OPENAI

    def test_get_anthropic_client(self) -> None:
        """Test getting Anthropic client."""
        client = get_llm_client(
            provider=LLMProviderType.ANTHROPIC,
            anthropic_api_key="test-key",
        )
        assert isinstance(client, AnthropicProvider)
        assert client.provider_type == LLMProviderType.ANTHROPIC

    @patch("procedurewriter.llm.providers.OllamaProvider.is_available", return_value=True)
    def test_get_ollama_client(self, mock_available: MagicMock) -> None:
        """Test getting Ollama client."""
        client = get_llm_client(
            provider=LLMProviderType.OLLAMA,
            ollama_base_url="http://localhost:11434",
        )
        assert isinstance(client, OllamaProvider)
        assert client.provider_type == LLMProviderType.OLLAMA

    def test_get_client_from_string(self) -> None:
        """Test getting client using string provider name."""
        client = get_llm_client(
            provider="openai",
            openai_api_key="test-key",
        )
        assert isinstance(client, OpenAIProvider)

    def test_raises_without_openai_key(self) -> None:
        """Test that ValueError is raised without OpenAI API key."""
        with pytest.raises(ValueError, match="OpenAI provider requires OPENAI_API_KEY"):
            get_llm_client(provider=LLMProviderType.OPENAI, openai_api_key=None)

    def test_raises_without_anthropic_key(self) -> None:
        """Test that ValueError is raised without Anthropic API key."""
        with pytest.raises(ValueError, match="Anthropic provider requires ANTHROPIC_API_KEY"):
            get_llm_client(provider=LLMProviderType.ANTHROPIC, anthropic_api_key=None)

    @patch.dict(os.environ, {"PROCEDUREWRITER_LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "env-key"})
    def test_auto_detect_from_env(self) -> None:
        """Test auto-detecting provider from environment."""
        client = get_llm_client()
        assert isinstance(client, AnthropicProvider)


class TestDefaultModels:
    """Tests for default model mappings."""

    def test_default_models_defined(self) -> None:
        """Test that default models are defined for all providers."""
        assert LLMProviderType.OPENAI in DEFAULT_MODELS
        assert LLMProviderType.ANTHROPIC in DEFAULT_MODELS
        assert LLMProviderType.OLLAMA in DEFAULT_MODELS

    def test_get_default_model(self) -> None:
        """Test get_default_model function."""
        assert get_default_model(LLMProviderType.OPENAI) == "gpt-4o-mini"
        assert get_default_model(LLMProviderType.ANTHROPIC) == "claude-3-5-sonnet-20241022"
        assert get_default_model(LLMProviderType.OLLAMA) == "llama3.1"
