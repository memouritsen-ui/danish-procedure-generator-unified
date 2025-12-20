"""Tests for StyleProfile model."""
from __future__ import annotations

import pytest

from procedurewriter.models.style_profile import StyleProfile, StyleProfileCreate


def test_style_profile_from_db_dict() -> None:
    """Create StyleProfile from database dict."""
    db_dict = {
        "id": "abc-123",
        "name": "Test Style",
        "description": "A test style",
        "is_default": True,
        "created_at_utc": "2025-01-01T00:00:00+00:00",
        "updated_at_utc": "2025-01-01T00:00:00+00:00",
        "tone_config": {
            "tone_description": "Formal",
            "target_audience": "Doctors",
            "detail_level": "comprehensive",
        },
        "structure_config": {
            "section_order": ["a", "b"],
            "include_clinical_pearls": True,
            "include_evidence_badges": False,
        },
        "formatting_config": {
            "heading_style": "numbered",
            "list_style": "bullets",
            "citation_style": "superscript",
        },
        "visual_config": {
            "color_scheme": "blue",
            "safety_box_style": "yellow",
        },
        "original_prompt": "Write formally",
    }

    profile = StyleProfile.from_db_dict(db_dict)

    assert profile.id == "abc-123"
    assert profile.name == "Test Style"
    assert profile.tone_description == "Formal"
    assert profile.target_audience == "Doctors"
    assert profile.include_clinical_pearls is True
    assert profile.heading_style == "numbered"


def test_style_profile_to_db_dict() -> None:
    """Convert StyleProfile to database dict."""
    profile = StyleProfile(
        id="abc-123",
        name="Test",
        description=None,
        is_default=False,
        tone_description="Casual",
        target_audience="Students",
        detail_level="concise",
        section_order=["x"],
        include_clinical_pearls=False,
        include_evidence_badges=True,
        heading_style="unnumbered",
        list_style="prose",
        citation_style="inline",
        color_scheme="gray",
        safety_box_style="red",
        original_prompt=None,
    )

    db_dict = profile.to_db_dict()

    assert db_dict["name"] == "Test"
    assert db_dict["tone_config"]["tone_description"] == "Casual"
    assert db_dict["structure_config"]["section_order"] == ["x"]


def test_style_profile_create_validation() -> None:
    """StyleProfileCreate validates required fields."""
    # Valid creation
    create = StyleProfileCreate(
        name="Valid",
        tone_description="Tone",
        target_audience="Audience",
        detail_level="moderate",
    )
    assert create.name == "Valid"

    # Missing required field should raise
    with pytest.raises(ValueError):
        StyleProfileCreate(name="")  # Empty name
