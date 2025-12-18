from __future__ import annotations

from pathlib import Path


class UnsafePathError(ValueError):
    pass


def safe_path_within(path: Path, *, root_dir: Path) -> Path:
    resolved_root = root_dir.resolve()
    resolved_path = path.resolve()
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as e:
        raise UnsafePathError(f"Path is outside root_dir: {resolved_path}") from e
    return resolved_path

