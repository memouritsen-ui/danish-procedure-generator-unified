"""StyleProfile model for LLM-powered document formatting."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StyleProfile:
    """Complete style profile for document generation."""

    id: str
    name: str
    description: str | None
    is_default: bool

    # Tone & Content
    tone_description: str
    target_audience: str
    detail_level: str  # "concise" | "moderate" | "comprehensive"

    # Structure
    section_order: list[str] = field(default_factory=list)
    include_clinical_pearls: bool = False
    include_evidence_badges: bool = True

    # Formatting
    heading_style: str = "numbered"  # "numbered" | "unnumbered"
    list_style: str = "bullets"  # "bullets" | "numbered" | "prose"
    citation_style: str = "superscript"  # "superscript" | "inline"

    # Visual
    color_scheme: str = "professional_blue"
    safety_box_style: str = "yellow_background"

    # Meta
    original_prompt: str | None = None

    @classmethod
    def from_db_dict(cls, data: dict[str, Any]) -> StyleProfile:
        """Create from database dictionary."""
        tone = data.get("tone_config", {})
        structure = data.get("structure_config", {})
        formatting = data.get("formatting_config", {})
        visual = data.get("visual_config", {})

        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description"),
            is_default=data.get("is_default", False),
            tone_description=tone.get("tone_description", ""),
            target_audience=tone.get("target_audience", ""),
            detail_level=tone.get("detail_level", "moderate"),
            section_order=structure.get("section_order", []),
            include_clinical_pearls=structure.get("include_clinical_pearls", False),
            include_evidence_badges=structure.get("include_evidence_badges", True),
            heading_style=formatting.get("heading_style", "numbered"),
            list_style=formatting.get("list_style", "bullets"),
            citation_style=formatting.get("citation_style", "superscript"),
            color_scheme=visual.get("color_scheme", "professional_blue"),
            safety_box_style=visual.get("safety_box_style", "yellow_background"),
            original_prompt=data.get("original_prompt"),
        )

    def to_db_dict(self) -> dict[str, Any]:
        """Convert to database dictionary format."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "is_default": self.is_default,
            "tone_config": {
                "tone_description": self.tone_description,
                "target_audience": self.target_audience,
                "detail_level": self.detail_level,
            },
            "structure_config": {
                "section_order": self.section_order,
                "include_clinical_pearls": self.include_clinical_pearls,
                "include_evidence_badges": self.include_evidence_badges,
            },
            "formatting_config": {
                "heading_style": self.heading_style,
                "list_style": self.list_style,
                "citation_style": self.citation_style,
            },
            "visual_config": {
                "color_scheme": self.color_scheme,
                "safety_box_style": self.safety_box_style,
            },
            "original_prompt": self.original_prompt,
        }


@dataclass
class StyleProfileSummary:
    """Summary view of a style profile for listing."""

    id: str
    name: str
    description: str | None
    is_default: bool

    @classmethod
    def from_db_dict(cls, data: dict[str, Any]) -> StyleProfileSummary:
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description"),
            is_default=data.get("is_default", False),
        )


@dataclass
class StyleProfileCreate:
    """Input for creating a new style profile."""

    name: str
    tone_description: str = ""
    target_audience: str = ""
    detail_level: str = "moderate"
    description: str | None = None
    section_order: list[str] = field(default_factory=list)
    include_clinical_pearls: bool = False
    include_evidence_badges: bool = True
    heading_style: str = "numbered"
    list_style: str = "bullets"
    citation_style: str = "superscript"
    color_scheme: str = "professional_blue"
    safety_box_style: str = "yellow_background"
    original_prompt: str | None = None

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("name is required")
