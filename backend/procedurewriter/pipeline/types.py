from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    fetched_at_utc: str
    kind: str
    title: str | None
    year: int | None
    url: str | None
    doi: str | None
    pmid: str | None
    raw_path: str
    normalized_path: str
    raw_sha256: str
    normalized_sha256: str
    extraction_notes: str | None
    terms_licence_note: str | None
    extra: dict[str, Any]


@dataclass(frozen=True)
class Snippet:
    source_id: str
    text: str
    location: dict[str, Any]
