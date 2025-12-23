"""Style profile management router."""

import html
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from procedurewriter.db import (
    create_style_profile,
    delete_style_profile,
    get_default_style_profile,
    get_style_profile,
    list_style_profiles,
    set_default_style_profile,
    update_style_profile,
)
from procedurewriter.models.style_profile import StyleProfile
from procedurewriter.settings import settings

router = APIRouter(prefix="/api/styles", tags=["styles"])


def _escape_html(value: str | None) -> str | None:
    """R5-012: Escape HTML entities in user-provided text to prevent stored XSS.

    Escapes: < > & " '
    """
    if value is None:
        return None
    return html.escape(value)


class CreateStyleRequest(BaseModel):
    """Request body for creating a style profile."""

    name: str
    description: str | None = None
    tone_description: str = ""
    target_audience: str = ""
    detail_level: str = "moderate"
    section_order: list[str] = []
    include_clinical_pearls: bool = False
    include_evidence_badges: bool = True
    heading_style: str = "numbered"
    list_style: str = "bullets"
    citation_style: str = "superscript"
    color_scheme: str = "professional_blue"
    safety_box_style: str = "yellow_background"
    original_prompt: str | None = None


class UpdateStyleRequest(BaseModel):
    """Request body for updating a style profile."""

    name: str | None = None
    description: str | None = None
    tone_description: str | None = None
    target_audience: str | None = None
    detail_level: str | None = None
    section_order: list[str] | None = None
    include_clinical_pearls: bool | None = None
    include_evidence_badges: bool | None = None
    heading_style: str | None = None
    list_style: str | None = None
    citation_style: str | None = None
    color_scheme: str | None = None
    safety_box_style: str | None = None
    original_prompt: str | None = None


@router.get("")
def api_list_styles() -> list[dict[str, Any]]:
    """List all style profiles."""
    profiles = list_style_profiles(settings.db_path)
    return [StyleProfile.from_db_dict(p).to_db_dict() for p in profiles]


@router.get("/default")
def api_get_default_style() -> dict[str, Any]:
    """Get the default style profile."""
    profile = get_default_style_profile(settings.db_path)
    if profile is None:
        raise HTTPException(status_code=404, detail="No default style profile set")
    return StyleProfile.from_db_dict(profile).to_db_dict()


@router.get("/{style_id}")
def api_get_style(style_id: str) -> dict[str, Any]:
    """Get a specific style profile."""
    profile = get_style_profile(settings.db_path, style_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Style profile {style_id} not found")
    return StyleProfile.from_db_dict(profile).to_db_dict()


@router.post("")
def api_create_style(request: CreateStyleRequest) -> dict[str, Any]:
    """Create a new style profile.

    R5-012: User-provided text fields are HTML-escaped to prevent stored XSS.
    """
    # R5-012: Escape HTML entities in user-provided text fields
    safe_name = _escape_html(request.name) or ""
    safe_description = _escape_html(request.description)
    safe_tone_description = _escape_html(request.tone_description) or ""
    safe_target_audience = _escape_html(request.target_audience) or ""
    safe_original_prompt = _escape_html(request.original_prompt)

    # Construct config dicts from flat fields
    tone_config = {
        "tone_description": safe_tone_description,
        "target_audience": safe_target_audience,
        "detail_level": request.detail_level,
    }
    structure_config = {
        "section_order": request.section_order,
        "include_clinical_pearls": request.include_clinical_pearls,
        "include_evidence_badges": request.include_evidence_badges,
    }
    formatting_config = {
        "heading_style": request.heading_style,
        "list_style": request.list_style,
        "citation_style": request.citation_style,
    }
    visual_config = {
        "color_scheme": request.color_scheme,
        "safety_box_style": request.safety_box_style,
    }

    profile_id = create_style_profile(
        settings.db_path,
        name=safe_name,
        description=safe_description,
        tone_config=tone_config,
        structure_config=structure_config,
        formatting_config=formatting_config,
        visual_config=visual_config,
        original_prompt=safe_original_prompt,
    )
    profile = get_style_profile(settings.db_path, profile_id)
    return StyleProfile.from_db_dict(profile).to_db_dict()


@router.put("/{style_id}")
def api_update_style(style_id: str, request: UpdateStyleRequest) -> dict[str, Any]:
    """Update a style profile.

    R5-012: User-provided text fields are HTML-escaped to prevent stored XSS.
    """
    # Get existing profile
    existing = get_style_profile(settings.db_path, style_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Style profile {style_id} not found")

    # Build updates dict
    updates: dict[str, Any] = {}

    # R5-012: Direct fields with HTML escaping
    if request.name is not None:
        updates["name"] = _escape_html(request.name)
    if request.description is not None:
        updates["description"] = _escape_html(request.description)
    if request.original_prompt is not None:
        updates["original_prompt"] = _escape_html(request.original_prompt)

    # R5-012: Tone config updates with HTML escaping
    tone_updates = {}
    if request.tone_description is not None:
        tone_updates["tone_description"] = _escape_html(request.tone_description)
    if request.target_audience is not None:
        tone_updates["target_audience"] = _escape_html(request.target_audience)
    if request.detail_level is not None:
        tone_updates["detail_level"] = request.detail_level
    if tone_updates:
        existing_tone = existing.get("tone_config", {})
        if isinstance(existing_tone, str):
            import json
            existing_tone = json.loads(existing_tone)
        updates["tone_config"] = {**existing_tone, **tone_updates}

    # Structure config updates
    structure_updates = {}
    if request.section_order is not None:
        structure_updates["section_order"] = request.section_order
    if request.include_clinical_pearls is not None:
        structure_updates["include_clinical_pearls"] = request.include_clinical_pearls
    if request.include_evidence_badges is not None:
        structure_updates["include_evidence_badges"] = request.include_evidence_badges
    if structure_updates:
        existing_structure = existing.get("structure_config", {})
        if isinstance(existing_structure, str):
            import json
            existing_structure = json.loads(existing_structure)
        updates["structure_config"] = {**existing_structure, **structure_updates}

    # Formatting config updates
    formatting_updates = {}
    if request.heading_style is not None:
        formatting_updates["heading_style"] = request.heading_style
    if request.list_style is not None:
        formatting_updates["list_style"] = request.list_style
    if request.citation_style is not None:
        formatting_updates["citation_style"] = request.citation_style
    if formatting_updates:
        existing_formatting = existing.get("formatting_config", {})
        if isinstance(existing_formatting, str):
            import json
            existing_formatting = json.loads(existing_formatting)
        updates["formatting_config"] = {**existing_formatting, **formatting_updates}

    # Visual config updates
    visual_updates = {}
    if request.color_scheme is not None:
        visual_updates["color_scheme"] = request.color_scheme
    if request.safety_box_style is not None:
        visual_updates["safety_box_style"] = request.safety_box_style
    if visual_updates:
        existing_visual = existing.get("visual_config", {})
        if isinstance(existing_visual, str):
            import json
            existing_visual = json.loads(existing_visual)
        updates["visual_config"] = {**existing_visual, **visual_updates}

    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    update_style_profile(settings.db_path, style_id, **updates)

    profile = get_style_profile(settings.db_path, style_id)
    return StyleProfile.from_db_dict(profile).to_db_dict()


@router.delete("/{style_id}", status_code=204)
def api_delete_style(style_id: str) -> None:
    """Delete a style profile.

    Returns 204 No Content on success per REST conventions (R5-007).
    """
    success = delete_style_profile(settings.db_path, style_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Style profile {style_id} not found")
    return None


@router.post("/{style_id}/set-default")
def api_set_default_style(style_id: str) -> dict[str, Any]:
    """Set a style profile as the default."""
    profile = get_style_profile(settings.db_path, style_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Style profile {style_id} not found")

    set_default_style_profile(settings.db_path, style_id)

    # Fetch updated profile
    profile = get_style_profile(settings.db_path, style_id)
    return StyleProfile.from_db_dict(profile).to_db_dict()
