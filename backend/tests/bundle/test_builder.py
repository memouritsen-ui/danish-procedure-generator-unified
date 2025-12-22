"""Tests for ZipBuilder class.

TDD: Tests define the interface for ZipBuilder.
ZipBuilder provides a structured way to create release bundles from run directories.

Run: pytest tests/bundle/test_builder.py -v
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from procedurewriter.bundle.builder import ZipBuilder


class TestZipBuilderInit:
    """Tests for ZipBuilder initialization."""

    def test_init_with_valid_directory(self, tmp_path: Path):
        """Should initialize with a valid run directory."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "test.txt").write_text("content", encoding="utf-8")

        builder = ZipBuilder(run_dir)

        assert builder.run_dir == run_dir

    def test_init_with_nonexistent_directory_raises(self, tmp_path: Path):
        """Should raise FileNotFoundError for nonexistent directory."""
        nonexistent = tmp_path / "does_not_exist"

        with pytest.raises(FileNotFoundError):
            ZipBuilder(nonexistent)

    def test_init_with_file_raises(self, tmp_path: Path):
        """Should raise ValueError if path is a file, not directory."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("content", encoding="utf-8")

        with pytest.raises(ValueError, match="not a directory"):
            ZipBuilder(file_path)


class TestZipBuilderBuild:
    """Tests for ZipBuilder.build() method."""

    def test_build_creates_zip_file(self, tmp_path: Path):
        """Should create a valid ZIP file at output path."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "test.txt").write_text("content", encoding="utf-8")
        output_path = tmp_path / "output.zip"

        builder = ZipBuilder(run_dir)
        builder.build(output_path)

        assert output_path.exists()
        assert zipfile.is_zipfile(output_path)

    def test_build_includes_all_files(self, tmp_path: Path):
        """Should include all files from run directory."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "file1.txt").write_text("one", encoding="utf-8")
        (run_dir / "file2.txt").write_text("two", encoding="utf-8")
        (run_dir / "procedure.md").write_text("# Procedure", encoding="utf-8")
        output_path = tmp_path / "output.zip"

        builder = ZipBuilder(run_dir)
        builder.build(output_path)

        with zipfile.ZipFile(output_path) as zf:
            names = set(zf.namelist())
            assert names == {"file1.txt", "file2.txt", "procedure.md"}

    def test_build_includes_subdirectory_files(self, tmp_path: Path):
        """Should include files from subdirectories with correct paths."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        subdir = run_dir / "sources"
        subdir.mkdir()
        (subdir / "source1.xml").write_text("<xml/>", encoding="utf-8")
        (subdir / "source2.xml").write_text("<xml/>", encoding="utf-8")
        output_path = tmp_path / "output.zip"

        builder = ZipBuilder(run_dir)
        builder.build(output_path)

        with zipfile.ZipFile(output_path) as zf:
            names = set(zf.namelist())
            assert "sources/source1.xml" in names
            assert "sources/source2.xml" in names

    def test_build_preserves_content(self, tmp_path: Path):
        """Should preserve exact file content."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        content = "# Pneumoni Behandling\n\nDansk procedure indhold æøå."
        (run_dir / "procedure.md").write_text(content, encoding="utf-8")
        output_path = tmp_path / "output.zip"

        builder = ZipBuilder(run_dir)
        builder.build(output_path)

        with zipfile.ZipFile(output_path) as zf:
            extracted = zf.read("procedure.md").decode("utf-8")
            assert extracted == content

    def test_build_excludes_output_file_itself(self, tmp_path: Path):
        """Should not include the output ZIP in itself."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "test.txt").write_text("content", encoding="utf-8")
        output_path = run_dir / "bundle.zip"  # Inside run_dir!

        builder = ZipBuilder(run_dir)
        builder.build(output_path)

        with zipfile.ZipFile(output_path) as zf:
            names = set(zf.namelist())
            assert "bundle.zip" not in names
            assert "test.txt" in names

    def test_build_creates_parent_directories(self, tmp_path: Path):
        """Should create parent directories for output path."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "test.txt").write_text("content", encoding="utf-8")
        output_path = tmp_path / "deep" / "nested" / "output.zip"

        builder = ZipBuilder(run_dir)
        builder.build(output_path)

        assert output_path.exists()

    def test_build_uses_deflate_compression(self, tmp_path: Path):
        """Should use DEFLATE compression for smaller bundles."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        # Create a file with repetitive content (compresses well)
        (run_dir / "large.txt").write_text("x" * 10000, encoding="utf-8")
        output_path = tmp_path / "output.zip"

        builder = ZipBuilder(run_dir)
        builder.build(output_path)

        with zipfile.ZipFile(output_path) as zf:
            info = zf.getinfo("large.txt")
            assert info.compress_type == zipfile.ZIP_DEFLATED

    def test_build_empty_directory_creates_empty_zip(self, tmp_path: Path):
        """Should create valid but empty ZIP for empty directory."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        output_path = tmp_path / "output.zip"

        builder = ZipBuilder(run_dir)
        builder.build(output_path)

        with zipfile.ZipFile(output_path) as zf:
            assert zf.namelist() == []


class TestZipBuilderExclude:
    """Tests for ZipBuilder.exclude() method."""

    def test_exclude_by_pattern(self, tmp_path: Path):
        """Should exclude files matching glob pattern."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "keep.txt").write_text("keep", encoding="utf-8")
        (run_dir / "skip.log").write_text("skip", encoding="utf-8")
        (run_dir / "also_skip.log").write_text("skip", encoding="utf-8")
        output_path = tmp_path / "output.zip"

        builder = ZipBuilder(run_dir)
        builder.exclude("*.log")
        builder.build(output_path)

        with zipfile.ZipFile(output_path) as zf:
            names = set(zf.namelist())
            assert "keep.txt" in names
            assert "skip.log" not in names
            assert "also_skip.log" not in names

    def test_exclude_multiple_patterns(self, tmp_path: Path):
        """Should support multiple exclude patterns."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "keep.txt").write_text("keep", encoding="utf-8")
        (run_dir / "skip.log").write_text("skip", encoding="utf-8")
        (run_dir / "skip.tmp").write_text("skip", encoding="utf-8")
        output_path = tmp_path / "output.zip"

        builder = ZipBuilder(run_dir)
        builder.exclude("*.log")
        builder.exclude("*.tmp")
        builder.build(output_path)

        with zipfile.ZipFile(output_path) as zf:
            names = set(zf.namelist())
            assert names == {"keep.txt"}

    def test_exclude_returns_self_for_chaining(self, tmp_path: Path):
        """Should return self for method chaining."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "test.txt").write_text("content", encoding="utf-8")

        builder = ZipBuilder(run_dir)
        result = builder.exclude("*.log")

        assert result is builder

    def test_exclude_subdirectory_pattern(self, tmp_path: Path):
        """Should exclude files in subdirectories by pattern."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        cache_dir = run_dir / "__pycache__"
        cache_dir.mkdir()
        (run_dir / "keep.py").write_text("# keep", encoding="utf-8")
        (cache_dir / "compiled.pyc").write_bytes(b"\x00\x00")
        output_path = tmp_path / "output.zip"

        builder = ZipBuilder(run_dir)
        builder.exclude("__pycache__/**")
        builder.build(output_path)

        with zipfile.ZipFile(output_path) as zf:
            names = set(zf.namelist())
            assert "keep.py" in names
            assert not any("__pycache__" in name for name in names)


class TestZipBuilderChecksums:
    """Tests for ZipBuilder.get_checksums() method."""

    def test_get_checksums_returns_sha256_dict(self, tmp_path: Path):
        """Should return dict of relative_path -> SHA256 hex digest."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        content = b"test content"
        (run_dir / "test.txt").write_bytes(content)
        expected_hash = hashlib.sha256(content).hexdigest()

        builder = ZipBuilder(run_dir)
        checksums = builder.get_checksums()

        assert "test.txt" in checksums
        assert checksums["test.txt"] == expected_hash

    def test_get_checksums_includes_all_files(self, tmp_path: Path):
        """Should include checksums for all files."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "a.txt").write_text("a", encoding="utf-8")
        (run_dir / "b.txt").write_text("b", encoding="utf-8")
        subdir = run_dir / "sub"
        subdir.mkdir()
        (subdir / "c.txt").write_text("c", encoding="utf-8")

        builder = ZipBuilder(run_dir)
        checksums = builder.get_checksums()

        assert "a.txt" in checksums
        assert "b.txt" in checksums
        assert "sub/c.txt" in checksums

    def test_get_checksums_respects_excludes(self, tmp_path: Path):
        """Should not include checksums for excluded files."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "keep.txt").write_text("keep", encoding="utf-8")
        (run_dir / "skip.log").write_text("skip", encoding="utf-8")

        builder = ZipBuilder(run_dir)
        builder.exclude("*.log")
        checksums = builder.get_checksums()

        assert "keep.txt" in checksums
        assert "skip.log" not in checksums

    def test_get_checksums_empty_dir_returns_empty_dict(self, tmp_path: Path):
        """Should return empty dict for empty directory."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        builder = ZipBuilder(run_dir)
        checksums = builder.get_checksums()

        assert checksums == {}


class TestZipBuilderListFiles:
    """Tests for ZipBuilder.list_files() method."""

    def test_list_files_returns_relative_paths(self, tmp_path: Path):
        """Should return list of relative file paths."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "a.txt").write_text("a", encoding="utf-8")
        (run_dir / "b.txt").write_text("b", encoding="utf-8")

        builder = ZipBuilder(run_dir)
        files = builder.list_files()

        assert set(files) == {"a.txt", "b.txt"}

    def test_list_files_respects_excludes(self, tmp_path: Path):
        """Should not include excluded files."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "keep.txt").write_text("keep", encoding="utf-8")
        (run_dir / "skip.log").write_text("skip", encoding="utf-8")

        builder = ZipBuilder(run_dir)
        builder.exclude("*.log")
        files = builder.list_files()

        assert "keep.txt" in files
        assert "skip.log" not in files

    def test_list_files_includes_subdirectory_paths(self, tmp_path: Path):
        """Should include files from subdirectories with full relative paths."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        subdir = run_dir / "sources"
        subdir.mkdir()
        (run_dir / "root.txt").write_text("root", encoding="utf-8")
        (subdir / "nested.txt").write_text("nested", encoding="utf-8")

        builder = ZipBuilder(run_dir)
        files = builder.list_files()

        assert "root.txt" in files
        assert "sources/nested.txt" in files
