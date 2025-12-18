from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from docx import Document
from pypdf import PdfReader

_whitespace_re = re.compile(r"[ \t]+")
_many_newlines_re = re.compile(r"\n{3,}")


def _clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _whitespace_re.sub(" ", text)
    text = _many_newlines_re.sub("\n\n", text)
    return text.strip()


def normalize_html(raw_html: bytes) -> str:
    soup = BeautifulSoup(raw_html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    for tag in soup.find_all(["nav", "header", "footer", "aside"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    return _clean_text(text)


def extract_pdf_pages(pdf_path: Path) -> list[str]:
    reader = PdfReader(str(pdf_path))
    pages: list[str] = []
    for page in reader.pages:
        t = page.extract_text() or ""
        pages.append(_clean_text(t))
    return pages


def normalize_pdf_pages(pages: list[str]) -> str:
    return _clean_text("\n\n".join(p for p in pages if p))


def extract_docx_blocks(docx_path: Path) -> list[dict[str, Any]]:
    doc = Document(str(docx_path))
    blocks: list[dict[str, Any]] = []
    for i, p in enumerate(doc.paragraphs):
        text = (p.text or "").strip()
        if not text:
            continue
        style = p.style.name if p.style is not None else ""
        kind, level = _docx_kind_and_level(style, text)
        blocks.append(
            {
                "i": i,
                "kind": kind,
                "level": level,
                "style": style,
                "text": _clean_text(text),
            }
        )
    return blocks


def normalize_docx_blocks(blocks: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for b in blocks:
        text = str(b.get("text") or "").strip()
        if not text:
            continue
        kind = str(b.get("kind") or "paragraph")
        if kind == "heading":
            level = int(b.get("level") or 1)
            prefix = "#" * max(1, min(level, 6))
            lines.append(f"{prefix} {text}")
        elif kind == "bullet":
            body = _strip_leading_bullets(text)
            lines.append(f"- {body}".strip())
        elif kind == "numbered":
            body = re.sub(r"^\\d+[.)]\\s+", "", text.lstrip())
            lines.append(f"1. {body}".strip())
        else:
            lines.append(text)
        lines.append("")
    return _clean_text("\n".join(lines))


def normalize_pubmed(title: str | None, abstract: str | None, journal: str | None, year: int | None) -> str:
    parts: list[str] = []
    if title:
        parts.append(title.strip())
    if journal or year:
        meta = " ".join(x for x in [journal, str(year) if year else None] if x)
        parts.append(meta.strip())
    if abstract:
        parts.append(abstract.strip())
    return _clean_text("\n\n".join(parts))


def _docx_kind_and_level(style: str, text: str) -> tuple[str, int | None]:
    s = (style or "").strip()
    lower = s.lower()
    if lower in {"title"}:
        return "heading", 1
    if lower.startswith("heading"):
        m = re.match(r"(?i)^heading\\s+(\\d+)$", s.strip())
        if m and m.group(1).isdigit():
            return "heading", int(m.group(1))
        return "heading", 1
    if "list bullet" in lower:
        return "bullet", None
    if "list number" in lower:
        return "numbered", None
    stripped = text.lstrip()
    if stripped.startswith(("•", "-", "–", "*")):
        return "bullet", None
    if re.match(r"^\\d+[.)]\\s+", stripped):
        return "numbered", None
    return "paragraph", None


def _strip_leading_bullets(text: str) -> str:
    s = text.lstrip()
    while s and s[0] in {"•", "-", "–", "*"}:
        s = s[1:].lstrip()
    return s
