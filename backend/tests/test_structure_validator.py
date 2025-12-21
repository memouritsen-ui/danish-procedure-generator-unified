from __future__ import annotations

from procedurewriter.pipeline.structure_validator import validate_required_sections


def test_validate_required_sections_passes_when_present() -> None:
    markdown = """# Title

## Formaal og Maalgruppe
Tekst. [S:SRC0001]

## Indikationer
- Punkt. [S:SRC0001]

## Komplikationer
- Punkt. [S:SRC0001]
"""
    required = ["Formaal og Maalgruppe", "Indikationer", "Komplikationer"]
    result = validate_required_sections(markdown, required_headings=required)

    assert result.is_valid is True
    assert result.missing_headings == []
    assert result.out_of_order_headings == []
    assert result.wrong_level_headings == []


def test_validate_required_sections_detects_missing() -> None:
    markdown = """# Title

## Indikationer
- Punkt. [S:SRC0001]
"""
    required = ["Formaal og Maalgruppe", "Indikationer"]
    result = validate_required_sections(markdown, required_headings=required)

    assert result.is_valid is False
    assert result.missing_headings == ["Formaal og Maalgruppe"]


def test_validate_required_sections_detects_out_of_order() -> None:
    markdown = """# Title

## Indikationer
- Punkt. [S:SRC0001]

## Formaal og Maalgruppe
Tekst. [S:SRC0001]
"""
    required = ["Formaal og Maalgruppe", "Indikationer"]
    result = validate_required_sections(markdown, required_headings=required)

    assert result.is_valid is False
    assert result.out_of_order_headings == ["Indikationer"]


def test_validate_required_sections_detects_wrong_level() -> None:
    markdown = """# Title

### Formaal og Maalgruppe
Tekst. [S:SRC0001]
"""
    required = ["Formaal og Maalgruppe"]
    result = validate_required_sections(markdown, required_headings=required)

    assert result.is_valid is False
    assert result.wrong_level_headings == ["Formaal og Maalgruppe"]
