"""Templates API router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from procedurewriter.settings import settings
from procedurewriter.templates import (
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
    name: str
    description: str | None = None
    config: dict[str, Any]


class UpdateTemplateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    config: dict[str, Any] | None = None


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

    template_id = create_template(
        settings.db_path,
        name=request.name,
        description=request.description,
        config=config,
    )

    return {"template_id": template_id}


@router.put("/{template_id}")
def api_update_template(template_id: str, request: UpdateTemplateRequest) -> dict[str, Any]:
    """Update a template."""
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


@router.delete("/{template_id}")
def api_delete_template(template_id: str) -> dict[str, Any]:
    """Delete a template."""
    try:
        success = delete_template(settings.db_path, template_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if not success:
        raise HTTPException(status_code=404, detail="Template not found")

    return {"status": "deleted"}


@router.post("/{template_id}/set-default")
def api_set_default_template(template_id: str) -> dict[str, Any]:
    """Set a template as the default."""
    success = set_default_template(settings.db_path, template_id)
    if not success:
        raise HTTPException(status_code=404, detail="Template not found")

    return {"status": "default_set"}
