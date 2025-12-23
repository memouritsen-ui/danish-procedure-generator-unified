"""Tests for ManifestBuilder class.

TDD: Tests define the interface for ManifestBuilder.
ManifestBuilder creates manifest.json files for procedure release bundles.

Run: pytest tests/bundle/test_manifest.py -v
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from procedurewriter.bundle.manifest import ManifestBuilder


class TestManifestBuilderInit:
    """Tests for ManifestBuilder initialization."""

    def test_init_with_valid_directory(self, tmp_path: Path):
        """Should initialize with a valid run directory."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "test.txt").write_text("content", encoding="utf-8")

        builder = ManifestBuilder(run_dir)

        assert builder.run_dir == run_dir

    def test_init_with_nonexistent_directory_raises(self, tmp_path: Path):
        """Should raise FileNotFoundError for nonexistent directory."""
        nonexistent = tmp_path / "does_not_exist"

        with pytest.raises(FileNotFoundError):
            ManifestBuilder(nonexistent)

    def test_init_with_file_raises(self, tmp_path: Path):
        """Should raise ValueError if path is a file, not directory."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("content", encoding="utf-8")

        with pytest.raises(ValueError, match="not a directory"):
            ManifestBuilder(file_path)


class TestManifestBuilderSetters:
    """Tests for ManifestBuilder fluent setter methods."""

    def test_set_run_id(self, tmp_path: Path):
        """Should set run_id in manifest."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        run_id = uuid4().hex

        builder = ManifestBuilder(run_dir)
        result = builder.set_run_id(run_id)

        assert result is builder  # Returns self for chaining
        manifest = builder.to_dict()
        assert manifest["run_id"] == run_id

    def test_set_procedure(self, tmp_path: Path):
        """Should set procedure name in manifest."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        builder = ManifestBuilder(run_dir)
        result = builder.set_procedure("Akut astma behandling")

        assert result is builder
        manifest = builder.to_dict()
        assert manifest["procedure"] == "Akut astma behandling"

    def test_set_version(self, tmp_path: Path):
        """Should set manifest version."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        builder = ManifestBuilder(run_dir)
        result = builder.set_version("2.0.0")

        assert result is builder
        manifest = builder.to_dict()
        assert manifest["version"] == "2.0.0"

    def test_set_created_at(self, tmp_path: Path):
        """Should set created_at timestamp."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        timestamp = "2024-12-22T12:00:00Z"

        builder = ManifestBuilder(run_dir)
        result = builder.set_created_at(timestamp)

        assert result is builder
        manifest = builder.to_dict()
        assert manifest["created_at"] == timestamp

    def test_chained_setters(self, tmp_path: Path):
        """Should support method chaining for all setters."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        run_id = uuid4().hex

        builder = (
            ManifestBuilder(run_dir)
            .set_run_id(run_id)
            .set_procedure("Test Procedure")
            .set_version("1.0.0")
            .set_created_at("2024-12-22T00:00:00Z")
        )

        manifest = builder.to_dict()
        assert manifest["run_id"] == run_id
        assert manifest["procedure"] == "Test Procedure"
        assert manifest["version"] == "1.0.0"
        assert manifest["created_at"] == "2024-12-22T00:00:00Z"


class TestManifestBuilderMetadata:
    """Tests for adding optional metadata."""

    def test_add_llm_config(self, tmp_path: Path):
        """Should add LLM configuration section."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        llm_config = {
            "provider": "openai",
            "model": "gpt-4",
            "temperature": 0.7,
        }

        builder = ManifestBuilder(run_dir)
        result = builder.add_llm_config(llm_config)

        assert result is builder
        manifest = builder.to_dict()
        assert manifest["llm_config"] == llm_config

    def test_add_quality(self, tmp_path: Path):
        """Should add quality metrics section."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        quality = {
            "final_score": 8.5,
            "iterations_used": 2,
            "gates_passed": ["s0_safety", "s1_quality"],
        }

        builder = ManifestBuilder(run_dir)
        result = builder.add_quality(quality)

        assert result is builder
        manifest = builder.to_dict()
        assert manifest["quality"] == quality

    def test_add_runtime(self, tmp_path: Path):
        """Should add runtime information section."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        runtime = {
            "total_duration_seconds": 250,
            "stage_timings": {"bootstrap": 5, "retrieve": 60},
            "warnings": [],
        }

        builder = ManifestBuilder(run_dir)
        result = builder.add_runtime(runtime)

        assert result is builder
        manifest = builder.to_dict()
        assert manifest["runtime"] == runtime

    def test_add_sources(self, tmp_path: Path):
        """Should add sources information section."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        sources = {
            "total_count": 15,
            "by_tier": {
                "danish_guidelines": 3,
                "international": 7,
            },
        }

        builder = ManifestBuilder(run_dir)
        result = builder.add_sources(sources)

        assert result is builder
        manifest = builder.to_dict()
        assert manifest["sources"] == sources

    def test_add_cost(self, tmp_path: Path):
        """Should add cost information section."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        cost = {
            "total_usd": 0.45,
            "input_tokens": 15000,
            "output_tokens": 5000,
        }

        builder = ManifestBuilder(run_dir)
        result = builder.add_cost(cost)

        assert result is builder
        manifest = builder.to_dict()
        assert manifest["cost"] == cost


class TestManifestBuilderChecksums:
    """Tests for checksum functionality."""

    def test_include_checksums(self, tmp_path: Path):
        """Should calculate and include file checksums."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "file1.txt").write_text("content1", encoding="utf-8")
        (run_dir / "file2.txt").write_text("content2", encoding="utf-8")

        builder = ManifestBuilder(run_dir)
        result = builder.include_checksums()

        assert result is builder
        manifest = builder.to_dict()
        assert "checksums" in manifest
        assert "file1.txt" in manifest["checksums"]
        assert "file2.txt" in manifest["checksums"]
        # Verify SHA-256 format (64 hex chars)
        assert len(manifest["checksums"]["file1.txt"]) == 64

    def test_include_checksums_with_excludes(self, tmp_path: Path):
        """Should respect exclude patterns for checksums."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "keep.txt").write_text("keep", encoding="utf-8")
        (run_dir / "skip.log").write_text("skip", encoding="utf-8")

        builder = ManifestBuilder(run_dir)
        result = builder.exclude("*.log").include_checksums()

        manifest = builder.to_dict()
        assert "keep.txt" in manifest["checksums"]
        assert "skip.log" not in manifest["checksums"]

    def test_include_checksums_nested_files(self, tmp_path: Path):
        """Should include checksums for files in subdirectories."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        subdir = run_dir / "sources"
        subdir.mkdir()
        (run_dir / "root.txt").write_text("root", encoding="utf-8")
        (subdir / "nested.txt").write_text("nested", encoding="utf-8")

        builder = ManifestBuilder(run_dir)
        builder.include_checksums()

        manifest = builder.to_dict()
        assert "root.txt" in manifest["checksums"]
        assert "sources/nested.txt" in manifest["checksums"]


class TestManifestBuilderExclude:
    """Tests for exclude functionality."""

    def test_exclude_pattern(self, tmp_path: Path):
        """Should store exclude patterns for checksums."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        builder = ManifestBuilder(run_dir)
        result = builder.exclude("*.log")

        assert result is builder
        # Exclude should affect include_checksums

    def test_exclude_multiple_patterns(self, tmp_path: Path):
        """Should support multiple exclude patterns."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "keep.txt").write_text("keep", encoding="utf-8")
        (run_dir / "skip.log").write_text("skip", encoding="utf-8")
        (run_dir / "skip.tmp").write_text("skip", encoding="utf-8")

        builder = ManifestBuilder(run_dir)
        builder.exclude("*.log").exclude("*.tmp").include_checksums()

        manifest = builder.to_dict()
        assert "keep.txt" in manifest["checksums"]
        assert "skip.log" not in manifest["checksums"]
        assert "skip.tmp" not in manifest["checksums"]


class TestManifestBuilderBuild:
    """Tests for ManifestBuilder.build() method."""

    def test_build_creates_manifest_file(self, tmp_path: Path):
        """Should create manifest.json file at output path."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        output_path = run_dir / "manifest.json"

        builder = ManifestBuilder(run_dir)
        builder.set_version("1.0.0").set_procedure("Test")
        builder.build(output_path)

        assert output_path.exists()

    def test_build_writes_valid_json(self, tmp_path: Path):
        """Should write valid JSON content."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        output_path = run_dir / "manifest.json"

        builder = ManifestBuilder(run_dir)
        builder.set_version("1.0.0").set_procedure("Test")
        builder.build(output_path)

        content = output_path.read_text(encoding="utf-8")
        data = json.loads(content)  # Should not raise
        assert data["version"] == "1.0.0"
        assert data["procedure"] == "Test"

    def test_build_creates_parent_directories(self, tmp_path: Path):
        """Should create parent directories if needed."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        output_path = tmp_path / "deep" / "nested" / "manifest.json"

        builder = ManifestBuilder(run_dir)
        builder.set_version("1.0.0")
        builder.build(output_path)

        assert output_path.exists()

    def test_build_returns_manifest_sha256(self, tmp_path: Path):
        """Should return SHA-256 hash of manifest content."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        output_path = run_dir / "manifest.json"

        builder = ManifestBuilder(run_dir)
        builder.set_version("1.0.0")
        sha256 = builder.build(output_path)

        # SHA-256 is 64 hex chars
        assert len(sha256) == 64
        assert all(c in "0123456789abcdef" for c in sha256)

    def test_build_includes_all_metadata(self, tmp_path: Path):
        """Should include all set metadata in output."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "test.txt").write_text("test", encoding="utf-8")
        output_path = run_dir / "manifest.json"
        run_id = uuid4().hex

        builder = (
            ManifestBuilder(run_dir)
            .set_run_id(run_id)
            .set_procedure("Akut behandling")
            .set_version("1.0.0")
            .set_created_at("2024-12-22T00:00:00Z")
            .add_llm_config({"provider": "openai"})
            .add_quality({"final_score": 9.0})
            .include_checksums()
        )
        builder.build(output_path)

        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert data["run_id"] == run_id
        assert data["procedure"] == "Akut behandling"
        assert data["version"] == "1.0.0"
        assert data["created_at"] == "2024-12-22T00:00:00Z"
        assert data["llm_config"]["provider"] == "openai"
        assert data["quality"]["final_score"] == 9.0
        assert "checksums" in data

    def test_build_handles_danish_characters(self, tmp_path: Path):
        """Should properly encode Danish characters."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        output_path = run_dir / "manifest.json"

        builder = ManifestBuilder(run_dir)
        builder.set_procedure("Akut hypoækmi behandling").set_version("1.0.0")
        builder.build(output_path)

        content = output_path.read_text(encoding="utf-8")
        assert "hypoækmi" in content
        data = json.loads(content)
        assert data["procedure"] == "Akut hypoækmi behandling"

    def test_build_sorted_keys_for_consistency(self, tmp_path: Path):
        """Should sort JSON keys for reproducible output."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        output_path = run_dir / "manifest.json"

        builder = ManifestBuilder(run_dir)
        builder.set_version("1.0.0").set_procedure("Test").set_run_id("abc123")
        builder.build(output_path)

        content = output_path.read_text(encoding="utf-8")
        # With sorted keys, 'procedure' comes before 'run_id' alphabetically
        assert content.index('"procedure"') < content.index('"run_id"')


class TestManifestBuilderToDict:
    """Tests for ManifestBuilder.to_dict() method."""

    def test_to_dict_returns_dict(self, tmp_path: Path):
        """Should return a dictionary."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        builder = ManifestBuilder(run_dir)
        result = builder.to_dict()

        assert isinstance(result, dict)

    def test_to_dict_does_not_modify_builder(self, tmp_path: Path):
        """Calling to_dict() should not modify the builder state."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        builder = ManifestBuilder(run_dir)
        builder.set_version("1.0.0")

        dict1 = builder.to_dict()
        dict2 = builder.to_dict()

        assert dict1 == dict2

    def test_to_dict_deep_copy(self, tmp_path: Path):
        """Should return a copy, not reference to internal state."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        builder = ManifestBuilder(run_dir)
        builder.set_version("1.0.0")

        result = builder.to_dict()
        result["version"] = "modified"

        # Original builder should be unchanged
        assert builder.to_dict()["version"] == "1.0.0"


class TestManifestBuilderDefaults:
    """Tests for default values."""

    def test_default_version(self, tmp_path: Path):
        """Should have default version if not set."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        builder = ManifestBuilder(run_dir)
        manifest = builder.to_dict()

        assert "version" in manifest
        assert manifest["version"] == "1.0.0"  # Default version

    def test_default_created_at_if_not_set(self, tmp_path: Path):
        """Should generate created_at if not set on build."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        output_path = run_dir / "manifest.json"

        builder = ManifestBuilder(run_dir)
        builder.build(output_path)

        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert "created_at" in data
        # Should be a valid ISO timestamp
        datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
