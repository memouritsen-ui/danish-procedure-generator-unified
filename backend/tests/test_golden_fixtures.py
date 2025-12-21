from __future__ import annotations

from pathlib import Path

from procedurewriter.config_store import load_yaml
from procedurewriter.pipeline.anatomical_requirements import AnatomicalValidator
from procedurewriter.pipeline.citations import validate_citations
from procedurewriter.pipeline.run import _author_guide_outline
from procedurewriter.pipeline.structure_validator import validate_required_sections


def test_pleuradraen_fixture_structure_and_citations() -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "pleuradraen.md"
    markdown = fixture_path.read_text(encoding="utf-8")

    author_guide = load_yaml(Path(__file__).parents[2] / "config" / "author_guide.yaml")
    required_headings = _author_guide_outline(author_guide)

    structure = validate_required_sections(markdown, required_headings=required_headings)
    assert structure.is_valid is True

    validate_citations(markdown, valid_source_ids={"SRC0001", "SRC0002"})


def test_pleuradraen_fixture_anatomy_validation() -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "pleuradraen.md"
    markdown = fixture_path.read_text(encoding="utf-8")

    validator = AnatomicalValidator()
    result = validator.validate("pleuradræn", markdown)
    assert result.is_valid is True
