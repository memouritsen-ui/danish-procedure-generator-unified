"""Integration tests for full bundle workflow.

TDD: Tests verify the complete end-to-end bundle creation process.
This integrates ZipBuilder, ManifestBuilder, and the bundle endpoint.

Run: pytest tests/integration/test_bundle.py -v
"""
from __future__ import annotations

import hashlib
import io
import json
import tempfile
import zipfile
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from procedurewriter.bundle.builder import ZipBuilder
from procedurewriter.bundle.manifest import ManifestBuilder
from procedurewriter.db import init_db, _connect
from procedurewriter.main import app


class TestBundleCreationWorkflow:
    """Integration tests for complete bundle creation workflow."""

    def test_manifest_checksums_match_zip_contents(self, tmp_path: Path):
        """Manifest checksums should match actual file checksums in ZIP."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        # Create realistic run files
        (run_dir / "procedure.md").write_text(
            "# Akut Astma Behandling\n\n## Introduktion\nDansk procedure.",
            encoding="utf-8",
        )
        (run_dir / "Procedure.docx").write_bytes(b"PK\x03\x04fake_docx_content")
        (run_dir / "sources.jsonl").write_text(
            '{"source_id": "src-001", "title": "Danish Guidelines"}\n',
            encoding="utf-8",
        )

        # Build manifest with checksums
        run_id = uuid4().hex
        manifest_builder = (
            ManifestBuilder(run_dir)
            .set_run_id(run_id)
            .set_procedure("Akut Astma Behandling")
            .set_version("1.0.0")
            .include_checksums()
        )
        manifest_path = run_dir / "manifest.json"
        manifest_builder.build(manifest_path)

        # Build ZIP bundle
        zip_builder = ZipBuilder(run_dir)
        zip_path = tmp_path / "bundle.zip"
        zip_builder.build(zip_path)

        # Verify: manifest checksums match actual file checksums
        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))

        with zipfile.ZipFile(zip_path) as zf:
            for filename, expected_hash in manifest_data["checksums"].items():
                # Skip manifest.json itself (it wasn't in the checksums)
                if filename == "manifest.json":
                    continue

                actual_content = zf.read(filename)
                actual_hash = hashlib.sha256(actual_content).hexdigest()
                assert actual_hash == expected_hash, f"Checksum mismatch for {filename}"

    def test_complete_bundle_includes_all_files(self, tmp_path: Path):
        """Complete bundle should include all run files and manifest."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        # Create all expected file types
        (run_dir / "procedure.md").write_text("# Procedure", encoding="utf-8")
        (run_dir / "Procedure.docx").write_bytes(b"DOCX_CONTENT")
        (run_dir / "sources.jsonl").write_text('{"id": "1"}\n', encoding="utf-8")
        (run_dir / "claims.json").write_text('[{"claim": "test"}]', encoding="utf-8")
        (run_dir / "evidence_notes.md").write_text("## Evidence Notes", encoding="utf-8")
        (run_dir / "run_manifest.json").write_text('{"version": "1.0"}', encoding="utf-8")

        # Create subdirectory with sources
        sources_dir = run_dir / "sources"
        sources_dir.mkdir()
        (sources_dir / "source_001.xml").write_text("<xml/>", encoding="utf-8")
        (sources_dir / "source_002.xml").write_text("<xml/>", encoding="utf-8")

        # Build bundle
        zip_builder = ZipBuilder(run_dir)
        zip_path = tmp_path / "bundle.zip"
        zip_builder.build(zip_path)

        # Verify all files are in bundle
        expected_files = {
            "procedure.md",
            "Procedure.docx",
            "sources.jsonl",
            "claims.json",
            "evidence_notes.md",
            "run_manifest.json",
            "sources/source_001.xml",
            "sources/source_002.xml",
        }

        with zipfile.ZipFile(zip_path) as zf:
            actual_files = set(zf.namelist())
            assert actual_files == expected_files

    def test_bundle_preserves_danish_content(self, tmp_path: Path):
        """Bundle should preserve Danish special characters (æ, ø, å)."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        danish_content = """# Akut Hypoglykæmi Behandling

## Indikationer
- Patienten har hypoglykæmi (blodsukker < 3.9 mmol/L)
- Bevidstløshed eller svær påvirket bevidsthed

## Behandling
1. Giv 20 ml 50% glukoseopløsning intravenøst
2. Overvåg patienten nøje
3. Gentag om nødvendigt
"""
        (run_dir / "procedure.md").write_text(danish_content, encoding="utf-8")

        # Build bundle
        zip_builder = ZipBuilder(run_dir)
        zip_path = tmp_path / "bundle.zip"
        zip_builder.build(zip_path)

        # Verify Danish content is preserved
        with zipfile.ZipFile(zip_path) as zf:
            extracted = zf.read("procedure.md").decode("utf-8")
            assert "Hypoglykæmi" in extracted
            assert "blodsukker" in extracted
            assert "Bevidstløshed" in extracted  # Capital B in original
            assert "glukoseopløsning" in extracted
            assert "nødvendigt" in extracted

    def test_manifest_with_all_metadata_sections(self, tmp_path: Path):
        """Manifest should correctly include all optional metadata sections."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "test.txt").write_text("content", encoding="utf-8")

        run_id = uuid4().hex

        builder = (
            ManifestBuilder(run_dir)
            .set_run_id(run_id)
            .set_procedure("Anafylaksi Behandling")
            .set_version("1.0.0")
            .set_created_at("2024-12-22T12:00:00Z")
            .add_llm_config({
                "provider": "openai",
                "model": "gpt-4",
                "temperature": 0.7,
            })
            .add_quality({
                "final_score": 8.5,
                "iterations_used": 2,
                "gates_passed": ["s0_safety", "s1_quality"],
            })
            .add_runtime({
                "total_duration_seconds": 180,
                "stage_timings": {
                    "bootstrap": 5,
                    "retrieve": 45,
                    "draft": 60,
                },
            })
            .add_sources({
                "total_count": 12,
                "by_tier": {
                    "danish_guidelines": 4,
                    "international": 8,
                },
            })
            .add_cost({
                "total_usd": 0.35,
                "input_tokens": 12000,
                "output_tokens": 4000,
            })
            .include_checksums()
        )

        manifest_path = run_dir / "manifest.json"
        builder.build(manifest_path)

        data = json.loads(manifest_path.read_text(encoding="utf-8"))

        # Verify all sections are present and correct
        assert data["run_id"] == run_id
        assert data["procedure"] == "Anafylaksi Behandling"
        assert data["version"] == "1.0.0"
        assert data["created_at"] == "2024-12-22T12:00:00Z"

        assert data["llm_config"]["provider"] == "openai"
        assert data["llm_config"]["model"] == "gpt-4"

        assert data["quality"]["final_score"] == 8.5
        assert "s0_safety" in data["quality"]["gates_passed"]

        assert data["runtime"]["total_duration_seconds"] == 180
        assert data["runtime"]["stage_timings"]["draft"] == 60

        assert data["sources"]["total_count"] == 12
        assert data["sources"]["by_tier"]["danish_guidelines"] == 4

        assert data["cost"]["total_usd"] == 0.35
        assert data["cost"]["input_tokens"] == 12000

        assert "checksums" in data
        assert "test.txt" in data["checksums"]

    def test_zip_and_manifest_exclude_patterns_match(self, tmp_path: Path):
        """ZipBuilder and ManifestBuilder should respect same exclude patterns."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        # Create files including ones that should be excluded
        (run_dir / "keep.md").write_text("# Keep this", encoding="utf-8")
        (run_dir / "debug.log").write_text("debug output", encoding="utf-8")
        (run_dir / "temp.tmp").write_text("temporary", encoding="utf-8")

        cache_dir = run_dir / "__pycache__"
        cache_dir.mkdir()
        (cache_dir / "module.pyc").write_bytes(b"\x00\x00")

        exclude_patterns = ["*.log", "*.tmp", "__pycache__/**"]

        # Build ZIP with excludes
        zip_builder = ZipBuilder(run_dir)
        for pattern in exclude_patterns:
            zip_builder.exclude(pattern)
        zip_path = tmp_path / "bundle.zip"
        zip_builder.build(zip_path)

        # Build manifest with same excludes
        manifest_builder = ManifestBuilder(run_dir)
        for pattern in exclude_patterns:
            manifest_builder.exclude(pattern)
        manifest_builder.include_checksums()
        manifest = manifest_builder.to_dict()

        # Verify both exclude the same files
        with zipfile.ZipFile(zip_path) as zf:
            zip_files = set(zf.namelist())

        manifest_files = set(manifest["checksums"].keys())

        # Both should only contain keep.md
        assert zip_files == {"keep.md"}
        assert manifest_files == {"keep.md"}


class TestBundleEndpointIntegration:
    """Integration tests for bundle endpoint with real database."""

    @pytest.fixture
    def test_client(self):
        """Create test client with temporary database."""
        from procedurewriter.settings import settings
        original_data_dir = settings.data_dir

        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            (data_dir / "index").mkdir(parents=True, exist_ok=True)
            runs_dir = data_dir / "runs"
            runs_dir.mkdir(parents=True, exist_ok=True)
            db_path = data_dir / "index" / "runs.sqlite3"
            init_db(db_path)

            settings.data_dir = data_dir

            try:
                with TestClient(app) as client:
                    yield client, db_path, runs_dir
            finally:
                settings.data_dir = original_data_dir

    def _create_complete_run(
        self, conn, run_id: str, runs_dir: Path, procedure: str = "Test Procedure"
    ) -> Path:
        """Create a complete run with all expected files."""
        run_dir = runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        # Create run in database
        conn.execute(
            """
            INSERT INTO runs (run_id, run_dir, created_at_utc, updated_at_utc, procedure, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (run_id, str(run_dir), "2024-12-22T00:00:00Z", "2024-12-22T00:00:00Z", procedure, "DONE"),
        )

        # Create realistic run files
        (run_dir / "procedure.md").write_text(
            f"# {procedure}\n\n## Indikationer\n- Test indikation",
            encoding="utf-8",
        )
        (run_dir / "Procedure.docx").write_bytes(b"PK\x03\x04DOCX_FAKE_CONTENT")
        (run_dir / "sources.jsonl").write_text(
            '{"source_id": "src-001", "title": "Guidelines"}\n'
            '{"source_id": "src-002", "title": "Study"}\n',
            encoding="utf-8",
        )
        (run_dir / "claims.json").write_text(
            json.dumps([
                {"claim_type": "DOSE", "text": "10 mg morfin"},
                {"claim_type": "THRESHOLD", "text": "BP < 90 mmHg"},
            ]),
            encoding="utf-8",
        )
        (run_dir / "run_manifest.json").write_text(
            json.dumps({"version": "1.0.0", "run_id": run_id}),
            encoding="utf-8",
        )

        return run_dir

    def test_bundle_endpoint_returns_valid_zip_with_all_files(self, test_client):
        """GET /api/runs/{id}/bundle should return ZIP with all run files."""
        client, db_path, runs_dir = test_client
        run_id = uuid4().hex

        with _connect(db_path) as conn:
            self._create_complete_run(conn, run_id, runs_dir, "Akut Astma")

        response = client.get(f"/api/runs/{run_id}/bundle")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"

        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            names = set(zf.namelist())
            assert "procedure.md" in names
            assert "Procedure.docx" in names
            assert "sources.jsonl" in names
            assert "claims.json" in names
            assert "run_manifest.json" in names

    def test_bundle_endpoint_preserves_file_contents(self, test_client):
        """Bundle should preserve exact file contents."""
        client, db_path, runs_dir = test_client
        run_id = uuid4().hex

        with _connect(db_path) as conn:
            run_dir = self._create_complete_run(conn, run_id, runs_dir, "Test")

        # Get the original content
        original_claims = (run_dir / "claims.json").read_text(encoding="utf-8")

        response = client.get(f"/api/runs/{run_id}/bundle")
        assert response.status_code == 200

        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            bundled_claims = zf.read("claims.json").decode("utf-8")
            assert bundled_claims == original_claims

    def test_bundle_from_large_run_directory(self, test_client):
        """Bundle should handle runs with many files efficiently."""
        client, db_path, runs_dir = test_client
        run_id = uuid4().hex

        with _connect(db_path) as conn:
            run_dir = self._create_complete_run(conn, run_id, runs_dir)

        # Add many source files
        sources_dir = run_dir / "sources"
        sources_dir.mkdir()
        for i in range(50):
            (sources_dir / f"source_{i:03d}.xml").write_text(
                f"<source id='{i}'/>\n" * 100,
                encoding="utf-8",
            )

        response = client.get(f"/api/runs/{run_id}/bundle")
        assert response.status_code == 200

        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            names = zf.namelist()
            # Should have 50 source files plus the base files
            source_files = [n for n in names if n.startswith("sources/")]
            assert len(source_files) == 50


class TestManifestZipIntegrity:
    """Tests for verifying manifest and ZIP integrity match."""

    def test_manifest_sha256_is_reproducible(self, tmp_path: Path):
        """Building manifest twice should produce same SHA256."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "test.txt").write_text("content", encoding="utf-8")

        # Build manifest twice with same inputs
        builder1 = (
            ManifestBuilder(run_dir)
            .set_run_id("fixed-id")
            .set_procedure("Fixed Procedure")
            .set_version("1.0.0")
            .set_created_at("2024-12-22T00:00:00Z")
            .include_checksums()
        )
        sha1 = builder1.build(tmp_path / "manifest1.json")

        builder2 = (
            ManifestBuilder(run_dir)
            .set_run_id("fixed-id")
            .set_procedure("Fixed Procedure")
            .set_version("1.0.0")
            .set_created_at("2024-12-22T00:00:00Z")
            .include_checksums()
        )
        sha2 = builder2.build(tmp_path / "manifest2.json")

        assert sha1 == sha2

    def test_manifest_in_zip_verifiable(self, tmp_path: Path):
        """Manifest in ZIP should be verifiable against its SHA256."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "procedure.md").write_text("# Procedure", encoding="utf-8")

        # Build manifest
        manifest_builder = (
            ManifestBuilder(run_dir)
            .set_run_id("test-id")
            .set_procedure("Test")
            .set_version("1.0.0")
            .set_created_at("2024-12-22T00:00:00Z")
            .include_checksums()
        )
        manifest_path = run_dir / "manifest.json"
        expected_sha = manifest_builder.build(manifest_path)

        # Build ZIP with manifest
        zip_builder = ZipBuilder(run_dir)
        zip_path = tmp_path / "bundle.zip"
        zip_builder.build(zip_path)

        # Extract manifest from ZIP and verify SHA256
        with zipfile.ZipFile(zip_path) as zf:
            manifest_content = zf.read("manifest.json")
            actual_sha = hashlib.sha256(manifest_content).hexdigest()

        assert actual_sha == expected_sha

    def test_file_modification_changes_checksum(self, tmp_path: Path):
        """Modifying a file after manifest creation should break checksum verification."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        test_file = run_dir / "procedure.md"
        test_file.write_text("# Original", encoding="utf-8")

        # Build manifest
        manifest_builder = ManifestBuilder(run_dir).include_checksums()
        manifest = manifest_builder.to_dict()
        original_checksum = manifest["checksums"]["procedure.md"]

        # Modify the file
        test_file.write_text("# Modified", encoding="utf-8")

        # Calculate new checksum
        new_content = test_file.read_bytes()
        new_checksum = hashlib.sha256(new_content).hexdigest()

        # Checksums should differ
        assert original_checksum != new_checksum

    def test_bundle_verification_workflow(self, tmp_path: Path):
        """Complete verification workflow: build bundle, verify all checksums."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        # Create run files
        files_content = {
            "procedure.md": "# Akut Behandling\n\nIndhold på dansk.",
            "claims.json": '[{"type": "DOSE", "text": "10 mg"}]',
            "evidence.md": "## Evidens\n\nBaseret på danske guidelines.",
        }
        for filename, content in files_content.items():
            (run_dir / filename).write_text(content, encoding="utf-8")

        # Build manifest and ZIP
        manifest_builder = (
            ManifestBuilder(run_dir)
            .set_run_id("verification-test")
            .set_procedure("Verification Test")
            .set_version("1.0.0")
            .set_created_at("2024-12-22T00:00:00Z")
            .include_checksums()
        )
        manifest_path = run_dir / "manifest.json"
        manifest_sha = manifest_builder.build(manifest_path)

        zip_builder = ZipBuilder(run_dir)
        zip_path = tmp_path / "bundle.zip"
        zip_builder.build(zip_path)

        # Verification: Extract and verify all checksums
        with zipfile.ZipFile(zip_path) as zf:
            # Load manifest
            manifest_content = zf.read("manifest.json")
            manifest = json.loads(manifest_content.decode("utf-8"))

            # Verify manifest SHA256
            assert hashlib.sha256(manifest_content).hexdigest() == manifest_sha

            # Verify all file checksums
            for filename, expected_sha in manifest["checksums"].items():
                if filename == "manifest.json":
                    continue
                file_content = zf.read(filename)
                actual_sha = hashlib.sha256(file_content).hexdigest()
                assert actual_sha == expected_sha, f"Checksum failed for {filename}"

        # All verifications passed


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_run_directory(self, tmp_path: Path):
        """Should handle empty run directory gracefully."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        # Build ZIP
        zip_builder = ZipBuilder(run_dir)
        zip_path = tmp_path / "bundle.zip"
        zip_builder.build(zip_path)

        # Build manifest
        manifest_builder = ManifestBuilder(run_dir).include_checksums()
        manifest = manifest_builder.to_dict()

        # Both should work with empty data
        with zipfile.ZipFile(zip_path) as zf:
            assert zf.namelist() == []
        assert manifest["checksums"] == {}

    def test_deeply_nested_directory_structure(self, tmp_path: Path):
        """Should handle deeply nested directory structures."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        # Create deeply nested file
        deep_dir = run_dir / "a" / "b" / "c" / "d"
        deep_dir.mkdir(parents=True)
        (deep_dir / "deep.txt").write_text("deep content", encoding="utf-8")

        zip_builder = ZipBuilder(run_dir)
        zip_path = tmp_path / "bundle.zip"
        zip_builder.build(zip_path)

        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            assert "a/b/c/d/deep.txt" in names

    def test_special_characters_in_filenames(self, tmp_path: Path):
        """Should handle files with special characters in names."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        # Create files with special characters (safe for most filesystems)
        (run_dir / "file-with-dash.md").write_text("content", encoding="utf-8")
        (run_dir / "file_with_underscore.md").write_text("content", encoding="utf-8")
        (run_dir / "file.multiple.dots.md").write_text("content", encoding="utf-8")

        zip_builder = ZipBuilder(run_dir)
        zip_path = tmp_path / "bundle.zip"
        zip_builder.build(zip_path)

        with zipfile.ZipFile(zip_path) as zf:
            names = set(zf.namelist())
            assert "file-with-dash.md" in names
            assert "file_with_underscore.md" in names
            assert "file.multiple.dots.md" in names

    def test_large_file_handling(self, tmp_path: Path):
        """Should handle large files with compression."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        # Create a large file (1MB of repetitive content - compresses well)
        large_content = "Lorem ipsum dolor sit amet. " * 50000
        (run_dir / "large.txt").write_text(large_content, encoding="utf-8")

        zip_builder = ZipBuilder(run_dir)
        zip_path = tmp_path / "bundle.zip"
        zip_builder.build(zip_path)

        # ZIP should be smaller than original due to compression
        original_size = len(large_content.encode("utf-8"))
        zip_size = zip_path.stat().st_size
        assert zip_size < original_size

        # Content should be preserved
        with zipfile.ZipFile(zip_path) as zf:
            extracted = zf.read("large.txt").decode("utf-8")
            assert extracted == large_content

    def test_binary_files_preserved(self, tmp_path: Path):
        """Should preserve binary files exactly."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        # Create binary content
        binary_content = bytes(range(256)) * 100
        (run_dir / "binary.dat").write_bytes(binary_content)

        zip_builder = ZipBuilder(run_dir)
        zip_path = tmp_path / "bundle.zip"
        zip_builder.build(zip_path)

        with zipfile.ZipFile(zip_path) as zf:
            extracted = zf.read("binary.dat")
            assert extracted == binary_content
