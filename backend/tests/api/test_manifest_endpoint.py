"""Tests for GET /api/runs/{run_id}/manifest endpoint.

TDD: Tests define the API contract for retrieving run manifest with metadata.

Run: pytest tests/api/test_manifest_endpoint.py -v
"""
from __future__ import annotations

import json
import tempfile
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


class TestGetManifest:
    """Tests for GET /api/runs/{run_id}/manifest endpoint."""

    def test_get_manifest_returns_json(self, test_client):
        """Should return manifest as JSON object."""
        client, db_path, runs_dir = test_client
        run_id = str(uuid4())

        with _connect(db_path) as conn:
            run_dir = _create_run(conn, run_id, runs_dir)

        # Create manifest file
        manifest = {
            "version": "1.0.0",
            "procedure": "Test Procedure",
            "created_at": "2024-12-22T00:00:00Z",
            "runtime": {
                "total_duration_seconds": 120,
                "warnings": [],
            },
        }
        (run_dir / "run_manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

        response = client.get(f"/api/runs/{run_id}/manifest")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

        data = response.json()
        assert data["version"] == "1.0.0"
        assert data["procedure"] == "Test Procedure"

    def test_get_manifest_run_not_found(self, test_client):
        """Should return 404 when run does not exist."""
        client, _, _ = test_client
        fake_run_id = str(uuid4())

        response = client.get(f"/api/runs/{fake_run_id}/manifest")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_manifest_file_not_found(self, test_client):
        """Should return 404 when manifest file does not exist."""
        client, db_path, runs_dir = test_client
        run_id = str(uuid4())

        with _connect(db_path) as conn:
            _create_run(conn, run_id, runs_dir)
            # Don't create manifest file

        response = client.get(f"/api/runs/{run_id}/manifest")
        assert response.status_code == 404
        assert "manifest" in response.json()["detail"].lower()

    def test_get_manifest_includes_runtime_info(self, test_client):
        """Should include runtime information in manifest."""
        client, db_path, runs_dir = test_client
        run_id = str(uuid4())

        with _connect(db_path) as conn:
            run_dir = _create_run(conn, run_id, runs_dir)

        manifest = {
            "version": "1.0.0",
            "runtime": {
                "total_duration_seconds": 250,
                "stage_timings": {
                    "bootstrap": 5,
                    "retrieve": 60,
                    "draft": 120,
                },
                "warnings": ["Low source count"],
            },
        }
        (run_dir / "run_manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

        response = client.get(f"/api/runs/{run_id}/manifest")
        assert response.status_code == 200

        data = response.json()
        assert "runtime" in data
        assert data["runtime"]["total_duration_seconds"] == 250
        assert "stage_timings" in data["runtime"]
        assert data["runtime"]["warnings"] == ["Low source count"]

    def test_get_manifest_includes_sources_info(self, test_client):
        """Should include source information in manifest."""
        client, db_path, runs_dir = test_client
        run_id = str(uuid4())

        with _connect(db_path) as conn:
            run_dir = _create_run(conn, run_id, runs_dir)

        manifest = {
            "version": "1.0.0",
            "sources": {
                "total_count": 15,
                "by_tier": {
                    "danish_guidelines": 3,
                    "international": 7,
                    "pubmed": 5,
                },
            },
        }
        (run_dir / "run_manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

        response = client.get(f"/api/runs/{run_id}/manifest")
        assert response.status_code == 200

        data = response.json()
        assert "sources" in data
        assert data["sources"]["total_count"] == 15

    def test_get_manifest_includes_quality_info(self, test_client):
        """Should include quality metrics in manifest."""
        client, db_path, runs_dir = test_client
        run_id = str(uuid4())

        with _connect(db_path) as conn:
            run_dir = _create_run(conn, run_id, runs_dir)

        manifest = {
            "version": "1.0.0",
            "quality": {
                "final_score": 8.5,
                "iterations_used": 2,
                "gates_passed": ["s0_safety", "s1_quality"],
            },
        }
        (run_dir / "run_manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

        response = client.get(f"/api/runs/{run_id}/manifest")
        assert response.status_code == 200

        data = response.json()
        assert "quality" in data
        assert data["quality"]["final_score"] == 8.5
        assert data["quality"]["iterations_used"] == 2

    def test_get_manifest_preserves_nested_structure(self, test_client):
        """Should preserve nested JSON structure from manifest file."""
        client, db_path, runs_dir = test_client
        run_id = str(uuid4())

        with _connect(db_path) as conn:
            run_dir = _create_run(conn, run_id, runs_dir)

        manifest = {
            "version": "1.0.0",
            "deeply": {
                "nested": {
                    "structure": {
                        "value": 42,
                        "list": [1, 2, 3],
                    }
                }
            },
        }
        (run_dir / "run_manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

        response = client.get(f"/api/runs/{run_id}/manifest")
        assert response.status_code == 200

        data = response.json()
        assert data["deeply"]["nested"]["structure"]["value"] == 42
        assert data["deeply"]["nested"]["structure"]["list"] == [1, 2, 3]

    def test_get_manifest_handles_unicode(self, test_client):
        """Should handle Danish characters in manifest."""
        client, db_path, runs_dir = test_client
        run_id = str(uuid4())

        with _connect(db_path) as conn:
            run_dir = _create_run(conn, run_id, runs_dir)

        manifest = {
            "version": "1.0.0",
            "procedure": "Akut behandling af hypoækmi",
            "author": "Læge Søren Ågaard",
        }
        (run_dir / "run_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )

        response = client.get(f"/api/runs/{run_id}/manifest")
        assert response.status_code == 200

        data = response.json()
        assert data["procedure"] == "Akut behandling af hypoækmi"
        assert data["author"] == "Læge Søren Ågaard"

    def test_get_manifest_includes_checksums(self, test_client):
        """Should include file checksums in manifest if present."""
        client, db_path, runs_dir = test_client
        run_id = str(uuid4())

        with _connect(db_path) as conn:
            run_dir = _create_run(conn, run_id, runs_dir)

        manifest = {
            "version": "1.0.0",
            "checksums": {
                "procedure.md": "sha256:abc123",
                "Procedure.docx": "sha256:def456",
                "sources.jsonl": "sha256:ghi789",
            },
        }
        (run_dir / "run_manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

        response = client.get(f"/api/runs/{run_id}/manifest")
        assert response.status_code == 200

        data = response.json()
        assert "checksums" in data
        assert len(data["checksums"]) == 3
        assert data["checksums"]["procedure.md"] == "sha256:abc123"

    def test_get_manifest_includes_llm_config(self, test_client):
        """Should include LLM configuration in manifest if present."""
        client, db_path, runs_dir = test_client
        run_id = str(uuid4())

        with _connect(db_path) as conn:
            run_dir = _create_run(conn, run_id, runs_dir)

        manifest = {
            "version": "1.0.0",
            "llm_config": {
                "provider": "openai",
                "model": "gpt-4",
                "temperature": 0.7,
            },
            "cost": {
                "total_usd": 0.45,
                "input_tokens": 15000,
                "output_tokens": 5000,
            },
        }
        (run_dir / "run_manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

        response = client.get(f"/api/runs/{run_id}/manifest")
        assert response.status_code == 200

        data = response.json()
        assert "llm_config" in data
        assert data["llm_config"]["provider"] == "openai"
        assert "cost" in data
        assert data["cost"]["total_usd"] == 0.45
