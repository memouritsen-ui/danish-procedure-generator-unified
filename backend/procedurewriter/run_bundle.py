from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any, cast


def read_run_manifest(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "run_manifest.json"
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("run_manifest.json must be a JSON object")
    return cast(dict[str, Any], obj)


def build_run_bundle_zip(run_dir: Path, *, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(run_dir.rglob("*")):
            if p.is_dir():
                continue
            if p.resolve() == output_path.resolve():
                continue
            rel = p.relative_to(run_dir)
            zf.write(p, arcname=str(rel))
