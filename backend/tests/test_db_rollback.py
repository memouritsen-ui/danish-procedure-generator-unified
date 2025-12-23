"""Tests for claim system database rollback functionality.

TDD: These tests verify that rollback scripts can:
- Drop all claim system tables safely
- Handle non-existent tables gracefully
- Re-apply migrations after rollback

Run: pytest tests/test_db_rollback.py -v
"""

import tempfile
from pathlib import Path

import pytest

from procedurewriter.db import init_db, _connect


@pytest.fixture
def test_db():
    """Create a temporary test database with all tables."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        init_db(db_path)
        yield db_path


def _table_exists(db_path: Path, table_name: str) -> bool:
    """Check if a table exists in the database."""
    with _connect(db_path) as conn:
        result = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        ).fetchone()
        return result is not None


def _create_test_run(conn, run_id: str) -> None:
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


def _get_table_list(db_path: Path) -> list[str]:
    """Get all table names in the database."""
    with _connect(db_path) as conn:
        result = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        return [r[0] for r in result]


class TestClaimSystemRollback:
    """Tests for rolling back claim system tables."""

    def test_rollback_claims_table(self, test_db):
        """Should be able to drop claims table."""
        from procedurewriter.db import rollback_claim_system_table

        assert _table_exists(test_db, "claims")
        rollback_claim_system_table(test_db, "claims")
        assert not _table_exists(test_db, "claims")

    def test_rollback_evidence_chunks_table(self, test_db):
        """Should be able to drop evidence_chunks table."""
        from procedurewriter.db import rollback_claim_system_table

        assert _table_exists(test_db, "evidence_chunks")
        rollback_claim_system_table(test_db, "evidence_chunks")
        assert not _table_exists(test_db, "evidence_chunks")

    def test_rollback_claim_evidence_links_table(self, test_db):
        """Should be able to drop claim_evidence_links table."""
        from procedurewriter.db import rollback_claim_system_table

        assert _table_exists(test_db, "claim_evidence_links")
        rollback_claim_system_table(test_db, "claim_evidence_links")
        assert not _table_exists(test_db, "claim_evidence_links")

    def test_rollback_issues_table(self, test_db):
        """Should be able to drop issues table."""
        from procedurewriter.db import rollback_claim_system_table

        assert _table_exists(test_db, "issues")
        rollback_claim_system_table(test_db, "issues")
        assert not _table_exists(test_db, "issues")

    def test_rollback_gates_table(self, test_db):
        """Should be able to drop gates table."""
        from procedurewriter.db import rollback_claim_system_table

        assert _table_exists(test_db, "gates")
        rollback_claim_system_table(test_db, "gates")
        assert not _table_exists(test_db, "gates")

    def test_rollback_nonexistent_table(self, test_db):
        """Should handle non-existent table gracefully."""
        from procedurewriter.db import rollback_claim_system_table

        # Should not raise
        rollback_claim_system_table(test_db, "nonexistent_table")
        assert not _table_exists(test_db, "nonexistent_table")


class TestFullClaimSystemRollback:
    """Tests for rolling back all claim system tables at once."""

    def test_rollback_all_claim_tables(self, test_db):
        """Should be able to rollback all 5 claim system tables."""
        from procedurewriter.db import rollback_claim_system

        # Verify tables exist before rollback
        claim_tables = ["claims", "evidence_chunks", "claim_evidence_links", "issues", "gates"]
        for table in claim_tables:
            assert _table_exists(test_db, table), f"{table} should exist before rollback"

        # Perform rollback
        rollback_claim_system(test_db)

        # Verify tables no longer exist
        for table in claim_tables:
            assert not _table_exists(test_db, table), f"{table} should not exist after rollback"

    def test_rollback_preserves_other_tables(self, test_db):
        """Rollback should not affect non-claim-system tables."""
        from procedurewriter.db import rollback_claim_system

        # These core tables should survive rollback
        core_tables = ["runs", "library_sources", "secrets", "templates", "protocols"]

        # Verify core tables exist
        for table in core_tables:
            assert _table_exists(test_db, table), f"{table} should exist"

        # Rollback claim system
        rollback_claim_system(test_db)

        # Verify core tables still exist
        for table in core_tables:
            assert _table_exists(test_db, table), f"{table} should still exist after rollback"

    def test_rollback_idempotent(self, test_db):
        """Rolling back twice should not cause errors."""
        from procedurewriter.db import rollback_claim_system

        # First rollback
        rollback_claim_system(test_db)

        # Second rollback should not raise
        rollback_claim_system(test_db)

        # Verify tables still don't exist
        claim_tables = ["claims", "evidence_chunks", "claim_evidence_links", "issues", "gates"]
        for table in claim_tables:
            assert not _table_exists(test_db, table)


class TestMigrationReapply:
    """Tests for re-applying migrations after rollback."""

    def test_can_reapply_after_rollback(self, test_db):
        """Should be able to re-initialize tables after rollback."""
        from procedurewriter.db import rollback_claim_system

        # Rollback
        rollback_claim_system(test_db)

        # Verify tables are gone
        claim_tables = ["claims", "evidence_chunks", "claim_evidence_links", "issues", "gates"]
        for table in claim_tables:
            assert not _table_exists(test_db, table)

        # Re-apply migrations
        init_db(test_db)

        # Verify tables are back
        for table in claim_tables:
            assert _table_exists(test_db, table), f"{table} should exist after re-init"

    def test_indexes_restored_after_reapply(self, test_db):
        """Indexes should be restored after rollback and re-init."""
        from procedurewriter.db import rollback_claim_system

        # Rollback and re-apply
        rollback_claim_system(test_db)
        init_db(test_db)

        # Check indexes exist
        with _connect(test_db) as conn:
            result = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='claims'"
            ).fetchall()
            index_names = [r[0] for r in result]

            assert "idx_claims_run" in index_names
            assert "idx_claims_type" in index_names


class TestRollbackWithData:
    """Tests for rollback behavior when tables contain data."""

    def test_rollback_with_claim_data(self, test_db):
        """Should drop table even when it contains data."""
        from procedurewriter.db import rollback_claim_system
        from uuid import uuid4

        run_id = str(uuid4())
        # Insert test data
        with _connect(test_db) as conn:
            _create_test_run(conn, run_id)
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
                    "Test claim",
                    "[]",
                    1,
                    0.9,
                    "2024-12-22T00:00:00Z",
                ),
            )

        # Verify data exists
        with _connect(test_db) as conn:
            count = conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
            assert count == 1

        # Rollback should succeed
        rollback_claim_system(test_db)

        # Table should be gone
        assert not _table_exists(test_db, "claims")

    def test_rollback_drops_indexes(self, test_db):
        """Rollback should also drop associated indexes."""
        from procedurewriter.db import rollback_claim_system

        # Verify indexes exist
        with _connect(test_db) as conn:
            result = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='claims'"
            ).fetchall()
            assert len(result) > 0

        # Rollback
        rollback_claim_system(test_db)

        # Verify indexes are gone (table doesn't exist)
        with _connect(test_db) as conn:
            result = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='claims'"
            ).fetchall()
            assert len(result) == 0
