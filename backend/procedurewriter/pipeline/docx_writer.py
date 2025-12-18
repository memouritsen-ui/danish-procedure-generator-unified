"""DOCX Writer with template-based customization.

Generates procedure documents with configurable structure, styling, and content options.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

from procedurewriter.config_store import load_yaml
from procedurewriter.pipeline.types import SourceRecord

_citation_tag_re = re.compile(r"\[S:[^\]]+\]")


def load_docx_template(template_path: Path | None = None) -> dict[str, Any]:
    """Load DOCX template configuration.

    Args:
        template_path: Path to docx_template.yaml. If None, uses defaults.

    Returns:
        Template configuration dictionary
    """
    if template_path and template_path.exists():
        config = load_yaml(template_path)
        if isinstance(config, dict):
            return config

    # Return default configuration
    return {
        "structure": {
            "sections": [
                {"id": "indikation", "heading": "Indikation", "visible": True, "format": "bullets"},
                {"id": "kontraindikation", "heading": "Kontraindikation", "visible": True, "format": "bullets"},
                {"id": "udstyr", "heading": "Udstyr", "visible": True, "format": "bullets"},
                {"id": "forberedelse", "heading": "Forberedelse", "visible": True, "format": "numbered"},
                {"id": "procedure", "heading": "Procedure", "visible": True, "format": "numbered"},
                {"id": "sikkerhedsboks", "heading": "Sikkerhedsboks", "visible": True, "format": "safety_box"},
                {"id": "komplikationer", "heading": "Komplikationer", "visible": True, "format": "bullets"},
                {"id": "efterbehandling", "heading": "Efterbehandling", "visible": True, "format": "bullets"},
                {"id": "dokumentation", "heading": "Dokumentation", "visible": True, "format": "bullets"},
                {"id": "referencer", "heading": "Referencer", "visible": True, "format": "references"},
            ]
        },
        "styling": {
            "fonts": {
                "body": {"family": "Calibri", "size": 11},
                "heading1": {"family": "Calibri", "size": 16, "bold": True},
                "heading2": {"family": "Calibri", "size": 14, "bold": True},
            },
            "colors": {
                "heading1": "#003366",
                "heading2": "#003366",
                "body": "#000000",
                "citation": "#6e6e6e",
                "safety_box_background": "#FFF2CC",
            },
        },
        "content": {
            "citations": {"style": "superscript", "size": 8, "show_references": True},
            "evidence_badges": {"show_in_text": False, "show_in_references": True},
            "audit_trail": {"show": True, "abbreviated_hash": True},
            "page_numbers": {"show": True, "format": "Side X af Y"},
        },
    }


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def _apply_font_style(run: Any, config: dict[str, Any], style_name: str = "body") -> None:
    """Apply font styling from template config."""
    fonts = config.get("styling", {}).get("fonts", {})
    font_config = fonts.get(style_name, fonts.get("body", {}))

    if "family" in font_config:
        run.font.name = font_config["family"]
    if "size" in font_config:
        run.font.size = Pt(font_config["size"])
    if font_config.get("bold"):
        run.font.bold = True
    if font_config.get("italic"):
        run.font.italic = True


def _apply_heading_color(paragraph: Any, config: dict[str, Any], level: int) -> None:
    """Apply heading color from template config."""
    colors = config.get("styling", {}).get("colors", {})
    color_key = f"heading{level}"
    hex_color = colors.get(color_key, "#003366")

    for run in paragraph.runs:
        r, g, b = _hex_to_rgb(hex_color)
        run.font.color.rgb = RGBColor(r, g, b)


def write_procedure_docx(
    *,
    markdown_text: str,
    sources: list[SourceRecord],
    output_path: Path,
    run_id: str,
    manifest_hash: str,
    template_path: Path | None = None,
    quality_score: int | None = None,
) -> None:
    """Write procedure document with template-based customization.

    Args:
        markdown_text: Procedure content in markdown format
        sources: List of source records for references
        output_path: Path to save the DOCX file
        run_id: Unique run identifier
        manifest_hash: SHA256 hash of the manifest
        template_path: Optional path to docx_template.yaml
        quality_score: Optional quality score (1-10)
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load template configuration
    config = load_docx_template(template_path)

    doc: Any = Document()

    # Apply document margins
    margins = config.get("styling", {}).get("margins", {})
    for section in doc.sections:
        section.top_margin = Inches(margins.get("top", 1.0))
        section.bottom_margin = Inches(margins.get("bottom", 1.0))
        section.left_margin = Inches(margins.get("left", 1.0))
        section.right_margin = Inches(margins.get("right", 1.0))

    # Add branding/logo if configured
    branding = config.get("styling", {}).get("branding", {})
    logo_placement = branding.get("logo_placement", "none")
    logo_path = branding.get("logo_path", "")

    if logo_placement == "header" and logo_path and Path(logo_path).exists():
        header = doc.sections[0].header
        p = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
        run = p.add_run()
        run.add_picture(logo_path, width=Inches(branding.get("logo_width", 1.5)))

    # Render markdown content
    _render_markdown_with_template(doc, markdown_text, config)

    # Add references section if configured
    content_config = config.get("content", {})
    citations_config = content_config.get("citations", {})
    if citations_config.get("show_references", True):
        doc.add_page_break()
        ref_heading = doc.add_heading("Referencer", level=1)
        _apply_heading_color(ref_heading, config, 1)

        evidence_badges = content_config.get("evidence_badges", {})
        show_badges = evidence_badges.get("show_in_references", True)

        for src in sources:
            parts: list[str] = []
            if src.title:
                parts.append(src.title)
            if src.year:
                parts.append(str(src.year))
            if src.url:
                parts.append(src.url)
            if src.doi:
                parts.append(f"DOI: {src.doi}")
            if src.pmid:
                parts.append(f"PMID: {src.pmid}")

            p = doc.add_paragraph()
            rid = p.add_run(f"[{src.source_id}] ")
            rid.bold = True
            p.add_run(" — ".join(parts))

            # Add evidence badge if configured
            if show_badges and src.extra:
                badge = src.extra.get("evidence_badge")
                badge_color = src.extra.get("evidence_badge_color")
                if badge:
                    badge_run = p.add_run(f" [{badge}]")
                    badge_run.font.size = Pt(8)
                    if badge_color:
                        r, g, b = _hex_to_rgb(badge_color)
                        badge_run.font.color.rgb = RGBColor(r, g, b)

    # Add footer with audit trail
    audit_config = content_config.get("audit_trail", {})
    if audit_config.get("show", True):
        ts = datetime.now(UTC).replace(microsecond=0).isoformat()
        hash_display = manifest_hash[:8] if audit_config.get("abbreviated_hash", True) else manifest_hash

        footer_parts = [f"run_id={run_id}", f"timestamp_utc={ts}", f"manifest_sha256={hash_display}"]

        # Add quality score if configured
        quality_config = content_config.get("quality_score", {})
        if quality_config.get("show", False) and quality_score is not None:
            footer_parts.append(f"quality_score={quality_score}/10")

        footer_text = " | ".join(footer_parts)

        section = doc.sections[0]
        footer = section.footer
        p = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
        p.text = footer_text
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Add page numbers if configured
    page_config = content_config.get("page_numbers", {})
    if page_config.get("show", True):
        _add_page_numbers(doc, page_config.get("format", "Side X af Y"))

    doc.save(str(output_path))


def _render_markdown_with_template(doc: Any, markdown_text: str, config: dict[str, Any]) -> None:
    """Render markdown content with template-based formatting."""
    current_h2: str | None = None
    safety_lines: list[str] = []

    # Get section visibility settings
    structure = config.get("structure", {})
    sections = structure.get("sections", [])
    section_config = {s["id"]: s for s in sections if isinstance(s, dict)}

    # Get styling colors
    colors = config.get("styling", {}).get("colors", {})
    citation_color = colors.get("citation", "#6e6e6e")
    citation_size = config.get("content", {}).get("citations", {}).get("size", 8)

    def get_section_id(heading: str) -> str | None:
        """Map heading text to section ID."""
        heading_lower = heading.lower().strip()
        for sec in sections:
            if isinstance(sec, dict):
                if sec.get("heading", "").lower() == heading_lower:
                    return sec.get("id")
                if sec.get("id", "").lower() == heading_lower:
                    return sec.get("id")
        return None

    def is_section_visible(section_id: str | None) -> bool:
        """Check if section should be visible."""
        if section_id is None:
            return True
        sec = section_config.get(section_id)
        if sec is None:
            return True
        return sec.get("visible", True)

    def flush_safety_box() -> None:
        nonlocal safety_lines
        if not safety_lines:
            return

        safety_bg = colors.get("safety_box_background", "FFF2CC")
        if safety_bg.startswith("#"):
            safety_bg = safety_bg[1:]

        table = doc.add_table(rows=1, cols=1)
        cell = table.cell(0, 0)
        _shade_cell(cell, fill=safety_bg)
        cell.text = ""
        for item in safety_lines:
            p = cell.add_paragraph(style="List Bullet")
            _add_text_with_citations(p, item, citation_color, citation_size)
        safety_lines = []

    current_section_visible = True

    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue

        if line.startswith("# "):
            flush_safety_box()
            heading_text = line[2:].strip()
            h = doc.add_heading(heading_text, level=0)
            _apply_heading_color(h, config, 1)
            current_h2 = None
            current_section_visible = True

        elif line.startswith("## "):
            flush_safety_box()
            heading_text = line[3:].strip()
            section_id = get_section_id(heading_text)
            current_section_visible = is_section_visible(section_id)

            if current_section_visible:
                current_h2 = heading_text
                h = doc.add_heading(heading_text, level=1)
                _apply_heading_color(h, config, 2)
            else:
                current_h2 = None

        elif line.startswith("### "):
            if not current_section_visible:
                continue
            flush_safety_box()
            heading_text = line[4:].strip()
            h = doc.add_heading(heading_text, level=2)
            _apply_heading_color(h, config, 3)

        elif line.startswith("- "):
            if not current_section_visible:
                continue
            if _in_safety_box(current_h2):
                safety_lines.append(line[2:].strip())
            else:
                p = doc.add_paragraph(style="List Bullet")
                _add_text_with_citations(p, line[2:].strip(), citation_color, citation_size)

        elif _is_numbered_list_item(line):
            if not current_section_visible:
                continue
            body = line.split(".", 1)[1].strip()
            if _in_safety_box(current_h2):
                safety_lines.append(body)
            else:
                p = doc.add_paragraph(style="List Number")
                _add_text_with_citations(p, body, citation_color, citation_size)

        else:
            if not current_section_visible:
                continue
            if _in_safety_box(current_h2):
                safety_lines.append(line.strip())
            else:
                p = doc.add_paragraph()
                _add_text_with_citations(p, line.strip(), citation_color, citation_size)

    flush_safety_box()


def _is_numbered_list_item(line: str) -> bool:
    """Check if line is a numbered list item."""
    if "." not in line:
        return False
    prefix, _rest = line.split(".", 1)
    prefix = prefix.strip()
    return prefix.isdigit()


def _in_safety_box(current_h2: str | None) -> bool:
    """Check if currently in safety box section."""
    return (current_h2 or "").strip().lower() == "sikkerhedsboks"


def _add_text_with_citations(
    paragraph: Any,
    text: str,
    citation_color: str = "#6e6e6e",
    citation_size: int = 8,
) -> None:
    """Add text with styled citation tags."""
    r, g, b = _hex_to_rgb(citation_color)
    pos = 0
    for m in _citation_tag_re.finditer(text):
        if m.start() > pos:
            paragraph.add_run(text[pos:m.start()])
        tag = m.group(0)
        run = paragraph.add_run(tag)
        run.font.superscript = True
        run.font.size = Pt(citation_size)
        run.font.color.rgb = RGBColor(r, g, b)
        pos = m.end()
    if pos < len(text):
        paragraph.add_run(text[pos:])


def _shade_cell(cell: Any, *, fill: str) -> None:
    """Apply background shading to a table cell."""
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def _add_page_numbers(doc: Any, format_string: str = "Side X af Y") -> None:
    """Add page numbers to document footer."""
    section = doc.sections[0]
    footer = section.footer

    # Get or create paragraph
    if footer.paragraphs:
        p = footer.paragraphs[0]
        if p.text:
            # Add a new paragraph for page numbers
            p = footer.add_paragraph()
    else:
        p = footer.add_paragraph()

    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    # Parse format string and add page number fields
    if "X af Y" in format_string or "X of Y" in format_string:
        prefix = format_string.split("X")[0]
        suffix = format_string.split("Y")[-1] if "Y" in format_string else ""

        if prefix:
            p.add_run(prefix)

        # Add PAGE field
        _add_field(p, "PAGE")

        middle = " af " if "af" in format_string else " of "
        p.add_run(middle)

        # Add NUMPAGES field
        _add_field(p, "NUMPAGES")

        if suffix:
            p.add_run(suffix)
    else:
        # Simple page number
        prefix = format_string.replace("X", "").strip()
        if prefix:
            p.add_run(prefix + " ")
        _add_field(p, "PAGE")


def _add_field(paragraph: Any, field_code: str) -> None:
    """Add a Word field (PAGE, NUMPAGES, etc.) to paragraph."""
    run = paragraph.add_run()
    fld_char_begin = OxmlElement("w:fldChar")
    fld_char_begin.set(qn("w:fldCharType"), "begin")
    run._r.append(fld_char_begin)

    instr_text = OxmlElement("w:instrText")
    instr_text.text = field_code
    run._r.append(instr_text)

    fld_char_separate = OxmlElement("w:fldChar")
    fld_char_separate.set(qn("w:fldCharType"), "separate")
    run._r.append(fld_char_separate)

    # Placeholder text
    run._r.append(OxmlElement("w:t"))

    fld_char_end = OxmlElement("w:fldChar")
    fld_char_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_char_end)
