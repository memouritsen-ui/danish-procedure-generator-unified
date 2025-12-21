"""Tests for LLM client caching integration."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from procedurewriter.llm.cached_provider import CachedLLMProvider
from procedurewriter.llm.providers import (
    OpenAIProvider,
    get_llm_client,
)


class TestGetLLMClientCaching:
    """Tests for caching integration in get_llm_client."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_caching_enabled_by_default(self, tmp_path: Path) -> None:
        """get_llm_client should return CachedLLMProvider by default."""
        client = get_llm_client(cache_dir=tmp_path)
        assert isinstance(client, CachedLLMProvider)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_caching_can_be_disabled(self, tmp_path: Path) -> None:
        """get_llm_client with enable_cache=False should return raw provider."""
        client = get_llm_client(enable_cache=False)
        assert not isinstance(client, CachedLLMProvider)
        assert isinstance(client, OpenAIProvider)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_custom_cache_dir(self, tmp_path: Path) -> None:
        """get_llm_client should use custom cache_dir when provided."""
        custom_dir = tmp_path / "custom_cache"
        client = get_llm_client(cache_dir=custom_dir)
        assert isinstance(client, CachedLLMProvider)
        # Verify cache directory was created
        assert custom_dir.exists()
