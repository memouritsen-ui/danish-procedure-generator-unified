"""Templates API router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from procedurewriter.settings import settings
from procedurewriter.templates import (
    DuplicateTemplateNameError,
    SectionConfig,
    TemplateConfig,
    create_template,
    delete_template,
    get_template,
    list_templates,
    set_default_template,
    update_template,
)

router = APIRouter(prefix="/api/templates", tags=["templates"])


# --- Request/Response Models ---


class CreateTemplateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100, pattern=r"^[\w\s\-æøåÆØÅ]+$")
    description: str | None = Field(default=None, max_length=500)
    config: dict[str, Any]

    @field_validator("config")
    @classmethod
    def validate_config_keys(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Validate that all config keys are <= 100 characters."""
        for key in v:
            if len(key) > 100:
                raise ValueError(f"Config key '{key[:50]}...' exceeds max length of 100 characters")
        return v


class UpdateTemplateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100, pattern=r"^[\w\s\-æøåÆØÅ]+$")
    description: str | None = Field(default=None, max_length=500)
    config: dict[str, Any] | None = None

    @field_validator("config")
    @classmethod
    def validate_config_keys(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        """Validate that all config keys are <= 100 characters."""
        if v is None:
            return v
        for key in v:
            if len(key) > 100:
                raise ValueError(f"Config key '{key[:50]}...' exceeds max length of 100 characters")
        return v


# --- Template Endpoints ---


@router.get("")
def api_list_templates() -> dict[str, Any]:
    """List all available templates."""
    templates = list_templates(settings.db_path)
    return {
        "templates": [
            {
                "template_id": t.template_id,
                "name": t.name,
                "description": t.description,
                "is_default": t.is_default,
                "is_system": t.is_system,
                "section_count": len(t.config.sections),
            }
            for t in templates
        ]
    }


@router.get("/{template_id}")
def api_get_template(template_id: str) -> dict[str, Any]:
    """Get a specific template with full config."""
    template = get_template(settings.db_path, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return {
        "template_id": template.template_id,
        "name": template.name,
        "description": template.description,
        "is_default": template.is_default,
        "is_system": template.is_system,
        "created_at_utc": template.created_at_utc,
        "updated_at_utc": template.updated_at_utc,
        "config": {
            "title_prefix": template.config.title_prefix,
            "sections": [
                {"heading": s.heading, "format": s.format, "bundle": s.bundle}
                for s in template.config.sections
            ],
        },
    }


@router.post("")
def api_create_template(request: CreateTemplateRequest) -> dict[str, Any]:
    """Create a new template."""
    config = TemplateConfig(
        title_prefix=request.config.get("title_prefix", "Procedure"),
        sections=[
            SectionConfig(
                heading=s["heading"],
                format=s.get("format", "bullets"),
                bundle=s.get("bundle", "action"),
            )
            for s in request.config.get("sections", [])
        ],
    )

    if not config.sections:
        raise HTTPException(status_code=400, detail="Template must have at least one section")

    try:
        template_id = create_template(
            settings.db_path,
            name=request.name,
            description=request.description,
            config=config,
        )
    except DuplicateTemplateNameError as e:
        # R5-008: Return 409 Conflict for duplicate names
        raise HTTPException(status_code=409, detail=str(e)) from e

    return {"template_id": template_id}


@router.patch("/{template_id}")
def api_update_template(template_id: str, request: UpdateTemplateRequest) -> dict[str, Any]:
    """Partially update a template.

    R5-009: Uses PATCH for partial updates per REST conventions.
    """
    config = None
    if request.config:
        config = TemplateConfig(
            title_prefix=request.config.get("title_prefix", "Procedure"),
            sections=[
                SectionConfig(
                    heading=s["heading"],
                    format=s.get("format", "bullets"),
                    bundle=s.get("bundle", "action"),
                )
                for s in request.config.get("sections", [])
            ],
        )

    try:
        success = update_template(
            settings.db_path,
            template_id,
            name=request.name,
            description=request.description,
            config=config,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if not success:
        raise HTTPException(status_code=404, detail="Template not found")

    return {"status": "updated"}


@router.delete("/{template_id}", status_code=204)
def api_delete_template(template_id: str) -> None:
    """Delete a template.

    Returns 204 No Content on success per REST conventions (R5-007).
    """
    try:
        success = delete_template(settings.db_path, template_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if not success:
        raise HTTPException(status_code=404, detail="Template not found")

    return None


@router.post("/{template_id}/set-default")
def api_set_default_template(template_id: str) -> dict[str, Any]:
    """Set a template as the default."""
    success = set_default_template(settings.db_path, template_id)
    if not success:
        raise HTTPException(status_code=404, detail="Template not found")

    return {"status": "default_set"}
