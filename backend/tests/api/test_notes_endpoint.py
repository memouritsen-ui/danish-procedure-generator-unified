"""Tests for GET /api/runs/{run_id}/evidence-notes endpoint.

TDD: Tests define the API contract for retrieving LLM-generated clinical notes.

Run: pytest tests/api/test_notes_endpoint.py -v
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


class TestGetEvidenceNotes:
    """Tests for GET /api/runs/{run_id}/evidence-notes endpoint."""

    def test_get_evidence_notes_returns_json(self, test_client):
        """Should return evidence notes as JSON object."""
        client, db_path, runs_dir = test_client
        run_id = uuid4().hex

        with _connect(db_path) as conn:
            run_dir = _create_run(conn, run_id, runs_dir)

        # Create evidence notes file
        notes = {
            "notes": [
                {
                    "id": str(uuid4()),
                    "chunk_id": str(uuid4()),
                    "summary": "Administrer adrenalin 0.3-0.5 mg intramuskulært.",
                    "source_title": "Anafylaksi Guideline",
                    "source_type": "danish_guideline",
                }
            ],
            "total_notes": 1,
        }
        (run_dir / "evidence_notes.json").write_text(
            json.dumps(notes, ensure_ascii=False), encoding="utf-8"
        )

        response = client.get(f"/api/runs/{run_id}/evidence-notes")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

        data = response.json()
        assert "notes" in data
        assert len(data["notes"]) == 1

    def test_get_evidence_notes_run_not_found(self, test_client):
        """Should return 404 when run does not exist."""
        client, _, _ = test_client
        fake_run_id = uuid4().hex

        response = client.get(f"/api/runs/{fake_run_id}/evidence-notes")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_evidence_notes_file_not_found(self, test_client):
        """Should return 404 when evidence notes file does not exist."""
        client, db_path, runs_dir = test_client
        run_id = uuid4().hex

        with _connect(db_path) as conn:
            _create_run(conn, run_id, runs_dir)
            # Don't create evidence_notes.json file

        response = client.get(f"/api/runs/{run_id}/evidence-notes")
        assert response.status_code == 404
        assert "not available" in response.json()["detail"].lower()

    def test_get_evidence_notes_multiple_notes(self, test_client):
        """Should return all notes from the file."""
        client, db_path, runs_dir = test_client
        run_id = uuid4().hex

        with _connect(db_path) as conn:
            run_dir = _create_run(conn, run_id, runs_dir)

        # Create multiple notes
        notes = {
            "notes": [
                {
                    "id": str(uuid4()),
                    "chunk_id": str(uuid4()),
                    "summary": "Note 1: Initial assessment protocol",
                    "source_title": "Emergency Protocol",
                    "source_type": "guideline",
                },
                {
                    "id": str(uuid4()),
                    "chunk_id": str(uuid4()),
                    "summary": "Note 2: Treatment recommendations",
                    "source_title": "Treatment Guide",
                    "source_type": "review",
                },
                {
                    "id": str(uuid4()),
                    "chunk_id": str(uuid4()),
                    "summary": "Note 3: Follow-up procedures",
                    "source_title": "Follow-up Manual",
                    "source_type": "guideline",
                },
            ],
            "total_notes": 3,
        }
        (run_dir / "evidence_notes.json").write_text(
            json.dumps(notes), encoding="utf-8"
        )

        response = client.get(f"/api/runs/{run_id}/evidence-notes")
        assert response.status_code == 200

        data = response.json()
        assert len(data["notes"]) == 3
        assert data["total_notes"] == 3

    def test_get_evidence_notes_with_metadata(self, test_client):
        """Should include metadata fields in notes."""
        client, db_path, runs_dir = test_client
        run_id = uuid4().hex

        with _connect(db_path) as conn:
            run_dir = _create_run(conn, run_id, runs_dir)

        notes = {
            "notes": [
                {
                    "id": str(uuid4()),
                    "chunk_id": str(uuid4()),
                    "summary": "Clinical note with full metadata",
                    "source_title": "Danish Guidelines 2024",
                    "source_type": "danish_guideline",
                    "created_at": "2024-12-22T10:00:00Z",
                }
            ],
            "total_notes": 1,
            "chunks_processed": 15,
            "chunks_failed": 0,
        }
        (run_dir / "evidence_notes.json").write_text(
            json.dumps(notes), encoding="utf-8"
        )

        response = client.get(f"/api/runs/{run_id}/evidence-notes")
        assert response.status_code == 200

        data = response.json()
        assert data["chunks_processed"] == 15
        assert data["chunks_failed"] == 0
        assert data["notes"][0]["source_title"] == "Danish Guidelines 2024"

    def test_get_evidence_notes_handles_unicode(self, test_client):
        """Should handle Danish characters in notes."""
        client, db_path, runs_dir = test_client
        run_id = uuid4().hex

        with _connect(db_path) as conn:
            run_dir = _create_run(conn, run_id, runs_dir)

        notes = {
            "notes": [
                {
                    "id": str(uuid4()),
                    "chunk_id": str(uuid4()),
                    "summary": "Patienten bør gives væske intravenøst. Obs. på allergi.",
                    "source_title": "Akut behandling af anafylaksi i præhospitalt regi",
                    "source_type": "danish_guideline",
                }
            ],
            "total_notes": 1,
        }
        (run_dir / "evidence_notes.json").write_text(
            json.dumps(notes, ensure_ascii=False), encoding="utf-8"
        )

        response = client.get(f"/api/runs/{run_id}/evidence-notes")
        assert response.status_code == 200

        data = response.json()
        assert "væske" in data["notes"][0]["summary"]
        assert "præhospitalt" in data["notes"][0]["source_title"]

    def test_get_evidence_notes_empty_notes_list(self, test_client):
        """Should handle empty notes list."""
        client, db_path, runs_dir = test_client
        run_id = uuid4().hex

        with _connect(db_path) as conn:
            run_dir = _create_run(conn, run_id, runs_dir)

        notes = {
            "notes": [],
            "total_notes": 0,
        }
        (run_dir / "evidence_notes.json").write_text(
            json.dumps(notes), encoding="utf-8"
        )

        response = client.get(f"/api/runs/{run_id}/evidence-notes")
        assert response.status_code == 200

        data = response.json()
        assert data["notes"] == []
        assert data["total_notes"] == 0

    def test_get_evidence_notes_preserves_structure(self, test_client):
        """Should preserve complete note structure."""
        client, db_path, runs_dir = test_client
        run_id = uuid4().hex
        note_id = str(uuid4())
        chunk_id = str(uuid4())

        with _connect(db_path) as conn:
            run_dir = _create_run(conn, run_id, runs_dir)

        notes = {
            "notes": [
                {
                    "id": note_id,
                    "chunk_id": chunk_id,
                    "summary": "Test clinical note",
                    "source_title": "Test Source",
                    "source_type": "test_type",
                    "created_at": "2024-12-22T10:00:00Z",
                    "extra_field": "preserved",
                }
            ],
            "total_notes": 1,
            "metadata": {
                "generation_model": "gpt-4o-mini",
                "generation_time_seconds": 5.2,
            },
        }
        (run_dir / "evidence_notes.json").write_text(
            json.dumps(notes), encoding="utf-8"
        )

        response = client.get(f"/api/runs/{run_id}/evidence-notes")
        assert response.status_code == 200

        data = response.json()
        assert data["notes"][0]["id"] == note_id
        assert data["notes"][0]["chunk_id"] == chunk_id
        assert data["notes"][0]["extra_field"] == "preserved"
        assert "metadata" in data
        assert data["metadata"]["generation_model"] == "gpt-4o-mini"

    def test_get_evidence_notes_different_source_types(self, test_client):
        """Should return notes with various source types."""
        client, db_path, runs_dir = test_client
        run_id = uuid4().hex

        with _connect(db_path) as conn:
            run_dir = _create_run(conn, run_id, runs_dir)

        notes = {
            "notes": [
                {
                    "id": str(uuid4()),
                    "chunk_id": str(uuid4()),
                    "summary": "Danish guideline note",
                    "source_title": "Sundhedsstyrelsen",
                    "source_type": "danish_guideline",
                },
                {
                    "id": str(uuid4()),
                    "chunk_id": str(uuid4()),
                    "summary": "Systematic review note",
                    "source_title": "Cochrane Review",
                    "source_type": "systematic_review",
                },
                {
                    "id": str(uuid4()),
                    "chunk_id": str(uuid4()),
                    "summary": "International guideline note",
                    "source_title": "NICE Guidelines",
                    "source_type": "international_guideline",
                },
            ],
            "total_notes": 3,
        }
        (run_dir / "evidence_notes.json").write_text(
            json.dumps(notes), encoding="utf-8"
        )

        response = client.get(f"/api/runs/{run_id}/evidence-notes")
        assert response.status_code == 200

        data = response.json()
        source_types = {note["source_type"] for note in data["notes"]}
        assert source_types == {"danish_guideline", "systematic_review", "international_guideline"}
