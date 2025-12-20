"""Tests for StyleParserAgent."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from procedurewriter.agents.style_parser_agent import (
    StyleParserAgent,
    StyleParserInput,
)
from procedurewriter.llm.providers import LLMResponse


def test_parse_natural_language_to_profile() -> None:
    """Parse natural language description to structured profile."""
    mock_llm = MagicMock()
    mock_llm.chat_completion.return_value = LLMResponse(
        content=json.dumps({
            "name": "Lærebog Stil",
            "tone_description": "Formel akademisk tone med passiv form",
            "target_audience": "Medicinstuderende",
            "detail_level": "comprehensive",
            "include_clinical_pearls": True,
            "include_evidence_badges": True,
            "heading_style": "numbered",
            "list_style": "bullets",
            "citation_style": "superscript",
            "color_scheme": "professional_blue",
            "safety_box_style": "yellow_background",
        }),
        input_tokens=100,
        output_tokens=200,
        total_tokens=300,
        model="test",
    )

    agent = StyleParserAgent(llm=mock_llm, model="test")
    input_data = StyleParserInput(
        procedure_title="",
        natural_language_prompt="Skriv som en dansk medicinsk lærebog til medicinstuderende. Formel tone.",
    )

    result = agent.execute(input_data)

    assert result.output.success is True
    assert result.output.parsed_profile is not None
    assert result.output.parsed_profile.tone_description == "Formel akademisk tone med passiv form"


def test_parse_handles_invalid_json() -> None:
    """Parser should handle invalid JSON from LLM."""
    mock_llm = MagicMock()
    mock_llm.chat_completion.return_value = LLMResponse(
        content="This is not valid JSON at all",
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        model="test",
    )

    agent = StyleParserAgent(llm=mock_llm, model="test")
    input_data = StyleParserInput(
        procedure_title="",
        natural_language_prompt="Invalid prompt",
    )

    result = agent.execute(input_data)

    assert result.output.success is False
    assert result.output.error is not None


def test_parse_handles_json_in_code_block() -> None:
    """Parser should extract JSON from markdown code blocks."""
    mock_llm = MagicMock()
    mock_llm.chat_completion.return_value = LLMResponse(
        content='''Here is the profile:

```json
{
    "name": "Klinisk Stil",
    "tone_description": "Klinisk og præcis",
    "target_audience": "Læger",
    "detail_level": "moderate"
}
```
''',
        input_tokens=100,
        output_tokens=150,
        total_tokens=250,
        model="test",
    )

    agent = StyleParserAgent(llm=mock_llm, model="test")
    input_data = StyleParserInput(
        procedure_title="",
        natural_language_prompt="Klinisk stil til læger",
    )

    result = agent.execute(input_data)

    assert result.output.success is True
    assert result.output.parsed_profile is not None
    assert result.output.parsed_profile.name == "Klinisk Stil"
