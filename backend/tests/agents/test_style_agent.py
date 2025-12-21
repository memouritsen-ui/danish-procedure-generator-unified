"""Tests for StyleAgent."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from procedurewriter.agents.style_agent import (
    StyleAgent,
    StyleInput,
    StyleOutput,
    StyleValidationError,
)
from procedurewriter.models.style_profile import StyleProfile
from procedurewriter.llm.providers import LLMResponse


def make_test_profile() -> StyleProfile:
    return StyleProfile(
        id="test-id",
        name="Test",
        description=None,
        is_default=False,
        tone_description="Formel akademisk tone",
        target_audience="Læger",
        detail_level="comprehensive",
        section_order=[],
        include_clinical_pearls=False,
        include_evidence_badges=True,
        heading_style="numbered",
        list_style="bullets",
        citation_style="superscript",
        color_scheme="blue",
        safety_box_style="yellow",
        original_prompt=None,
    )


def test_style_agent_preserves_citations() -> None:
    """StyleAgent must preserve all citations."""
    mock_llm = MagicMock()
    mock_llm.chat_completion.return_value = LLMResponse(
        content="Poleret tekst med [SRC0001] og [SRC0002] bevaret.",
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        model="test",
    )

    agent = StyleAgent(llm=mock_llm, model="test")
    input_data = StyleInput(
        procedure_title="Test",
        raw_markdown="Original tekst med [SRC0001] og [SRC0002].",
        sources=[],
        style_profile=make_test_profile(),
    )

    result = agent.execute(input_data)

    assert result.output.success is True
    assert "[SRC0001]" in result.output.polished_markdown
    assert "[SRC0002]" in result.output.polished_markdown


def test_style_agent_fails_on_missing_citations() -> None:
    """StyleAgent should fallback to original if LLM drops citations after retries."""
    mock_llm = MagicMock()
    # LLM response is missing [SRC0002]
    mock_llm.chat_completion.return_value = LLMResponse(
        content="Poleret tekst med [SRC0001] men mangler den anden.",
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        model="test",
    )

    agent = StyleAgent(llm=mock_llm, model="test")
    input_data = StyleInput(
        procedure_title="Test",
        raw_markdown="Original tekst med [SRC0001] og [SRC0002].",
        sources=[],
        style_profile=make_test_profile(),
    )

    result = agent.execute(input_data)

    # Should succeed but add warning about missing citations
    assert result.output.success is True
    assert "[SRC0002]" in result.output.polished_markdown  # Missing citation added
    assert len(result.output.warnings) > 0  # Warning about added citations


def test_style_agent_applies_tone() -> None:
    """StyleAgent should include tone in prompt."""
    mock_llm = MagicMock()
    mock_llm.chat_completion.return_value = LLMResponse(
        content="Poleret output",
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        model="test",
    )

    agent = StyleAgent(llm=mock_llm, model="test")
    profile = make_test_profile()
    profile.tone_description = "VERY_SPECIFIC_TONE"

    input_data = StyleInput(
        procedure_title="Test",
        raw_markdown="Text",
        sources=[],
        style_profile=profile,
    )

    agent.execute(input_data)

    # Check that LLM was called with tone in prompt
    call_args = mock_llm.chat_completion.call_args
    messages = call_args.kwargs.get("messages", call_args.args[0] if call_args.args else [])
    prompt_content = str(messages)
    assert "VERY_SPECIFIC_TONE" in prompt_content
