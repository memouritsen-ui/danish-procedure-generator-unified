from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from procedurewriter.pipeline.hashing import sha256_bytes, sha256_text
from procedurewriter.pipeline.io import write_bytes, write_text
from procedurewriter.pipeline.types import SourceRecord


def make_source_id(n: int) -> str:
    return f"SRC{n:04d}"


@dataclass(frozen=True)
class WrittenFiles:
    raw_path: Path
    normalized_path: Path
    raw_sha256: str
    normalized_sha256: str


def write_source_files(
    *,
    run_dir: Path,
    source_id: str,
    raw_bytes: bytes,
    raw_suffix: str,
    normalized_text: str,
) -> WrittenFiles:
    raw_path = run_dir / "raw" / f"{source_id}{raw_suffix}"
    norm_path = run_dir / "normalized" / f"{source_id}.txt"
    write_bytes(raw_path, raw_bytes)
    write_text(norm_path, normalized_text)
    return WrittenFiles(
        raw_path=raw_path,
        normalized_path=norm_path,
        raw_sha256=sha256_bytes(raw_bytes),
        normalized_sha256=sha256_text(normalized_text),
    )


def to_jsonl_record(src: SourceRecord) -> dict[str, Any]:
    return {
        "source_id": src.source_id,
        "fetched_at_utc": src.fetched_at_utc,
        "kind": src.kind,
        "title": src.title,
        "year": src.year,
        "url": src.url,
        "doi": src.doi,
        "pmid": src.pmid,
        "raw_path": src.raw_path,
        "normalized_path": src.normalized_path,
        "raw_sha256": src.raw_sha256,
        "normalized_sha256": src.normalized_sha256,
        "extraction_notes": src.extraction_notes,
        "terms_licence_note": src.terms_licence_note,
        "extra": src.extra,
    }
