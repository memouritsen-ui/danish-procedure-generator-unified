from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass


class CitationValidationError(ValueError):
    pass


_citation_re = re.compile(r"\[S:([^\]]+)\]")
_citation_prefix_re = re.compile(r"^\[S:([^\]]+)\]")
_sentence_split_re = re.compile(r"(?<=[.!?])\s+")
_bullet_re = re.compile(r"^[-*+]\s+(?P<body>.+)$")
_numbered_re = re.compile(r"^(?P<num>\d+)[.)]\s+(?P<body>.+)$")
_numbered_only_re = re.compile(r"^\d+[.)]\s*$")

_abbrev_multi_dot_re = re.compile(r"(?i)^[a-zæøå]{1,4}\.(?:[a-zæøå]{1,4}\.)+$")
# Pattern to detect bibliographic reference lines (URLs, DOIs, PMIDs, etc.)
_bibliography_re = re.compile(
    r"^\s*\(?\d{4}\)?\s*"  # Year like (2025) or 2025
    r".*(?:https?://|doi:|DOI:|pmid:|PMID:)",  # Followed by URL/DOI/PMID
    re.IGNORECASE
)
_abbrev_single_dot_endings = {
    # General Danish abbreviations
    "ca.",
    "evt.",
    "obs.",
    "inkl.",
    "jf.",
    "pga.",
    "ifm.",
    "kl.",
    "sek.",
    "min.",
    "maks.",
    "max.",
    "dvs.",
    "etc.",
    "fx.",
    "f.eks.",
    "m.v.",
    "m.fl.",
    "bl.a.",
    "vs.",
    "pt.",
    "resp.",
    "ref.",
    "nr.",
    # Medical abbreviations (anatomical)
    "n.",    # nervus
    "m.",    # musculus
    "v.",    # vena
    "a.",    # arteria
    "r.",    # ramus
    "lig.",  # ligamentum
    "proc.", # processus
    # Medical abbreviations (clinical)
    "p.o.",  # per os
    "i.v.",  # intravenøst
    "i.m.",  # intramuskulært
    "s.c.",  # subkutant
    "mg.",   # milligram (sometimes written with dot)
    "ml.",   # milliliter
    "kg.",   # kilogram
}


@dataclass(frozen=True)
class CitedSentence:
    line_no: int
    text: str
    citations: list[str]


def iter_cited_sentences(markdown_text: str) -> Iterator[CitedSentence]:
    out: list[CitedSentence] = []
    for line_no, block in _iter_blocks(markdown_text):
        parts = [p.strip() for p in _sentence_split_re.split(block) if p.strip()]
        merged: list[str] = []
        for part in parts:
            if merged and (_is_only_citations(part) or _ends_with_abbreviation(merged[-1])):
                merged[-1] = f"{merged[-1]} {part}".strip()
            else:
                merged.append(part)

        # Extract all citations from the entire block - these apply to the whole unit
        block_citations = _citation_re.findall(block)

        for sent in merged:
            if not _looks_like_sentence(sent):
                continue
            lead_cits, remainder = _extract_leading_citations(sent)
            if lead_cits and out:
                prev = out[-1]
                out[-1] = CitedSentence(
                    line_no=prev.line_no,
                    text=f"{prev.text} {' '.join(f'[S:{c}]' for c in lead_cits)}".strip(),
                    citations=prev.citations + lead_cits,
                )
                if not remainder:
                    continue
                sent = remainder

            # Use sentence-level citations if available, otherwise fall back to block-level
            sentence_citations = _citation_re.findall(sent)
            citations = sentence_citations if sentence_citations else block_citations
            out.append(CitedSentence(line_no=line_no, text=sent.strip(), citations=citations))

    yield from out


def _iter_blocks(markdown_text: str) -> list[tuple[int, str]]:
    blocks: list[tuple[int, str]] = []
    current: list[str] = []
    current_start = 1
    current_kind: str | None = None

    def flush() -> None:
        nonlocal current, current_kind
        if current:
            text = " ".join(current).strip()
            if text:
                blocks.append((current_start, text))
        current = []
        current_kind = None

    for line_no, line in enumerate(markdown_text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            flush()
            continue
        if stripped.startswith("#"):
            flush()
            continue
        if _is_only_citations(stripped):
            if current:
                current.append(stripped)
            continue

        m = _bullet_re.match(stripped)
        if m:
            flush()
            current_start = line_no
            current_kind = "list"
            current = [m.group("body").strip()]
            continue

        m = _numbered_re.match(stripped)
        if m:
            flush()
            current_start = line_no
            current_kind = "list"
            current = [m.group("body").strip()]
            continue

        if _numbered_only_re.match(stripped):
            flush()
            current_start = line_no
            current_kind = "list"
            current = []
            continue

        if current_kind == "list" and not current:
            current = [stripped]
            continue

        if not current:
            current_start = line_no
            current_kind = "para"
            current = [stripped]
            continue

        current.append(stripped)

    flush()
    return blocks


def _looks_like_sentence(text: str) -> bool:
    # Require at least one letter/number to avoid checking pure citation lines.
    if not any(ch.isalnum() for ch in text):
        return False
    # Skip bibliographic reference lines (year + URL/DOI/PMID)
    if _bibliography_re.match(text):
        return False
    # Skip lines that are purely URLs or DOIs
    stripped = text.strip()
    return not stripped.startswith(("http://", "https://", "doi:", "DOI:"))


def _is_only_citations(text: str) -> bool:
    if not _citation_re.search(text):
        return False
    stripped = _citation_re.sub("", text).strip()
    return stripped == ""


def _ends_with_abbreviation(text: str) -> bool:
    stripped = _citation_re.sub("", text).strip()
    if not stripped:
        return False
    last = stripped.split()[-1]
    last = last.rstrip(")”“’\"'],;:…")  # common closers/punctuation
    last = last.lstrip("([{\"'“‘")  # common openers
    lower = last.lower()
    if lower in _abbrev_single_dot_endings:
        return True
    return bool(_abbrev_multi_dot_re.match(lower))


def _extract_leading_citations(text: str) -> tuple[list[str], str]:
    cits: list[str] = []
    rest = text.lstrip()
    while True:
        m = _citation_prefix_re.match(rest)
        if not m:
            break
        cits.append(m.group(1))
        rest = rest[m.end() :].lstrip()
    return cits, rest


def split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in _sentence_split_re.split(text.strip()) if p.strip()]
    if not parts:
        return []
    merged: list[str] = []
    for part in parts:
        if merged and (_is_only_citations(part) or _ends_with_abbreviation(merged[-1])):
            merged[-1] = f"{merged[-1]} {part}".strip()
        else:
            merged.append(part)
    return [s for s in merged if _looks_like_sentence(s)]
