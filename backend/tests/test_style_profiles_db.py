"""Tests for style_profiles database operations."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from procedurewriter.db import (
    init_db,
    create_style_profile,
    get_style_profile,
    list_style_profiles,
    update_style_profile,
    delete_style_profile,
    get_default_style_profile,
    set_default_style_profile,
)


@pytest.fixture
def db_path() -> Path:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.db"
        init_db(path)
        yield path


def test_create_and_get_style_profile(db_path: Path) -> None:
    """Create a style profile and retrieve it."""
    profile_id = create_style_profile(
        db_path=db_path,
        name="Lærebog Formel",
        description="Akademisk stil til medicinstuderende",
        tone_config={
            "tone_description": "Formel akademisk tone med passiv form",
            "target_audience": "Medicinstuderende",
            "detail_level": "comprehensive",
        },
        structure_config={
            "section_order": ["indikation", "kontraindikation", "procedure"],
            "include_clinical_pearls": True,
            "include_evidence_badges": True,
        },
        formatting_config={
            "heading_style": "numbered",
            "list_style": "bullets",
            "citation_style": "superscript",
        },
        visual_config={
            "color_scheme": "professional_blue",
            "safety_box_style": "yellow_background",
        },
        original_prompt="Skriv som en dansk medicinsk lærebog",
    )

    assert profile_id is not None

    profile = get_style_profile(db_path, profile_id)
    assert profile is not None
    assert profile["name"] == "Lærebog Formel"
    assert profile["tone_config"]["target_audience"] == "Medicinstuderende"


def test_list_style_profiles(db_path: Path) -> None:
    """List all style profiles."""
    create_style_profile(
        db_path=db_path,
        name="Style 1",
        tone_config={},
        structure_config={},
        formatting_config={},
        visual_config={},
    )
    create_style_profile(
        db_path=db_path,
        name="Style 2",
        tone_config={},
        structure_config={},
        formatting_config={},
        visual_config={},
    )

    profiles = list_style_profiles(db_path)
    assert len(profiles) == 2


def test_set_default_style_profile(db_path: Path) -> None:
    """Set a profile as default."""
    id1 = create_style_profile(
        db_path=db_path,
        name="Style 1",
        tone_config={},
        structure_config={},
        formatting_config={},
        visual_config={},
    )
    id2 = create_style_profile(
        db_path=db_path,
        name="Style 2",
        tone_config={},
        structure_config={},
        formatting_config={},
        visual_config={},
    )

    set_default_style_profile(db_path, id1)
    default = get_default_style_profile(db_path)
    assert default is not None
    assert default["id"] == id1

    # Setting new default should unset old one
    set_default_style_profile(db_path, id2)
    default = get_default_style_profile(db_path)
    assert default["id"] == id2


def test_delete_style_profile(db_path: Path) -> None:
    """Delete a style profile."""
    profile_id = create_style_profile(
        db_path=db_path,
        name="To Delete",
        tone_config={},
        structure_config={},
        formatting_config={},
        visual_config={},
    )

    delete_style_profile(db_path, profile_id)
    profile = get_style_profile(db_path, profile_id)
    assert profile is None


def test_update_style_profile(db_path: Path) -> None:
    """Update a style profile."""
    profile_id = create_style_profile(
        db_path=db_path,
        name="Original Name",
        tone_config={"tone_description": "Original"},
        structure_config={},
        formatting_config={},
        visual_config={},
    )

    update_style_profile(
        db_path,
        profile_id,
        name="Updated Name",
        tone_config={"tone_description": "Updated"},
    )

    profile = get_style_profile(db_path, profile_id)
    assert profile is not None
    assert profile["name"] == "Updated Name"
    assert profile["tone_config"]["tone_description"] == "Updated"
