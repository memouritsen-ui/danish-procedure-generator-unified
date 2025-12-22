"""Tests for GET /api/runs/{run_id}/bundle endpoint.

TDD: Tests define the API contract for downloading a complete run bundle as ZIP.

Run: pytest tests/api/test_bundle_endpoint.py -v
"""
from __future__ import annotations

import io
import tempfile
import zipfile
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from procedurewriter.main import app
from procedurewriter.db import init_db, _connect


@pytest.fixture
def test_client():
    """Create test client with temporary database."""
    from procedurewriter.settings import settings
    original_data_dir = settings.data_dir

    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        # Create the index directory for the DB
        (data_dir / "index").mkdir(parents=True, exist_ok=True)
        # Create runs directory for run_dir references
        runs_dir = data_dir / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)
        db_path = data_dir / "index" / "runs.sqlite3"
        init_db(db_path)

        # Directly modify the singleton's data_dir
        settings.data_dir = data_dir

        try:
            with TestClient(app) as client:
                yield client, db_path, runs_dir
        finally:
            # Restore original data_dir
            settings.data_dir = original_data_dir


def _create_run(conn, run_id: str, runs_dir: Path) -> Path:
    """Helper to create a run with required fields."""
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    conn.execute(
        """
        INSERT INTO runs (run_id, run_dir, created_at_utc, updated_at_utc, procedure, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (run_id, str(run_dir), "2024-12-22T00:00:00Z", "2024-12-22T00:00:00Z", "Test", "DONE"),
    )
    return run_dir


class TestGetBundle:
    """Tests for GET /api/runs/{run_id}/bundle endpoint."""

    def test_get_bundle_returns_zip_file(self, test_client):
        """Should return a valid ZIP file for a run."""
        client, db_path, runs_dir = test_client
        run_id = str(uuid4())

        with _connect(db_path) as conn:
            run_dir = _create_run(conn, run_id, runs_dir)

        # Create some test files in the run directory
        (run_dir / "procedure.md").write_text("# Test Procedure", encoding="utf-8")
        (run_dir / "sources.jsonl").write_text('{"source_id": "test"}\n', encoding="utf-8")

        response = client.get(f"/api/runs/{run_id}/bundle")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"

        # Verify it's a valid ZIP
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            names = zf.namelist()
            assert "procedure.md" in names
            assert "sources.jsonl" in names

    def test_get_bundle_run_not_found(self, test_client):
        """Should return 404 when run does not exist."""
        client, _, _ = test_client
        fake_run_id = str(uuid4())

        response = client.get(f"/api/runs/{fake_run_id}/bundle")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_bundle_run_dir_not_found(self, test_client):
        """Should return 404 when run_dir does not exist."""
        client, db_path, runs_dir = test_client
        run_id = str(uuid4())

        # Create run in DB but don't create the run_dir on disk
        with _connect(db_path) as conn:
            nonexistent_dir = runs_dir / run_id
            conn.execute(
                """
                INSERT INTO runs (run_id, run_dir, created_at_utc, updated_at_utc, procedure, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (run_id, str(nonexistent_dir), "2024-12-22T00:00:00Z", "2024-12-22T00:00:00Z", "Test", "DONE"),
            )

        response = client.get(f"/api/runs/{run_id}/bundle")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_bundle_has_correct_filename(self, test_client):
        """Should set correct filename in Content-Disposition header."""
        client, db_path, runs_dir = test_client
        run_id = str(uuid4())

        with _connect(db_path) as conn:
            run_dir = _create_run(conn, run_id, runs_dir)

        # Create a test file
        (run_dir / "test.txt").write_text("test", encoding="utf-8")

        response = client.get(f"/api/runs/{run_id}/bundle")
        assert response.status_code == 200

        content_disposition = response.headers.get("content-disposition", "")
        assert f"{run_id}.zip" in content_disposition

    def test_get_bundle_includes_all_files(self, test_client):
        """Should include all files from the run directory."""
        client, db_path, runs_dir = test_client
        run_id = str(uuid4())

        with _connect(db_path) as conn:
            run_dir = _create_run(conn, run_id, runs_dir)

        # Create multiple files
        (run_dir / "procedure.md").write_text("# Procedure", encoding="utf-8")
        (run_dir / "Procedure.docx").write_bytes(b"DOCX content")
        (run_dir / "sources.jsonl").write_text('{"id": "1"}\n', encoding="utf-8")
        (run_dir / "run_manifest.json").write_text('{"version": "1.0"}', encoding="utf-8")

        response = client.get(f"/api/runs/{run_id}/bundle")
        assert response.status_code == 200

        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            names = zf.namelist()
            assert "procedure.md" in names
            assert "Procedure.docx" in names
            assert "sources.jsonl" in names
            assert "run_manifest.json" in names

    def test_get_bundle_includes_subdirectory_files(self, test_client):
        """Should include files from subdirectories."""
        client, db_path, runs_dir = test_client
        run_id = str(uuid4())

        with _connect(db_path) as conn:
            run_dir = _create_run(conn, run_id, runs_dir)

        # Create subdirectory with files
        sources_dir = run_dir / "sources"
        sources_dir.mkdir()
        (sources_dir / "source1.txt").write_text("Source 1", encoding="utf-8")
        (sources_dir / "source2.txt").write_text("Source 2", encoding="utf-8")

        response = client.get(f"/api/runs/{run_id}/bundle")
        assert response.status_code == 200

        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            names = zf.namelist()
            # Subdirectory files should be included with relative paths
            assert any("sources/source1.txt" in name or "sources\\source1.txt" in name for name in names)
            assert any("sources/source2.txt" in name or "sources\\source2.txt" in name for name in names)

    def test_get_bundle_empty_run_dir(self, test_client):
        """Should return valid but empty ZIP for empty run directory."""
        client, db_path, runs_dir = test_client
        run_id = str(uuid4())

        with _connect(db_path) as conn:
            _create_run(conn, run_id, runs_dir)
            # run_dir exists but is empty

        response = client.get(f"/api/runs/{run_id}/bundle")
        assert response.status_code == 200

        # Should be a valid ZIP, just empty
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            assert zf.namelist() == []

    def test_get_bundle_does_not_include_itself(self, test_client):
        """Should not include the bundle ZIP file itself in the bundle."""
        client, db_path, runs_dir = test_client
        run_id = str(uuid4())

        with _connect(db_path) as conn:
            run_dir = _create_run(conn, run_id, runs_dir)

        # Create some files
        (run_dir / "procedure.md").write_text("# Test", encoding="utf-8")

        response = client.get(f"/api/runs/{run_id}/bundle")
        assert response.status_code == 200

        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            names = zf.namelist()
            # The bundle itself should not be in the bundle
            assert "run_bundle.zip" not in names

    def test_get_bundle_preserves_file_content(self, test_client):
        """Should preserve exact file content in the bundle."""
        client, db_path, runs_dir = test_client
        run_id = str(uuid4())

        with _connect(db_path) as conn:
            run_dir = _create_run(conn, run_id, runs_dir)

        # Create file with specific content
        test_content = "# Pneumoni Behandling\n\nDenne procedure beskriver behandling af pneumoni."
        (run_dir / "procedure.md").write_text(test_content, encoding="utf-8")

        response = client.get(f"/api/runs/{run_id}/bundle")
        assert response.status_code == 200

        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            extracted_content = zf.read("procedure.md").decode("utf-8")
            assert extracted_content == test_content

    def test_get_bundle_multiple_calls_return_fresh_bundle(self, test_client):
        """Should generate fresh bundle on each call."""
        client, db_path, runs_dir = test_client
        run_id = str(uuid4())

        with _connect(db_path) as conn:
            run_dir = _create_run(conn, run_id, runs_dir)

        # Create initial file
        (run_dir / "file1.txt").write_text("Initial", encoding="utf-8")

        response1 = client.get(f"/api/runs/{run_id}/bundle")
        assert response1.status_code == 200

        with zipfile.ZipFile(io.BytesIO(response1.content)) as zf:
            names1 = zf.namelist()
            assert "file1.txt" in names1
            assert "file2.txt" not in names1

        # Add another file
        (run_dir / "file2.txt").write_text("Added later", encoding="utf-8")

        response2 = client.get(f"/api/runs/{run_id}/bundle")
        assert response2.status_code == 200

        with zipfile.ZipFile(io.BytesIO(response2.content)) as zf:
            names2 = zf.namelist()
            assert "file1.txt" in names2
            assert "file2.txt" in names2  # New file should be included
