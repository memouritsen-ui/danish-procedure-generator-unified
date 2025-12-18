from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from procedurewriter.pipeline.hashing import sha256_bytes, sha256_file
from procedurewriter.pipeline.io import write_text
from procedurewriter.pipeline.types import SourceRecord


def write_manifest(
    *,
    manifest_path: Path,
    run_id: str,
    created_at_utc: str,
    procedure: str,
    context: str | None,
    author_guide_path: Path,
    allowlist_path: Path,
    sources_jsonl_path: Path,
    procedure_md_path: Path,
    evidence_report_path: Path | None = None,
    sources: list[SourceRecord],
    runtime: dict[str, Any],
) -> str:
    author_guide_sha = sha256_file(author_guide_path)
    allowlist_sha = sha256_file(allowlist_path)

    artifacts: dict[str, Any] = {
        "sources_jsonl": {"path": str(sources_jsonl_path), "sha256": sha256_file(sources_jsonl_path)},
        "procedure_md": {"path": str(procedure_md_path), "sha256": sha256_file(procedure_md_path)},
    }
    if evidence_report_path is not None and evidence_report_path.exists():
        artifacts["evidence_report"] = {"path": str(evidence_report_path), "sha256": sha256_file(evidence_report_path)}

    manifest: dict[str, Any] = {
        "manifest_version": 1,
        "run_id": run_id,
        "created_at_utc": created_at_utc,
        "procedure": procedure,
        "context": context,
        "config_snapshot": {
            "author_guide_path": str(author_guide_path),
            "author_guide_sha256": author_guide_sha,
            "allowlist_path": str(allowlist_path),
            "allowlist_sha256": allowlist_sha,
        },
        "artifacts": artifacts,
        "sources": [
            {
                "source_id": s.source_id,
                "kind": s.kind,
                "url": s.url,
                "doi": s.doi,
                "pmid": s.pmid,
                "raw_path": s.raw_path,
                "normalized_path": s.normalized_path,
                "raw_sha256": s.raw_sha256,
                "normalized_sha256": s.normalized_sha256,
            }
            for s in sources
        ],
        "runtime": runtime,
    }

    serialized = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    write_text(manifest_path, serialized)
    return sha256_bytes(serialized.encode("utf-8"))
