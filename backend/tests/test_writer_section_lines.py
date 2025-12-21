"""Tests for _normalize_section_lines function in writer module."""
from __future__ import annotations

import pytest

from procedurewriter.pipeline.text_units import CitationValidationError
from procedurewriter.pipeline.writer import _normalize_section_lines


def test_normalize_section_lines_bullets_prefix_and_citation() -> None:
    """Test that bullet formatting and citations are applied correctly."""
    lines = _normalize_section_lines(
        "First line\n- Second [S:SRC0002]\n",
        fmt="bullets",
        fallback_citation="SRC0001",
    )
    assert lines[0].startswith("- ")
    assert "[S:" in lines[0]
    assert lines[1].startswith("- ")
    assert "[S:SRC0002]" in lines[1]


def test_normalize_section_lines_numbered_numbers_and_citation() -> None:
    """Test that numbered formatting and citations are applied correctly."""
    lines = _normalize_section_lines(
        "Step A\n2. Step B [S:SRC0002]\n",
        fmt="numbered",
        fallback_citation="SRC0001",
    )
    assert lines[0].startswith("1. ")
    assert "[S:" in lines[0]
    assert lines[1].startswith("2. ")
    assert "[S:SRC0002]" in lines[1]


def test_normalize_section_lines_preserves_multi_sentence_lines() -> None:
    """
    Lines with multiple sentences are preserved as-is.

    This is intentional design - the function keeps each LLM line as one unit
    to preserve the natural flow the LLM intended. Sentence splitting was
    explicitly removed to maintain content coherence.
    """
    lines = _normalize_section_lines(
        "Hvis der ikke er effekt. Overvej escalation. [S:SRC0002]\n",
        fmt="bullets",
        fallback_citation="SRC0001",
    )
    # The function intentionally keeps multi-sentence lines as one unit
    assert len(lines) == 1
    assert "[S:SRC0002]" in lines[0]
    assert "Hvis der ikke er effekt" in lines[0]
    assert "Overvej escalation" in lines[0]


def test_normalize_section_lines_preserves_abbreviations() -> None:
    """
    Abbreviations like f.eks. are preserved within lines.

    Since sentence splitting is disabled, abbreviations are naturally
    preserved without special handling.
    """
    lines = _normalize_section_lines(
        "Giv systemisk steroid (f.eks. prednisolon 50 mg). Monitorér tæt. [S:SRC0001]\n",
        fmt="bullets",
        fallback_citation="SRC0001",
    )
    # The function intentionally keeps multi-sentence lines as one unit
    assert len(lines) == 1
    assert "f.eks. prednisolon" in lines[0]
    assert "[S:SRC0001]" in lines[0]


def test_normalize_section_lines_strict_disallows_missing_citations() -> None:
    """Strict mode should raise when citations are missing and fallback is disabled."""
    with pytest.raises(CitationValidationError):
        _normalize_section_lines(
            "Mangler citation.\n",
            fmt="bullets",
            fallback_citation="SRC0001",
            strict_mode=True,
            allow_fallback_citations=False,
        )


def test_normalize_section_lines_no_fallback_when_disabled_non_strict() -> None:
    """Non-strict mode should not inject fallback citations when disabled."""
    lines = _normalize_section_lines(
        "Mangler citation.\n",
        fmt="bullets",
        fallback_citation="SRC0001",
        strict_mode=False,
        allow_fallback_citations=False,
    )
    assert "[S:" not in lines[0]
