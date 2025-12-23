"""Tests for GET /api/runs/{run_id}/chunks endpoint.

TDD: Tests define the API contract for retrieving evidence chunks.

Run: pytest tests/api/test_chunks_endpoint.py -v
"""
from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from procedurewriter.main import app
from procedurewriter.db import init_db, _connect
from procedurewriter.models.evidence import EvidenceChunk


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


def _create_evidence_chunk(conn, run_id: str, source_id: str, text: str, chunk_index: int = 0) -> EvidenceChunk:
    """Helper to create an evidence chunk in the database."""
    chunk = EvidenceChunk(
        run_id=run_id,
        source_id=source_id,
        text=text,
        chunk_index=chunk_index,
        created_at=datetime.now(timezone.utc),
    )
    conn.execute(
        """
        INSERT INTO evidence_chunks (
            id, run_id, source_id, text, chunk_index, start_char, end_char,
            embedding_vector_json, metadata_json, created_at_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        chunk.to_db_row(),
    )
    return chunk


class TestGetEvidenceChunks:
    """Tests for GET /api/runs/{run_id}/chunks endpoint."""

    def test_get_chunks_returns_json_list(self, test_client):
        """Should return evidence chunks as JSON array."""
        client, db_path, runs_dir = test_client
        run_id = uuid4().hex

        with _connect(db_path) as conn:
            _create_run(conn, run_id, runs_dir)
            _create_evidence_chunk(
                conn, run_id, "SRC001", "Evidence text about treatment.", chunk_index=0
            )
            conn.commit()

        response = client.get(f"/api/runs/{run_id}/chunks")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["source_id"] == "SRC001"
        assert data[0]["text"] == "Evidence text about treatment."

    def test_get_chunks_run_not_found(self, test_client):
        """Should return 404 when run does not exist."""
        client, _, _ = test_client
        fake_run_id = uuid4().hex

        response = client.get(f"/api/runs/{fake_run_id}/chunks")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_chunks_empty_list(self, test_client):
        """Should return empty list when no chunks exist."""
        client, db_path, runs_dir = test_client
        run_id = uuid4().hex

        with _connect(db_path) as conn:
            _create_run(conn, run_id, runs_dir)
            conn.commit()

        response = client.get(f"/api/runs/{run_id}/chunks")
        assert response.status_code == 200

        data = response.json()
        assert data == []

    def test_get_chunks_multiple_chunks(self, test_client):
        """Should return all chunks for the run."""
        client, db_path, runs_dir = test_client
        run_id = uuid4().hex

        with _connect(db_path) as conn:
            _create_run(conn, run_id, runs_dir)
            _create_evidence_chunk(conn, run_id, "SRC001", "First chunk", chunk_index=0)
            _create_evidence_chunk(conn, run_id, "SRC001", "Second chunk", chunk_index=1)
            _create_evidence_chunk(conn, run_id, "SRC002", "Third chunk", chunk_index=0)
            conn.commit()

        response = client.get(f"/api/runs/{run_id}/chunks")
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 3

    def test_get_chunks_filter_by_source_id(self, test_client):
        """Should filter chunks by source_id when provided."""
        client, db_path, runs_dir = test_client
        run_id = uuid4().hex

        with _connect(db_path) as conn:
            _create_run(conn, run_id, runs_dir)
            _create_evidence_chunk(conn, run_id, "SRC001", "First chunk", chunk_index=0)
            _create_evidence_chunk(conn, run_id, "SRC002", "Second chunk", chunk_index=0)
            _create_evidence_chunk(conn, run_id, "SRC001", "Third chunk", chunk_index=1)
            conn.commit()

        response = client.get(f"/api/runs/{run_id}/chunks?source_id=SRC001")
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 2
        assert all(chunk["source_id"] == "SRC001" for chunk in data)

    def test_get_chunks_filter_returns_empty_for_nonexistent_source(self, test_client):
        """Should return empty list when filtering by non-existent source_id."""
        client, db_path, runs_dir = test_client
        run_id = uuid4().hex

        with _connect(db_path) as conn:
            _create_run(conn, run_id, runs_dir)
            _create_evidence_chunk(conn, run_id, "SRC001", "First chunk", chunk_index=0)
            conn.commit()

        response = client.get(f"/api/runs/{run_id}/chunks?source_id=NONEXISTENT")
        assert response.status_code == 200

        data = response.json()
        assert data == []

    def test_get_chunks_includes_metadata(self, test_client):
        """Should include metadata in chunk response."""
        client, db_path, runs_dir = test_client
        run_id = uuid4().hex

        with _connect(db_path) as conn:
            _create_run(conn, run_id, runs_dir)
            chunk = EvidenceChunk(
                run_id=run_id,
                source_id="SRC001",
                text="Evidence with metadata",
                chunk_index=0,
                start_char=100,
                end_char=200,
                metadata={"section": "treatment", "page": 5},
            )
            conn.execute(
                """
                INSERT INTO evidence_chunks (
                    id, run_id, source_id, text, chunk_index, start_char, end_char,
                    embedding_vector_json, metadata_json, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                chunk.to_db_row(),
            )
            conn.commit()

        response = client.get(f"/api/runs/{run_id}/chunks")
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 1
        assert data[0]["start_char"] == 100
        assert data[0]["end_char"] == 200
        assert data[0]["metadata"]["section"] == "treatment"
        assert data[0]["metadata"]["page"] == 5

    def test_get_chunks_ordered_by_chunk_index(self, test_client):
        """Should return chunks ordered by source_id then chunk_index."""
        client, db_path, runs_dir = test_client
        run_id = uuid4().hex

        with _connect(db_path) as conn:
            _create_run(conn, run_id, runs_dir)
            # Insert in non-sequential order
            _create_evidence_chunk(conn, run_id, "SRC001", "Chunk 2", chunk_index=2)
            _create_evidence_chunk(conn, run_id, "SRC001", "Chunk 0", chunk_index=0)
            _create_evidence_chunk(conn, run_id, "SRC001", "Chunk 1", chunk_index=1)
            conn.commit()

        response = client.get(f"/api/runs/{run_id}/chunks")
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 3
        # Should be ordered by chunk_index
        assert data[0]["chunk_index"] == 0
        assert data[1]["chunk_index"] == 1
        assert data[2]["chunk_index"] == 2

    def test_get_chunks_handles_unicode(self, test_client):
        """Should handle Danish characters in chunk text."""
        client, db_path, runs_dir = test_client
        run_id = uuid4().hex

        danish_text = "Patienten bør gives væske intravenøst. Obs. på allergi."

        with _connect(db_path) as conn:
            _create_run(conn, run_id, runs_dir)
            _create_evidence_chunk(conn, run_id, "SRC001", danish_text, chunk_index=0)
            conn.commit()

        response = client.get(f"/api/runs/{run_id}/chunks")
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 1
        assert "væske" in data[0]["text"]
        assert "intravenøst" in data[0]["text"]
