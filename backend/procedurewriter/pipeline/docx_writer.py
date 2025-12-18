from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

from procedurewriter.pipeline.types import SourceRecord

_citation_tag_re = re.compile(r"\[S:[^\]]+\]")


def write_procedure_docx(
    *,
    markdown_text: str,
    sources: list[SourceRecord],
    output_path: Path,
    run_id: str,
    manifest_hash: str,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc: Any = Document()
    _render_markdown(doc, markdown_text)

    doc.add_page_break()
    doc.add_heading("Referencer", level=1)
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

    ts = datetime.now(UTC).replace(microsecond=0).isoformat()
    footer_text = f"run_id={run_id} | timestamp_utc={ts} | manifest_sha256={manifest_hash}"
    section = doc.sections[0]
    footer = section.footer
    p = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
    p.text = footer_text

    doc.save(str(output_path))


def _render_markdown(doc: Any, markdown_text: str) -> None:
    current_h2: str | None = None
    safety_lines: list[str] = []

    def flush_safety_box() -> None:
        nonlocal safety_lines
        if not safety_lines:
            return
        table = doc.add_table(rows=1, cols=1)
        cell = table.cell(0, 0)
        _shade_cell(cell, fill="FFF2CC")  # light yellow
        cell.text = ""
        for item in safety_lines:
            p = cell.add_paragraph(style="List Bullet")
            _add_text_with_citations(p, item)
        safety_lines = []

    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if line.startswith("# "):
            flush_safety_box()
            doc.add_heading(line[2:].strip(), level=0)
            current_h2 = None
        elif line.startswith("## "):
            flush_safety_box()
            current_h2 = line[3:].strip()
            doc.add_heading(line[3:].strip(), level=1)
        elif line.startswith("### "):
            flush_safety_box()
            doc.add_heading(line[4:].strip(), level=2)
        elif line.startswith("- "):
            if _in_safety_box(current_h2):
                safety_lines.append(line[2:].strip())
            else:
                p = doc.add_paragraph(style="List Bullet")
                _add_text_with_citations(p, line[2:].strip())
        elif _is_numbered_list_item(line):
            body = line.split(".", 1)[1].strip()
            if _in_safety_box(current_h2):
                safety_lines.append(body)
            else:
                p = doc.add_paragraph(style="List Number")
                _add_text_with_citations(p, body)
        else:
            if _in_safety_box(current_h2):
                safety_lines.append(line.strip())
            else:
                p = doc.add_paragraph()
                _add_text_with_citations(p, line.strip())

    flush_safety_box()


def _is_numbered_list_item(line: str) -> bool:
    if "." not in line:
        return False
    prefix, _rest = line.split(".", 1)
    prefix = prefix.strip()
    return prefix.isdigit()


def _in_safety_box(current_h2: str | None) -> bool:
    return (current_h2 or "").strip().lower() == "sikkerhedsboks"


def _add_text_with_citations(paragraph: Any, text: str) -> None:
    pos = 0
    for m in _citation_tag_re.finditer(text):
        if m.start() > pos:
            paragraph.add_run(text[pos : m.start()])
        tag = m.group(0)
        run = paragraph.add_run(tag)
        run.font.superscript = True
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor(110, 110, 110)
        pos = m.end()
    if pos < len(text):
        paragraph.add_run(text[pos:])


def _shade_cell(cell: Any, *, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)
