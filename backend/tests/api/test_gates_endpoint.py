"""Tests for GET /api/runs/{run_id}/gates endpoint.

TDD: Tests define the API contract for retrieving gates for a run.

Run: pytest tests/api/test_gates_endpoint.py -v
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from procedurewriter.main import app
from procedurewriter.db import init_db, _connect
from procedurewriter.models.gates import Gate, GateType, GateStatus


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


class TestGetGates:
    """Tests for GET /api/runs/{run_id}/gates endpoint."""

    def test_get_gates_empty(self, test_client):
        """Should return empty list when run has no gates."""
        client, db_path, runs_dir = test_client
        run_id = str(uuid4())

        with _connect(db_path) as conn:
            _create_run(conn, run_id, runs_dir)

        response = client.get(f"/api/runs/{run_id}/gates")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_gates_returns_all_gates_for_run(self, test_client):
        """Should return all gates for the specified run."""
        client, db_path, runs_dir = test_client
        run_id = str(uuid4())

        with _connect(db_path) as conn:
            _create_run(conn, run_id, runs_dir)

            # Insert 3 gates
            gate_types = [GateType.S0_SAFETY, GateType.S1_QUALITY, GateType.FINAL]
            for gate_type in gate_types:
                gate = Gate(
                    run_id=run_id,
                    gate_type=gate_type,
                    status=GateStatus.PASS,
                    issues_checked=10,
                    issues_failed=0,
                    message=f"{gate_type.value} gate passed",
                )
                conn.execute(
                    """
                    INSERT INTO gates (
                        id, run_id, gate_type, status, issues_checked, issues_failed,
                        message, created_at_utc, evaluated_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    gate.to_db_row(),
                )

        response = client.get(f"/api/runs/{run_id}/gates")
        assert response.status_code == 200

        gates = response.json()
        assert len(gates) == 3

        # Verify gate structure
        for gate in gates:
            assert "id" in gate
            assert "run_id" in gate
            assert gate["run_id"] == run_id
            assert "gate_type" in gate
            assert "status" in gate
            assert "issues_checked" in gate
            assert "issues_failed" in gate
            assert "message" in gate
            assert "created_at" in gate

    def test_get_gates_run_not_found(self, test_client):
        """Should return 404 when run does not exist."""
        client, _, _ = test_client
        fake_run_id = str(uuid4())

        response = client.get(f"/api/runs/{fake_run_id}/gates")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_gates_different_statuses(self, test_client):
        """Should return gates with different statuses."""
        client, db_path, runs_dir = test_client
        run_id = str(uuid4())

        with _connect(db_path) as conn:
            _create_run(conn, run_id, runs_dir)

            # Insert gates with different statuses
            gate_data = [
                (GateType.S0_SAFETY, GateStatus.PASS, 10, 0),
                (GateType.S1_QUALITY, GateStatus.FAIL, 5, 2),
                (GateType.FINAL, GateStatus.PENDING, 0, 0),
            ]
            for gate_type, status, checked, failed in gate_data:
                gate = Gate(
                    run_id=run_id,
                    gate_type=gate_type,
                    status=status,
                    issues_checked=checked,
                    issues_failed=failed,
                )
                conn.execute(
                    """
                    INSERT INTO gates (
                        id, run_id, gate_type, status, issues_checked, issues_failed,
                        message, created_at_utc, evaluated_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    gate.to_db_row(),
                )

        response = client.get(f"/api/runs/{run_id}/gates")
        assert response.status_code == 200

        gates = response.json()
        assert len(gates) == 3

        # Verify different statuses returned
        statuses_found = {g["status"] for g in gates}
        assert statuses_found == {"pass", "fail", "pending"}

    def test_get_gates_does_not_return_other_runs_gates(self, test_client):
        """Should only return gates for the specified run, not others."""
        client, db_path, runs_dir = test_client
        run_id_1 = str(uuid4())
        run_id_2 = str(uuid4())

        with _connect(db_path) as conn:
            # Create two runs
            _create_run(conn, run_id_1, runs_dir)
            _create_run(conn, run_id_2, runs_dir)

            # Add 2 gates to run 1
            for gate_type in [GateType.S0_SAFETY, GateType.S1_QUALITY]:
                gate = Gate(
                    run_id=run_id_1,
                    gate_type=gate_type,
                    status=GateStatus.PASS,
                    issues_checked=5,
                    issues_failed=0,
                )
                conn.execute(
                    """
                    INSERT INTO gates (
                        id, run_id, gate_type, status, issues_checked, issues_failed,
                        message, created_at_utc, evaluated_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    gate.to_db_row(),
                )

            # Add 3 gates to run 2
            for gate_type in [GateType.S0_SAFETY, GateType.S1_QUALITY, GateType.FINAL]:
                gate = Gate(
                    run_id=run_id_2,
                    gate_type=gate_type,
                    status=GateStatus.FAIL,
                    issues_checked=10,
                    issues_failed=3,
                )
                conn.execute(
                    """
                    INSERT INTO gates (
                        id, run_id, gate_type, status, issues_checked, issues_failed,
                        message, created_at_utc, evaluated_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    gate.to_db_row(),
                )

        # Get gates for run 1
        response = client.get(f"/api/runs/{run_id_1}/gates")
        assert response.status_code == 200
        gates = response.json()
        assert len(gates) == 2
        assert all(g["run_id"] == run_id_1 for g in gates)

        # Get gates for run 2
        response = client.get(f"/api/runs/{run_id_2}/gates")
        assert response.status_code == 200
        gates = response.json()
        assert len(gates) == 3
        assert all(g["run_id"] == run_id_2 for g in gates)

    def test_get_gates_filter_by_status(self, test_client):
        """Should filter gates by status when status query param is provided."""
        client, db_path, runs_dir = test_client
        run_id = str(uuid4())

        with _connect(db_path) as conn:
            _create_run(conn, run_id, runs_dir)

            # Insert gates with different statuses
            gate_data = [
                (GateType.S0_SAFETY, GateStatus.PASS),
                (GateType.S1_QUALITY, GateStatus.PASS),
                (GateType.FINAL, GateStatus.FAIL),
            ]
            for gate_type, status in gate_data:
                gate = Gate(
                    run_id=run_id,
                    gate_type=gate_type,
                    status=status,
                    issues_checked=5,
                    issues_failed=0 if status == GateStatus.PASS else 1,
                )
                conn.execute(
                    """
                    INSERT INTO gates (
                        id, run_id, gate_type, status, issues_checked, issues_failed,
                        message, created_at_utc, evaluated_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    gate.to_db_row(),
                )

        # Filter by pass status
        response = client.get(f"/api/runs/{run_id}/gates?status=pass")
        assert response.status_code == 200
        gates = response.json()
        assert len(gates) == 2
        assert all(g["status"] == "pass" for g in gates)

        # Filter by fail status
        response = client.get(f"/api/runs/{run_id}/gates?status=fail")
        assert response.status_code == 200
        gates = response.json()
        assert len(gates) == 1
        assert gates[0]["status"] == "fail"

    def test_get_gates_invalid_status_filter(self, test_client):
        """Should return 400 for invalid status filter."""
        client, db_path, runs_dir = test_client
        run_id = str(uuid4())

        with _connect(db_path) as conn:
            _create_run(conn, run_id, runs_dir)

        response = client.get(f"/api/runs/{run_id}/gates?status=invalid")
        assert response.status_code == 400
        assert "invalid" in response.json()["detail"].lower()

    def test_get_gates_with_issues_counts(self, test_client):
        """Should correctly return gates with issue counts."""
        client, db_path, runs_dir = test_client
        run_id = str(uuid4())

        with _connect(db_path) as conn:
            _create_run(conn, run_id, runs_dir)

            gate = Gate(
                run_id=run_id,
                gate_type=GateType.S0_SAFETY,
                status=GateStatus.FAIL,
                issues_checked=15,
                issues_failed=3,
                message="3 safety issues found",
            )
            conn.execute(
                """
                INSERT INTO gates (
                    id, run_id, gate_type, status, issues_checked, issues_failed,
                    message, created_at_utc, evaluated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                gate.to_db_row(),
            )

        response = client.get(f"/api/runs/{run_id}/gates")
        assert response.status_code == 200

        gates = response.json()
        assert len(gates) == 1
        assert gates[0]["issues_checked"] == 15
        assert gates[0]["issues_failed"] == 3
        assert gates[0]["message"] == "3 safety issues found"

    def test_get_gates_by_type(self, test_client):
        """Should filter gates by type when type query param is provided."""
        client, db_path, runs_dir = test_client
        run_id = str(uuid4())

        with _connect(db_path) as conn:
            _create_run(conn, run_id, runs_dir)

            # Insert all gate types
            for gate_type in [GateType.S0_SAFETY, GateType.S1_QUALITY, GateType.FINAL]:
                gate = Gate(
                    run_id=run_id,
                    gate_type=gate_type,
                    status=GateStatus.PASS,
                    issues_checked=5,
                    issues_failed=0,
                )
                conn.execute(
                    """
                    INSERT INTO gates (
                        id, run_id, gate_type, status, issues_checked, issues_failed,
                        message, created_at_utc, evaluated_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    gate.to_db_row(),
                )

        # Filter by s0_safety type
        response = client.get(f"/api/runs/{run_id}/gates?type=s0_safety")
        assert response.status_code == 200
        gates = response.json()
        assert len(gates) == 1
        assert gates[0]["gate_type"] == "s0_safety"

        # Filter by final type
        response = client.get(f"/api/runs/{run_id}/gates?type=final")
        assert response.status_code == 200
        gates = response.json()
        assert len(gates) == 1
        assert gates[0]["gate_type"] == "final"

    def test_get_gates_invalid_type_filter(self, test_client):
        """Should return 400 for invalid type filter."""
        client, db_path, runs_dir = test_client
        run_id = str(uuid4())

        with _connect(db_path) as conn:
            _create_run(conn, run_id, runs_dir)

        response = client.get(f"/api/runs/{run_id}/gates?type=invalid_type")
        assert response.status_code == 400
        assert "invalid" in response.json()["detail"].lower()
