"""Tests for style profile integration in pipeline."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from procedurewriter.models.style_profile import StyleProfile


def make_test_profile() -> StyleProfile:
    return StyleProfile(
        id="test-id",
        name="Test",
        description=None,
        is_default=True,
        tone_description="Formel",
        target_audience="Læger",
        detail_level="comprehensive",
    )


def test_pipeline_uses_style_agent_when_profile_exists() -> None:
    """Pipeline should use StyleAgent when a default profile exists."""
    # This test verifies the integration point exists
    from procedurewriter.pipeline.run import _apply_style_profile

    mock_llm = MagicMock()
    mock_llm.chat_completion.return_value = MagicMock(
        content="Polished [SRC0001] text",
        input_tokens=10,
        output_tokens=10,
        total_tokens=20,
    )

    result = _apply_style_profile(
        raw_markdown="Original [SRC0001] text",
        sources=[],
        procedure_name="Test",
        style_profile=make_test_profile(),
        llm=mock_llm,
        model="test",
    )

    assert result is not None
    assert "[SRC0001]" in result


def test_pipeline_returns_original_when_no_profile() -> None:
    """Pipeline should return original markdown when no profile."""
    from procedurewriter.pipeline.run import _apply_style_profile

    result = _apply_style_profile(
        raw_markdown="Original text",
        sources=[],
        procedure_name="Test",
        style_profile=None,
        llm=None,
        model=None,
    )

    assert result == "Original text"
