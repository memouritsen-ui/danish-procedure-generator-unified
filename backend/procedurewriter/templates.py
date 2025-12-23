"""
Template management system.

Provides CRUD operations for procedure templates.
Templates define the structure and sections for generated procedures.

NO MOCKS - All operations use real database.
"""
import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from procedurewriter.db import _connect


@dataclass
class SectionConfig:
    """Configuration for a single template section."""

    heading: str
    format: str  # "bullets", "numbered", "paragraphs"
    bundle: str  # "action", "explanation", "safety"


@dataclass
class TemplateConfig:
    """Full template configuration."""

    title_prefix: str
    sections: list[SectionConfig]


@dataclass
class Template:
    """Template with metadata."""

    template_id: str
    name: str
    description: str | None
    created_at_utc: str
    updated_at_utc: str
    is_default: bool
    is_system: bool
    config: TemplateConfig


def _parse_config(config_json: str) -> TemplateConfig:
    """Parse JSON config to TemplateConfig."""
    data = json.loads(config_json)
    return TemplateConfig(
        title_prefix=data.get("title_prefix", "Procedure"),
        sections=[
            SectionConfig(
                heading=s["heading"],
                format=s.get("format", "bullets"),
                bundle=s.get("bundle", "action"),
            )
            for s in data.get("sections", [])
        ],
    )


def _serialize_config(config: TemplateConfig) -> str:
    """Serialize TemplateConfig to JSON."""
    return json.dumps(
        {
            "title_prefix": config.title_prefix,
            "sections": [
                {"heading": s.heading, "format": s.format, "bundle": s.bundle}
                for s in config.sections
            ],
        }
    )


def _row_to_template(row: sqlite3.Row) -> Template:
    """Convert database row to Template object."""
    return Template(
        template_id=row["template_id"],
        name=row["name"],
        description=row["description"],
        created_at_utc=row["created_at_utc"],
        updated_at_utc=row["updated_at_utc"],
        is_default=bool(row["is_default"]),
        is_system=bool(row["is_system"]),
        config=_parse_config(row["config_json"]),
    )


def list_templates(db_path: Path) -> list[Template]:
    """List all templates.

    Returns templates ordered by: default first, then alphabetically by name.
    """
    with _connect(db_path) as conn:
        cursor = conn.execute(
            "SELECT * FROM templates ORDER BY is_default DESC, name ASC"
        )
        rows = cursor.fetchall()
    return [_row_to_template(row) for row in rows]


def get_template(db_path: Path, template_id: str) -> Template | None:
    """Get a specific template by ID.

    Args:
        db_path: Path to the database file.
        template_id: The template ID to look up.

    Returns:
        Template if found, None otherwise.
    """
    with _connect(db_path) as conn:
        cursor = conn.execute(
            "SELECT * FROM templates WHERE template_id = ?",
            (template_id,),
        )
        row = cursor.fetchone()

    if not row:
        return None

    return _row_to_template(row)


def get_default_template(db_path: Path) -> Template | None:
    """Get the default template.

    Returns:
        The default template if one exists, None otherwise.
    """
    with _connect(db_path) as conn:
        cursor = conn.execute(
            "SELECT * FROM templates WHERE is_default = TRUE LIMIT 1"
        )
        row = cursor.fetchone()

    if not row:
        return None

    return _row_to_template(row)


class DuplicateTemplateNameError(ValueError):
    """R5-008: Raised when attempting to create a template with a duplicate name."""

    pass


def create_template(
    db_path: Path,
    name: str,
    config: TemplateConfig,
    description: str | None = None,
) -> str:
    """Create a new template.

    Args:
        db_path: Path to the database file.
        name: Display name for the template.
        config: Template configuration with sections.
        description: Optional description.

    Returns:
        The generated template_id.

    Raises:
        DuplicateTemplateNameError: If a template with this name already exists (R5-008).
    """
    template_id = str(uuid.uuid4())[:8]
    now = datetime.utcnow().isoformat() + "Z"

    with _connect(db_path) as conn:
        # R5-008: Check for duplicate name
        existing = conn.execute(
            "SELECT template_id FROM templates WHERE LOWER(name) = LOWER(?)",
            (name,),
        ).fetchone()
        if existing:
            raise DuplicateTemplateNameError(
                f"A template with name '{name}' already exists (id: {existing['template_id']})"
            )

        conn.execute(
            """
            INSERT INTO templates
            (template_id, name, description, created_at_utc, updated_at_utc,
             is_default, is_system, config_json)
            VALUES (?, ?, ?, ?, ?, FALSE, FALSE, ?)
            """,
            (template_id, name, description, now, now, _serialize_config(config)),
        )
        conn.commit()

    return template_id


def update_template(
    db_path: Path,
    template_id: str,
    name: str | None = None,
    description: str | None = None,
    config: TemplateConfig | None = None,
) -> bool:
    """Update a template.

    Args:
        db_path: Path to the database file.
        template_id: The template to update.
        name: New name (if provided).
        description: New description (if provided).
        config: New configuration (if provided).

    Returns:
        True if template was found and updated.

    Raises:
        ValueError: If attempting to modify a system template.
    """
    template = get_template(db_path, template_id)
    if not template:
        return False

    if template.is_system:
        raise ValueError("Cannot modify system templates")

    now = datetime.utcnow().isoformat() + "Z"

    updates = ["updated_at_utc = ?"]
    values: list[Any] = [now]

    if name is not None:
        updates.append("name = ?")
        values.append(name)

    if description is not None:
        updates.append("description = ?")
        values.append(description)

    if config is not None:
        updates.append("config_json = ?")
        values.append(_serialize_config(config))

    values.append(template_id)

    with _connect(db_path) as conn:
        conn.execute(
            f"UPDATE templates SET {', '.join(updates)} WHERE template_id = ?",
            values,
        )
        conn.commit()

    return True


def delete_template(db_path: Path, template_id: str) -> bool:
    """Delete a template.

    Args:
        db_path: Path to the database file.
        template_id: The template to delete.

    Returns:
        True if template was found and deleted.

    Raises:
        ValueError: If attempting to delete a system template.
    """
    template = get_template(db_path, template_id)
    if not template:
        return False

    if template.is_system:
        raise ValueError("Cannot delete system templates")

    with _connect(db_path) as conn:
        conn.execute("DELETE FROM templates WHERE template_id = ?", (template_id,))
        conn.commit()

    return True


def set_default_template(db_path: Path, template_id: str) -> bool:
    """Set a template as the default.

    Clears the default flag on all other templates first.

    Args:
        db_path: Path to the database file.
        template_id: The template to make default.

    Returns:
        True if template was found and set as default.
    """
    template = get_template(db_path, template_id)
    if not template:
        return False

    with _connect(db_path) as conn:
        # Clear existing default
        conn.execute("UPDATE templates SET is_default = FALSE")
        # Set new default
        conn.execute(
            "UPDATE templates SET is_default = TRUE WHERE template_id = ?",
            (template_id,),
        )
        conn.commit()

    return True


def get_template_for_run(db_path: Path, template_id: str | None) -> TemplateConfig:
    """Get template config for a run.

    Resolution order:
    1. If template_id is provided, use that template
    2. Otherwise, use the default template
    3. If no templates exist, use hardcoded fallback

    Args:
        db_path: Path to the database file.
        template_id: Optional specific template to use.

    Returns:
        TemplateConfig to use for the procedure.
    """
    if template_id:
        template = get_template(db_path, template_id)
        if template:
            return template.config

    # Try default template
    default = get_default_template(db_path)
    if default:
        return default.config

    # Fallback to hardcoded default
    return TemplateConfig(
        title_prefix="Procedure",
        sections=[
            SectionConfig("Indikationer", "bullets", "action"),
            SectionConfig("Kontraindikationer", "bullets", "action"),
            SectionConfig("Forberedelse", "bullets", "action"),
            SectionConfig("Udstyr", "bullets", "action"),
            SectionConfig("Fremgangsmåde (trin-for-trin)", "numbered", "action"),
            SectionConfig("Forklaringslag", "paragraphs", "explanation"),
            SectionConfig("Sikkerhedsboks", "bullets", "safety"),
            SectionConfig("Komplikationer", "bullets", "action"),
            SectionConfig("Disposition", "bullets", "action"),
            SectionConfig("Evidens", "bullets", "explanation"),
        ],
    )
