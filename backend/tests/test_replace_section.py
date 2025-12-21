from __future__ import annotations

import pytest

from procedurewriter.pipeline.run import SectionNotFoundError, _replace_section


def test_replace_section_strict_raises_when_missing() -> None:
    """Strict mode should raise when the target section is missing."""
    md = "## A\nIndhold A\n"
    with pytest.raises(SectionNotFoundError):
        _replace_section(
            md,
            heading="B",
            new_lines=["Nyt indhold"],
            strict_mode=True,
        )


def test_replace_section_non_strict_appends() -> None:
    """Non-strict mode should append missing sections at the end."""
    md = "## A\nIndhold A\n"
    updated = _replace_section(
        md,
        heading="B",
        new_lines=["Nyt indhold"],
        strict_mode=False,
    )
    assert "## B" in updated
    assert "Nyt indhold" in updated
