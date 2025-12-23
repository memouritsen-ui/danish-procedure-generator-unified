"""Tests for claim system database tables and operations.

TDD: These tests verify the database schema and CRUD operations for:
- claims table
- evidence_chunks table
- claim_evidence_links table
- issues table
- gates table

Run: pytest tests/test_db_claims.py -v
"""

import json
import sqlite3
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

from procedurewriter.db import init_db, _connect


@pytest.fixture
def test_db():
    """Create a temporary test database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        init_db(db_path)
        yield db_path


def _create_test_run(conn: sqlite3.Connection, run_id: str) -> None:
    """Helper to create a test run record (for FK constraint satisfaction)."""
    from datetime import datetime, UTC
    now = datetime.now(UTC).isoformat()
    conn.execute(
        """
        INSERT INTO runs (
            run_id, created_at_utc, updated_at_utc, procedure, context,
            status, run_dir, procedure_normalized
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (run_id, now, now, "Test Procedure", None, "QUEUED", "/tmp/test", "test_procedure"),
    )


class TestClaimsTable:
    """Tests for claims table schema and operations."""

    def test_claims_table_exists(self, test_db):
        """Claims table should be created by init_db."""
        with _connect(test_db) as conn:
            result = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='claims'"
            ).fetchone()
            assert result is not None
            assert result[0] == "claims"

    def test_claims_table_schema(self, test_db):
        """Claims table should have correct columns."""
        with _connect(test_db) as conn:
            cursor = conn.execute("PRAGMA table_info(claims)")
            columns = {row[1]: row[2] for row in cursor.fetchall()}

            assert "id" in columns
            assert "run_id" in columns
            assert "claim_type" in columns
            assert "text" in columns
            assert "normalized_value" in columns
            assert "unit" in columns
            assert "source_refs_json" in columns
            assert "line_number" in columns
            assert "confidence" in columns
            assert "created_at_utc" in columns

    def test_claims_table_indexes(self, test_db):
        """Claims table should have appropriate indexes."""
        with _connect(test_db) as conn:
            result = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='claims'"
            ).fetchall()
            index_names = [r[0] for r in result]

            assert "idx_claims_run" in index_names
            assert "idx_claims_type" in index_names

    def test_insert_claim(self, test_db):
        """Should be able to insert a claim."""
        claim_id = str(uuid4())
        run_id = str(uuid4())

        with _connect(test_db) as conn:
            _create_test_run(conn, run_id)
            conn.execute(
                """
                INSERT INTO claims (
                    id, run_id, claim_type, text, normalized_value, unit,
                    source_refs_json, line_number, confidence, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    claim_id,
                    run_id,
                    "dose",
                    "amoxicillin 50 mg/kg/d",
                    "50",
                    "mg/kg/d",
                    json.dumps(["SRC0023"]),
                    15,
                    0.9,
                    "2024-12-22T00:00:00Z",
                ),
            )

            result = conn.execute(
                "SELECT * FROM claims WHERE id = ?", (claim_id,)
            ).fetchone()

            assert result is not None
            assert result[1] == run_id
            assert result[2] == "dose"
            assert result[3] == "amoxicillin 50 mg/kg/d"

    def test_query_claims_by_run(self, test_db):
        """Should be able to query claims by run_id."""
        run_id = str(uuid4())

        with _connect(test_db) as conn:
            _create_test_run(conn, run_id)
            # Insert multiple claims for same run
            for i in range(3):
                conn.execute(
                    """
                    INSERT INTO claims (
                        id, run_id, claim_type, text, source_refs_json,
                        line_number, confidence, created_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        run_id,
                        "dose",
                        f"claim {i}",
                        "[]",
                        i + 1,
                        0.8,
                        "2024-12-22T00:00:00Z",
                    ),
                )

            results = conn.execute(
                "SELECT * FROM claims WHERE run_id = ?", (run_id,)
            ).fetchall()

            assert len(results) == 3


class TestEvidenceChunksTable:
    """Tests for evidence_chunks table schema and operations."""

    def test_evidence_chunks_table_exists(self, test_db):
        """Evidence chunks table should be created by init_db."""
        with _connect(test_db) as conn:
            result = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='evidence_chunks'"
            ).fetchone()
            assert result is not None

    def test_evidence_chunks_table_schema(self, test_db):
        """Evidence chunks table should have correct columns."""
        with _connect(test_db) as conn:
            cursor = conn.execute("PRAGMA table_info(evidence_chunks)")
            columns = {row[1]: row[2] for row in cursor.fetchall()}

            assert "id" in columns
            assert "run_id" in columns
            assert "source_id" in columns
            assert "text" in columns
            assert "chunk_index" in columns
            assert "start_char" in columns
            assert "end_char" in columns
            assert "embedding_vector_json" in columns
            assert "metadata_json" in columns
            assert "created_at_utc" in columns

    def test_insert_evidence_chunk(self, test_db):
        """Should be able to insert an evidence chunk."""
        chunk_id = str(uuid4())
        run_id = str(uuid4())

        with _connect(test_db) as conn:
            _create_test_run(conn, run_id)
            conn.execute(
                """
                INSERT INTO evidence_chunks (
                    id, run_id, source_id, text, chunk_index,
                    start_char, end_char, metadata_json, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk_id,
                    run_id,
                    "SRC0023",
                    "Evidence text here",
                    0,
                    100,
                    200,
                    json.dumps({"section": "treatment"}),
                    "2024-12-22T00:00:00Z",
                ),
            )

            result = conn.execute(
                "SELECT * FROM evidence_chunks WHERE id = ?", (chunk_id,)
            ).fetchone()

            assert result is not None
            assert result[2] == "SRC0023"


class TestClaimEvidenceLinksTable:
    """Tests for claim_evidence_links table schema and operations."""

    def test_links_table_exists(self, test_db):
        """Claim evidence links table should be created by init_db."""
        with _connect(test_db) as conn:
            result = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='claim_evidence_links'"
            ).fetchone()
            assert result is not None

    def test_links_table_schema(self, test_db):
        """Links table should have correct columns."""
        with _connect(test_db) as conn:
            cursor = conn.execute("PRAGMA table_info(claim_evidence_links)")
            columns = {row[1]: row[2] for row in cursor.fetchall()}

            assert "id" in columns
            assert "claim_id" in columns
            assert "evidence_chunk_id" in columns
            assert "binding_type" in columns
            assert "binding_score" in columns
            assert "created_at_utc" in columns

    def test_insert_link(self, test_db):
        """Should be able to insert a claim-evidence link."""
        link_id = str(uuid4())
        run_id = str(uuid4())
        claim_id = str(uuid4())
        chunk_id = str(uuid4())

        with _connect(test_db) as conn:
            # Create dependencies first (FK constraints)
            _create_test_run(conn, run_id)
            conn.execute(
                """
                INSERT INTO claims (id, run_id, claim_type, text, source_refs_json,
                    line_number, confidence, created_at_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (claim_id, run_id, "dose", "test claim", "[]", 1, 0.9, "2024-12-22T00:00:00Z"),
            )
            conn.execute(
                """
                INSERT INTO evidence_chunks (id, run_id, source_id, text, chunk_index,
                    start_char, end_char, metadata_json, created_at_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (chunk_id, run_id, "SRC001", "evidence text", 0, 0, 100, "{}", "2024-12-22T00:00:00Z"),
            )
            conn.execute(
                """
                INSERT INTO claim_evidence_links (
                    id, claim_id, evidence_chunk_id, binding_type,
                    binding_score, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    link_id,
                    claim_id,
                    chunk_id,
                    "semantic",
                    0.92,
                    "2024-12-22T00:00:00Z",
                ),
            )

            result = conn.execute(
                "SELECT * FROM claim_evidence_links WHERE id = ?", (link_id,)
            ).fetchone()

            assert result is not None
            assert result[3] == "semantic"
            assert result[4] == 0.92


class TestIssuesTable:
    """Tests for issues table schema and operations."""

    def test_issues_table_exists(self, test_db):
        """Issues table should be created by init_db."""
        with _connect(test_db) as conn:
            result = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='issues'"
            ).fetchone()
            assert result is not None

    def test_issues_table_schema(self, test_db):
        """Issues table should have correct columns."""
        with _connect(test_db) as conn:
            cursor = conn.execute("PRAGMA table_info(issues)")
            columns = {row[1]: row[2] for row in cursor.fetchall()}

            assert "id" in columns
            assert "run_id" in columns
            assert "code" in columns
            assert "severity" in columns
            assert "message" in columns
            assert "line_number" in columns
            assert "claim_id" in columns
            assert "source_id" in columns
            assert "auto_detected" in columns
            assert "resolved" in columns
            assert "resolution_note" in columns
            assert "resolved_at_utc" in columns
            assert "created_at_utc" in columns

    def test_issues_table_indexes(self, test_db):
        """Issues table should have appropriate indexes."""
        with _connect(test_db) as conn:
            result = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='issues'"
            ).fetchall()
            index_names = [r[0] for r in result]

            assert "idx_issues_run" in index_names
            assert "idx_issues_severity" in index_names
            assert "idx_issues_resolved" in index_names

    def test_insert_issue(self, test_db):
        """Should be able to insert an issue."""
        issue_id = str(uuid4())
        run_id = str(uuid4())

        with _connect(test_db) as conn:
            _create_test_run(conn, run_id)
            conn.execute(
                """
                INSERT INTO issues (
                    id, run_id, code, severity, message,
                    line_number, auto_detected, resolved, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    issue_id,
                    run_id,
                    "S0-003",
                    "s0",
                    "Dose claim without evidence",
                    42,
                    1,
                    0,
                    "2024-12-22T00:00:00Z",
                ),
            )

            result = conn.execute(
                "SELECT * FROM issues WHERE id = ?", (issue_id,)
            ).fetchone()

            assert result is not None
            assert result[2] == "S0-003"
            assert result[3] == "s0"

    def test_query_unresolved_issues(self, test_db):
        """Should be able to query unresolved issues."""
        run_id = str(uuid4())

        with _connect(test_db) as conn:
            _create_test_run(conn, run_id)
            # Insert resolved and unresolved issues
            for i, resolved in enumerate([0, 1, 0, 0]):
                conn.execute(
                    """
                    INSERT INTO issues (
                        id, run_id, code, severity, message,
                        auto_detected, resolved, created_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        run_id,
                        f"S0-00{i}",
                        "s0",
                        f"Issue {i}",
                        1,
                        resolved,
                        "2024-12-22T00:00:00Z",
                    ),
                )

            results = conn.execute(
                "SELECT * FROM issues WHERE run_id = ? AND resolved = 0",
                (run_id,),
            ).fetchall()

            assert len(results) == 3


class TestGatesTable:
    """Tests for gates table schema and operations."""

    def test_gates_table_exists(self, test_db):
        """Gates table should be created by init_db."""
        with _connect(test_db) as conn:
            result = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='gates'"
            ).fetchone()
            assert result is not None

    def test_gates_table_schema(self, test_db):
        """Gates table should have correct columns."""
        with _connect(test_db) as conn:
            cursor = conn.execute("PRAGMA table_info(gates)")
            columns = {row[1]: row[2] for row in cursor.fetchall()}

            assert "id" in columns
            assert "run_id" in columns
            assert "gate_type" in columns
            assert "status" in columns
            assert "issues_checked" in columns
            assert "issues_failed" in columns
            assert "message" in columns
            assert "created_at_utc" in columns
            assert "evaluated_at_utc" in columns

    def test_gates_table_indexes(self, test_db):
        """Gates table should have appropriate indexes."""
        with _connect(test_db) as conn:
            result = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='gates'"
            ).fetchall()
            index_names = [r[0] for r in result]

            assert "idx_gates_run" in index_names
            assert "idx_gates_type" in index_names
            assert "idx_gates_status" in index_names

    def test_insert_gate(self, test_db):
        """Should be able to insert a gate."""
        gate_id = str(uuid4())
        run_id = str(uuid4())

        with _connect(test_db) as conn:
            _create_test_run(conn, run_id)
            conn.execute(
                """
                INSERT INTO gates (
                    id, run_id, gate_type, status, issues_checked,
                    issues_failed, message, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    gate_id,
                    run_id,
                    "s0_safety",
                    "pass",
                    15,
                    0,
                    "All safety checks passed",
                    "2024-12-22T00:00:00Z",
                ),
            )

            result = conn.execute(
                "SELECT * FROM gates WHERE id = ?", (gate_id,)
            ).fetchone()

            assert result is not None
            assert result[2] == "s0_safety"
            assert result[3] == "pass"
            assert result[4] == 15
            assert result[5] == 0

    def test_query_gates_by_run(self, test_db):
        """Should be able to query all gates for a run."""
        run_id = str(uuid4())

        with _connect(test_db) as conn:
            _create_test_run(conn, run_id)
            # Insert S0, S1, and Final gates
            for gate_type in ["s0_safety", "s1_quality", "final"]:
                conn.execute(
                    """
                    INSERT INTO gates (
                        id, run_id, gate_type, status,
                        issues_checked, issues_failed, created_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        run_id,
                        gate_type,
                        "pending",
                        0,
                        0,
                        "2024-12-22T00:00:00Z",
                    ),
                )

            results = conn.execute(
                "SELECT * FROM gates WHERE run_id = ?", (run_id,)
            ).fetchall()

            assert len(results) == 3
