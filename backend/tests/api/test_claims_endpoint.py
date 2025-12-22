"""Tests for GET /api/runs/{run_id}/claims endpoint.

TDD: Tests define the API contract for retrieving claims for a run.

Run: pytest tests/api/test_claims_endpoint.py -v
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
from procedurewriter.models.claims import Claim, ClaimType


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


class TestGetClaims:
    """Tests for GET /api/runs/{run_id}/claims endpoint."""

    def test_get_claims_empty(self, test_client):
        """Should return empty list when run has no claims."""
        client, db_path, runs_dir = test_client
        run_id = str(uuid4())

        with _connect(db_path) as conn:
            _create_run(conn, run_id, runs_dir)

        response = client.get(f"/api/runs/{run_id}/claims")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_claims_returns_all_claims_for_run(self, test_client):
        """Should return all claims for the specified run."""
        client, db_path, runs_dir = test_client
        run_id = str(uuid4())

        with _connect(db_path) as conn:
            _create_run(conn, run_id, runs_dir)

            # Insert 3 claims
            for i in range(3):
                claim = Claim(
                    run_id=run_id,
                    claim_type=ClaimType.DOSE,
                    text=f"amoxicillin {10 * (i + 1)} mg/kg/d",
                    normalized_value=str(10 * (i + 1)),
                    unit="mg/kg/d",
                    source_refs=[f"SRC{i:04d}"],
                    line_number=i + 10,
                    confidence=0.85 + i * 0.05,
                )
                conn.execute(
                    """
                    INSERT INTO claims (
                        id, run_id, claim_type, text, normalized_value, unit,
                        source_refs_json, line_number, confidence, created_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    claim.to_db_row(),
                )

        response = client.get(f"/api/runs/{run_id}/claims")
        assert response.status_code == 200

        claims = response.json()
        assert len(claims) == 3

        # Verify claim structure
        for claim in claims:
            assert "id" in claim
            assert "run_id" in claim
            assert claim["run_id"] == run_id
            assert "claim_type" in claim
            assert "text" in claim
            assert "normalized_value" in claim
            assert "unit" in claim
            assert "source_refs" in claim
            assert "line_number" in claim
            assert "confidence" in claim
            assert "created_at" in claim

    def test_get_claims_run_not_found(self, test_client):
        """Should return 404 when run does not exist."""
        client, _, _ = test_client
        fake_run_id = str(uuid4())

        response = client.get(f"/api/runs/{fake_run_id}/claims")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_claims_different_types(self, test_client):
        """Should return claims of different types."""
        client, db_path, runs_dir = test_client
        run_id = str(uuid4())

        with _connect(db_path) as conn:
            _create_run(conn, run_id, runs_dir)

            # Insert claims of different types
            claim_types = [ClaimType.DOSE, ClaimType.THRESHOLD, ClaimType.RECOMMENDATION]
            for i, claim_type in enumerate(claim_types):
                claim = Claim(
                    run_id=run_id,
                    claim_type=claim_type,
                    text=f"Claim text {i}",
                    line_number=i + 1,
                    confidence=0.9,
                )
                conn.execute(
                    """
                    INSERT INTO claims (
                        id, run_id, claim_type, text, normalized_value, unit,
                        source_refs_json, line_number, confidence, created_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    claim.to_db_row(),
                )

        response = client.get(f"/api/runs/{run_id}/claims")
        assert response.status_code == 200

        claims = response.json()
        assert len(claims) == 3

        # Verify different types returned
        types_found = {c["claim_type"] for c in claims}
        assert types_found == {"dose", "threshold", "recommendation"}

    def test_get_claims_does_not_return_other_runs_claims(self, test_client):
        """Should only return claims for the specified run, not others."""
        client, db_path, runs_dir = test_client
        run_id_1 = str(uuid4())
        run_id_2 = str(uuid4())

        with _connect(db_path) as conn:
            # Create two runs
            _create_run(conn, run_id_1, runs_dir)
            _create_run(conn, run_id_2, runs_dir)

            # Add 2 claims to run 1
            for i in range(2):
                claim = Claim(
                    run_id=run_id_1,
                    claim_type=ClaimType.DOSE,
                    text=f"Run 1 claim {i}",
                    line_number=i + 1,
                    confidence=0.9,
                )
                conn.execute(
                    """
                    INSERT INTO claims (
                        id, run_id, claim_type, text, normalized_value, unit,
                        source_refs_json, line_number, confidence, created_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    claim.to_db_row(),
                )

            # Add 3 claims to run 2
            for i in range(3):
                claim = Claim(
                    run_id=run_id_2,
                    claim_type=ClaimType.THRESHOLD,
                    text=f"Run 2 claim {i}",
                    line_number=i + 1,
                    confidence=0.85,
                )
                conn.execute(
                    """
                    INSERT INTO claims (
                        id, run_id, claim_type, text, normalized_value, unit,
                        source_refs_json, line_number, confidence, created_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    claim.to_db_row(),
                )

        # Get claims for run 1
        response = client.get(f"/api/runs/{run_id_1}/claims")
        assert response.status_code == 200
        claims = response.json()
        assert len(claims) == 2
        assert all(c["run_id"] == run_id_1 for c in claims)

        # Get claims for run 2
        response = client.get(f"/api/runs/{run_id_2}/claims")
        assert response.status_code == 200
        claims = response.json()
        assert len(claims) == 3
        assert all(c["run_id"] == run_id_2 for c in claims)

    def test_get_claims_filter_by_type(self, test_client):
        """Should filter claims by type when type query param is provided."""
        client, db_path, runs_dir = test_client
        run_id = str(uuid4())

        with _connect(db_path) as conn:
            _create_run(conn, run_id, runs_dir)

            # Insert claims of different types
            for claim_type in [ClaimType.DOSE, ClaimType.DOSE, ClaimType.THRESHOLD]:
                claim = Claim(
                    run_id=run_id,
                    claim_type=claim_type,
                    text=f"Claim of type {claim_type.value}",
                    line_number=1,
                    confidence=0.9,
                )
                conn.execute(
                    """
                    INSERT INTO claims (
                        id, run_id, claim_type, text, normalized_value, unit,
                        source_refs_json, line_number, confidence, created_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    claim.to_db_row(),
                )

        # Filter by dose type
        response = client.get(f"/api/runs/{run_id}/claims?type=dose")
        assert response.status_code == 200
        claims = response.json()
        assert len(claims) == 2
        assert all(c["claim_type"] == "dose" for c in claims)

        # Filter by threshold type
        response = client.get(f"/api/runs/{run_id}/claims?type=threshold")
        assert response.status_code == 200
        claims = response.json()
        assert len(claims) == 1
        assert claims[0]["claim_type"] == "threshold"

    def test_get_claims_invalid_type_filter(self, test_client):
        """Should return 400 for invalid claim type filter."""
        client, db_path, runs_dir = test_client
        run_id = str(uuid4())

        with _connect(db_path) as conn:
            _create_run(conn, run_id, runs_dir)

        response = client.get(f"/api/runs/{run_id}/claims?type=invalid_type")
        assert response.status_code == 400
        assert "invalid" in response.json()["detail"].lower()

    def test_get_claims_source_refs_deserialized(self, test_client):
        """Should deserialize source_refs from JSON to list."""
        client, db_path, runs_dir = test_client
        run_id = str(uuid4())

        with _connect(db_path) as conn:
            _create_run(conn, run_id, runs_dir)

            claim = Claim(
                run_id=run_id,
                claim_type=ClaimType.DOSE,
                text="Test claim",
                source_refs=["SRC0001", "SRC0002", "SRC0003"],
                line_number=1,
                confidence=0.9,
            )
            conn.execute(
                """
                INSERT INTO claims (
                    id, run_id, claim_type, text, normalized_value, unit,
                    source_refs_json, line_number, confidence, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                claim.to_db_row(),
            )

        response = client.get(f"/api/runs/{run_id}/claims")
        assert response.status_code == 200

        claims = response.json()
        assert len(claims) == 1
        assert claims[0]["source_refs"] == ["SRC0001", "SRC0002", "SRC0003"]
        assert isinstance(claims[0]["source_refs"], list)
