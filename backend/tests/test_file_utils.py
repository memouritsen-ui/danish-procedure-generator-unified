from pathlib import Path

import pytest

from procedurewriter.file_utils import UnsafePathError, safe_path_within


def test_safe_path_within_allows_child(tmp_path: Path):
    root = tmp_path / "root"
    child = root / "a" / "b.txt"
    child.parent.mkdir(parents=True, exist_ok=True)
    child.write_text("x", encoding="utf-8")
    resolved = safe_path_within(child, root_dir=root)
    assert resolved.exists()


def test_safe_path_within_rejects_outside(tmp_path: Path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("x", encoding="utf-8")
    with pytest.raises(UnsafePathError):
        safe_path_within(outside, root_dir=root)

