from __future__ import annotations

from procedurewriter.pipeline.writer import _normalize_section_lines


def test_normalize_section_lines_bullets_prefix_and_citation() -> None:
    lines = _normalize_section_lines("First line\n- Second [S:SRC0002]\n", fmt="bullets", fallback_citation="SRC0001")
    assert lines[0].startswith("- ")
    assert "[S:" in lines[0]
    assert lines[1].startswith("- ")
    assert "[S:SRC0002]" in lines[1]


def test_normalize_section_lines_numbered_numbers_and_citation() -> None:
    lines = _normalize_section_lines("Step A\n2. Step B [S:SRC0002]\n", fmt="numbered", fallback_citation="SRC0001")
    assert lines[0].startswith("1. ")
    assert "[S:" in lines[0]
    assert lines[1].startswith("2. ")
    assert "[S:SRC0002]" in lines[1]


def test_normalize_section_lines_splits_multiple_sentences_and_propagates_citations() -> None:
    lines = _normalize_section_lines(
        "Hvis der ikke er effekt. Overvej escalation. [S:SRC0002]\n",
        fmt="bullets",
        fallback_citation="SRC0001",
    )
    assert len(lines) == 2
    assert all("[S:SRC0002]" in x for x in lines)


def test_normalize_section_lines_abbrev_does_not_split_mid_abbreviation() -> None:
    lines = _normalize_section_lines(
        "Giv systemisk steroid (f.eks. prednisolon 50 mg). Monitorér tæt. [S:SRC0001]\n",
        fmt="bullets",
        fallback_citation="SRC0001",
    )
    assert len(lines) == 2
    assert "f.eks. prednisolon" in lines[0]
    assert all("[S:SRC0001]" in x for x in lines)
