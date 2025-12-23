"""Tests for GET /api/runs/{run_id}/issues endpoint.

TDD: Tests define the API contract for retrieving issues for a run.

Run: pytest tests/api/test_issues_endpoint.py -v
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from procedurewriter.main import app
from procedurewriter.db import init_db, _connect
from procedurewriter.models.issues import Issue, IssueCode, IssueSeverity


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


class TestGetIssues:
    """Tests for GET /api/runs/{run_id}/issues endpoint."""

    def test_get_issues_empty(self, test_client):
        """Should return empty list when run has no issues."""
        client, db_path, runs_dir = test_client
        run_id = uuid4().hex

        with _connect(db_path) as conn:
            _create_run(conn, run_id, runs_dir)

        response = client.get(f"/api/runs/{run_id}/issues")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_issues_returns_all_issues_for_run(self, test_client):
        """Should return all issues for the specified run."""
        client, db_path, runs_dir = test_client
        run_id = uuid4().hex

        with _connect(db_path) as conn:
            _create_run(conn, run_id, runs_dir)

            # Insert 3 issues
            for i in range(3):
                issue = Issue(
                    run_id=run_id,
                    code=IssueCode.DOSE_WITHOUT_EVIDENCE,
                    severity=IssueSeverity.S0,
                    message=f"Test issue {i}",
                    line_number=i + 10,
                )
                conn.execute(
                    """
                    INSERT INTO issues (
                        id, run_id, code, severity, message, line_number, claim_id, source_id,
                        auto_detected, resolved, resolution_note, resolved_at_utc, created_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    issue.to_db_row(),
                )

        response = client.get(f"/api/runs/{run_id}/issues")
        assert response.status_code == 200

        issues = response.json()
        assert len(issues) == 3

        # Verify issue structure
        for issue in issues:
            assert "id" in issue
            assert "run_id" in issue
            assert issue["run_id"] == run_id
            assert "code" in issue
            assert "severity" in issue
            assert "message" in issue
            assert "line_number" in issue
            assert "auto_detected" in issue
            assert "resolved" in issue
            assert "created_at" in issue

    def test_get_issues_run_not_found(self, test_client):
        """Should return 404 when run does not exist."""
        client, _, _ = test_client
        fake_run_id = uuid4().hex

        response = client.get(f"/api/runs/{fake_run_id}/issues")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_issues_different_severities(self, test_client):
        """Should return issues of different severities."""
        client, db_path, runs_dir = test_client
        run_id = uuid4().hex

        with _connect(db_path) as conn:
            _create_run(conn, run_id, runs_dir)

            # Insert issues of different severities
            severity_codes = [
                (IssueSeverity.S0, IssueCode.DOSE_WITHOUT_EVIDENCE),
                (IssueSeverity.S1, IssueCode.CLAIM_BINDING_FAILED),
                (IssueSeverity.S2, IssueCode.INFORMAL_LANGUAGE),
            ]
            for i, (severity, code) in enumerate(severity_codes):
                issue = Issue(
                    run_id=run_id,
                    code=code,
                    severity=severity,
                    message=f"Issue with {severity.value}",
                    line_number=i + 1,
                )
                conn.execute(
                    """
                    INSERT INTO issues (
                        id, run_id, code, severity, message, line_number, claim_id, source_id,
                        auto_detected, resolved, resolution_note, resolved_at_utc, created_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    issue.to_db_row(),
                )

        response = client.get(f"/api/runs/{run_id}/issues")
        assert response.status_code == 200

        issues = response.json()
        assert len(issues) == 3

        # Verify different severities returned
        severities_found = {i["severity"] for i in issues}
        assert severities_found == {"s0", "s1", "s2"}

    def test_get_issues_does_not_return_other_runs_issues(self, test_client):
        """Should only return issues for the specified run, not others."""
        client, db_path, runs_dir = test_client
        run_id_1 = uuid4().hex
        run_id_2 = uuid4().hex

        with _connect(db_path) as conn:
            # Create two runs
            _create_run(conn, run_id_1, runs_dir)
            _create_run(conn, run_id_2, runs_dir)

            # Add 2 issues to run 1
            for i in range(2):
                issue = Issue(
                    run_id=run_id_1,
                    code=IssueCode.DOSE_WITHOUT_EVIDENCE,
                    severity=IssueSeverity.S0,
                    message=f"Run 1 issue {i}",
                    line_number=i + 1,
                )
                conn.execute(
                    """
                    INSERT INTO issues (
                        id, run_id, code, severity, message, line_number, claim_id, source_id,
                        auto_detected, resolved, resolution_note, resolved_at_utc, created_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    issue.to_db_row(),
                )

            # Add 3 issues to run 2
            for i in range(3):
                issue = Issue(
                    run_id=run_id_2,
                    code=IssueCode.CLAIM_BINDING_FAILED,
                    severity=IssueSeverity.S1,
                    message=f"Run 2 issue {i}",
                    line_number=i + 1,
                )
                conn.execute(
                    """
                    INSERT INTO issues (
                        id, run_id, code, severity, message, line_number, claim_id, source_id,
                        auto_detected, resolved, resolution_note, resolved_at_utc, created_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    issue.to_db_row(),
                )

        # Get issues for run 1
        response = client.get(f"/api/runs/{run_id_1}/issues")
        assert response.status_code == 200
        issues = response.json()
        assert len(issues) == 2
        assert all(i["run_id"] == run_id_1 for i in issues)

        # Get issues for run 2
        response = client.get(f"/api/runs/{run_id_2}/issues")
        assert response.status_code == 200
        issues = response.json()
        assert len(issues) == 3
        assert all(i["run_id"] == run_id_2 for i in issues)

    def test_get_issues_filter_by_severity(self, test_client):
        """Should filter issues by severity when severity query param is provided."""
        client, db_path, runs_dir = test_client
        run_id = uuid4().hex

        with _connect(db_path) as conn:
            _create_run(conn, run_id, runs_dir)

            # Insert issues of different severities
            issues_data = [
                (IssueSeverity.S0, IssueCode.DOSE_WITHOUT_EVIDENCE),
                (IssueSeverity.S0, IssueCode.THRESHOLD_WITHOUT_EVIDENCE),
                (IssueSeverity.S1, IssueCode.CLAIM_BINDING_FAILED),
            ]
            for i, (severity, code) in enumerate(issues_data):
                issue = Issue(
                    run_id=run_id,
                    code=code,
                    severity=severity,
                    message=f"Issue {i}",
                    line_number=i + 1,
                )
                conn.execute(
                    """
                    INSERT INTO issues (
                        id, run_id, code, severity, message, line_number, claim_id, source_id,
                        auto_detected, resolved, resolution_note, resolved_at_utc, created_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    issue.to_db_row(),
                )

        # Filter by S0 severity
        response = client.get(f"/api/runs/{run_id}/issues?severity=s0")
        assert response.status_code == 200
        issues = response.json()
        assert len(issues) == 2
        assert all(i["severity"] == "s0" for i in issues)

        # Filter by S1 severity
        response = client.get(f"/api/runs/{run_id}/issues?severity=s1")
        assert response.status_code == 200
        issues = response.json()
        assert len(issues) == 1
        assert issues[0]["severity"] == "s1"

    def test_get_issues_invalid_severity_filter(self, test_client):
        """Should return 400 for invalid severity filter."""
        client, db_path, runs_dir = test_client
        run_id = uuid4().hex

        with _connect(db_path) as conn:
            _create_run(conn, run_id, runs_dir)

        response = client.get(f"/api/runs/{run_id}/issues?severity=invalid")
        assert response.status_code == 400
        assert "invalid" in response.json()["detail"].lower()

    def test_get_issues_with_claim_id(self, test_client):
        """Should correctly return issues with associated claim IDs."""
        client, db_path, runs_dir = test_client
        run_id = uuid4().hex
        claim_id = uuid4()

        with _connect(db_path) as conn:
            _create_run(conn, run_id, runs_dir)

            # Create the claim first (FK constraint requires this)
            from datetime import datetime, UTC
            now = datetime.now(UTC).isoformat()
            conn.execute(
                """
                INSERT INTO claims (
                    id, run_id, claim_type, text, normalized_value, unit,
                    source_refs_json, line_number, confidence, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(claim_id), run_id, "dose", "Test claim text",
                    "10", "mg", "[]", 1, 0.95, now
                ),
            )

            issue = Issue(
                run_id=run_id,
                code=IssueCode.DOSE_WITHOUT_EVIDENCE,
                severity=IssueSeverity.S0,
                message="Issue with claim reference",
                claim_id=claim_id,
                line_number=1,
            )
            conn.execute(
                """
                INSERT INTO issues (
                    id, run_id, code, severity, message, line_number, claim_id, source_id,
                    auto_detected, resolved, resolution_note, resolved_at_utc, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                issue.to_db_row(),
            )

        response = client.get(f"/api/runs/{run_id}/issues")
        assert response.status_code == 200

        issues = response.json()
        assert len(issues) == 1
        assert issues[0]["claim_id"] == str(claim_id)

    def test_get_issues_resolved_status(self, test_client):
        """Should correctly return resolved status and resolution details."""
        client, db_path, runs_dir = test_client
        run_id = uuid4().hex

        with _connect(db_path) as conn:
            _create_run(conn, run_id, runs_dir)

            # Create an unresolved issue
            issue1 = Issue(
                run_id=run_id,
                code=IssueCode.DOSE_WITHOUT_EVIDENCE,
                severity=IssueSeverity.S0,
                message="Unresolved issue",
                line_number=1,
                resolved=False,
            )
            conn.execute(
                """
                INSERT INTO issues (
                    id, run_id, code, severity, message, line_number, claim_id, source_id,
                    auto_detected, resolved, resolution_note, resolved_at_utc, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                issue1.to_db_row(),
            )

        response = client.get(f"/api/runs/{run_id}/issues")
        assert response.status_code == 200

        issues = response.json()
        assert len(issues) == 1
        assert issues[0]["resolved"] is False
