import json
import zipfile
from pathlib import Path

from procedurewriter.run_bundle import build_run_bundle_zip, read_run_manifest


def test_build_run_bundle_zip_includes_files(tmp_path: Path):
    run_dir = tmp_path / "run"
    (run_dir / "raw").mkdir(parents=True)
    (run_dir / "normalized").mkdir(parents=True)
    (run_dir / "raw" / "SRC0001.xml").write_text("<x/>", encoding="utf-8")
    (run_dir / "normalized" / "SRC0001.txt").write_text("n", encoding="utf-8")
    (run_dir / "procedure.md").write_text("# P", encoding="utf-8")
    (run_dir / "run_manifest.json").write_text(json.dumps({"run_id": "RID"}), encoding="utf-8")

    out = run_dir / "run_bundle.zip"
    build_run_bundle_zip(run_dir, output_path=out)
    assert out.exists()

    with zipfile.ZipFile(out) as zf:
        names = set(zf.namelist())
    assert "procedure.md" in names
    assert "run_manifest.json" in names
    assert "raw/SRC0001.xml" in names
    assert "normalized/SRC0001.txt" in names


def test_read_run_manifest(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "run_manifest.json").write_text(json.dumps({"run_id": "RID", "x": 1}), encoding="utf-8")
    manifest = read_run_manifest(run_dir)
    assert manifest["run_id"] == "RID"
    assert manifest["x"] == 1

