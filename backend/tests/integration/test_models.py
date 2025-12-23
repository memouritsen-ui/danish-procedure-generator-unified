"""Integration tests for claim system models end-to-end.

TDD: Tests the complete workflow of:
1. Creating Pydantic models
2. Storing in database
3. Retrieving from database
4. Verifying relationships

Run: pytest tests/integration/test_models.py -v
"""

import json
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

from procedurewriter.db import init_db, _connect
from procedurewriter.models import (
    Claim,
    ClaimType,
    EvidenceChunk,
    ClaimEvidenceLink,
    BindingType,
    Issue,
    IssueCode,
    IssueSeverity,
    Gate,
    GateStatus,
    GateType,
)


@pytest.fixture
def test_db():
    """Create a temporary test database with all tables."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        init_db(db_path)
        yield db_path


def _create_test_run(db_path: Path, run_id: str) -> None:
    """Helper to create a test run record in the database."""
    from datetime import datetime, UTC
    now = datetime.now(UTC).isoformat()
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO runs (
                run_id, created_at_utc, updated_at_utc, procedure, context,
                status, run_dir, procedure_normalized
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, now, now, "Test Procedure", None, "QUEUED", "/tmp/test", "test_procedure"),
        )


@pytest.fixture
def run_id(test_db):
    """Generate a unique run ID and create the corresponding run record."""
    rid = str(uuid4())
    _create_test_run(test_db, rid)
    return rid


class TestClaimWorkflow:
    """End-to-end tests for claim creation and storage."""

    def test_create_claim_model_and_store(self, test_db, run_id):
        """Should create a Claim model and store it in the database."""
        # Create a Pydantic model
        claim = Claim(
            run_id=run_id,
            claim_type=ClaimType.DOSE,
            text="Amoxicillin 50 mg/kg/dag fordelt på 3 doser",
            normalized_value="50",
            unit="mg/kg/dag",
            source_refs=["SRC001", "SRC002"],
            line_number=42,
            confidence=0.95,
        )

        # Store in database using to_db_row() for consistent conversion
        with _connect(test_db) as conn:
            conn.execute(
                """
                INSERT INTO claims (
                    id, run_id, claim_type, text, normalized_value, unit,
                    source_refs_json, line_number, confidence, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                claim.to_db_row(),
            )

        # Retrieve and verify
        with _connect(test_db) as conn:
            row = conn.execute(
                "SELECT * FROM claims WHERE id = ?", (claim.to_db_row()[0],)
            ).fetchone()

            assert row is not None
            assert row["claim_type"] == "dose"
            assert row["normalized_value"] == "50"
            assert row["confidence"] == 0.95
            assert json.loads(row["source_refs_json"]) == ["SRC001", "SRC002"]

    def test_multiple_claims_for_run(self, test_db, run_id):
        """Should support multiple claims per run."""
        claims = [
            Claim(
                run_id=run_id,
                claim_type=ClaimType.DOSE,
                text="Claim 1",
                line_number=1,
                confidence=0.9,
            ),
            Claim(
                run_id=run_id,
                claim_type=ClaimType.THRESHOLD,
                text="Claim 2",
                line_number=2,
                confidence=0.85,
            ),
            Claim(
                run_id=run_id,
                claim_type=ClaimType.RECOMMENDATION,
                text="Claim 3",
                line_number=3,
                confidence=0.8,
            ),
        ]

        # Store all claims using to_db_row() for consistent conversion
        with _connect(test_db) as conn:
            for claim in claims:
                conn.execute(
                    """
                    INSERT INTO claims (
                        id, run_id, claim_type, text, normalized_value, unit,
                        source_refs_json, line_number, confidence, created_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    claim.to_db_row(),
                )

        # Query all claims for run
        with _connect(test_db) as conn:
            rows = conn.execute(
                "SELECT * FROM claims WHERE run_id = ? ORDER BY line_number",
                (run_id,),
            ).fetchall()

            assert len(rows) == 3
            assert rows[0]["claim_type"] == "dose"
            assert rows[1]["claim_type"] == "threshold"
            assert rows[2]["claim_type"] == "recommendation"


class TestEvidenceChunkWorkflow:
    """End-to-end tests for evidence chunk creation and storage."""

    def test_create_evidence_chunk_and_store(self, test_db, run_id):
        """Should create an EvidenceChunk model and store it in the database."""
        chunk = EvidenceChunk(
            run_id=run_id,
            source_id="SRC001",
            text="The recommended dose of amoxicillin is 50 mg/kg/day.",
            chunk_index=0,
            start_char=0,
            end_char=55,
            metadata={"section": "treatment", "language": "en"},
        )

        # Store in database using to_db_row() for consistent conversion
        with _connect(test_db) as conn:
            conn.execute(
                """
                INSERT INTO evidence_chunks (
                    id, run_id, source_id, text, chunk_index,
                    start_char, end_char, embedding_vector_json,
                    metadata_json, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                chunk.to_db_row(),
            )

        # Retrieve and verify
        with _connect(test_db) as conn:
            row = conn.execute(
                "SELECT * FROM evidence_chunks WHERE id = ?", (chunk.to_db_row()[0],)
            ).fetchone()

            assert row is not None
            assert row["source_id"] == "SRC001"
            assert json.loads(row["metadata_json"])["section"] == "treatment"


class TestClaimEvidenceLinkWorkflow:
    """End-to-end tests for linking claims to evidence."""

    def test_create_claim_evidence_link(self, test_db, run_id):
        """Should create a claim-evidence link and store it."""
        # Create claim
        claim = Claim(
            run_id=run_id,
            claim_type=ClaimType.DOSE,
            text="Amoxicillin 50 mg/kg/dag",
            line_number=10,
            confidence=0.9,
        )

        # Create evidence chunk
        chunk = EvidenceChunk(
            run_id=run_id,
            source_id="SRC001",
            text="Recommended dose 50 mg/kg/day",
            chunk_index=0,
        )

        # Create link
        link = ClaimEvidenceLink(
            claim_id=claim.id,
            evidence_chunk_id=chunk.id,
            binding_type=BindingType.SEMANTIC,
            binding_score=0.92,
        )

        # Store all in database using to_db_row() for consistent conversion
        with _connect(test_db) as conn:
            # Store claim
            conn.execute(
                """
                INSERT INTO claims (
                    id, run_id, claim_type, text, normalized_value, unit,
                    source_refs_json, line_number, confidence, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                claim.to_db_row(),
            )

            # Store chunk
            conn.execute(
                """
                INSERT INTO evidence_chunks (
                    id, run_id, source_id, text, chunk_index,
                    start_char, end_char, embedding_vector_json,
                    metadata_json, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                chunk.to_db_row(),
            )

            # Store link
            conn.execute(
                """
                INSERT INTO claim_evidence_links (
                    id, claim_id, evidence_chunk_id, binding_type,
                    binding_score, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                link.to_db_row(),
            )

        # Query link with join
        with _connect(test_db) as conn:
            row = conn.execute(
                """
                SELECT l.*, c.text as claim_text, e.text as evidence_text
                FROM claim_evidence_links l
                JOIN claims c ON l.claim_id = c.id
                JOIN evidence_chunks e ON l.evidence_chunk_id = e.id
                WHERE l.id = ?
                """,
                (link.to_db_row()[0],),
            ).fetchone()

            assert row is not None
            assert row["binding_type"] == "semantic"
            assert row["binding_score"] == 0.92
            assert "Amoxicillin" in row["claim_text"]
            assert "Recommended" in row["evidence_text"]


class TestIssueWorkflow:
    """End-to-end tests for issue tracking."""

    def test_create_issue_and_resolve(self, test_db, run_id):
        """Should create an issue and mark it resolved."""
        issue = Issue(
            run_id=run_id,
            code=IssueCode.DOSE_WITHOUT_EVIDENCE,
            severity=IssueSeverity.S0,
            message="Claim on line 42 has no supporting evidence",
            line_number=42,
        )

        assert issue.severity == IssueSeverity.S0
        assert issue.is_safety_critical

        # Store in database using to_db_row() for consistent conversion
        with _connect(test_db) as conn:
            conn.execute(
                """
                INSERT INTO issues (
                    id, run_id, code, severity, message, line_number,
                    claim_id, source_id, auto_detected, resolved,
                    resolution_note, resolved_at_utc, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                issue.to_db_row(),
            )

        # Mark as resolved
        resolution_note = "Evidence added manually"
        with _connect(test_db) as conn:
            conn.execute(
                """
                UPDATE issues
                SET resolved = 1, resolution_note = ?, resolved_at_utc = ?
                WHERE id = ?
                """,
                (resolution_note, "2024-12-22T12:00:00Z", issue.to_db_row()[0]),
            )

        # Verify resolution
        with _connect(test_db) as conn:
            row = conn.execute(
                "SELECT * FROM issues WHERE id = ?", (issue.to_db_row()[0],)
            ).fetchone()

            assert row["resolved"] == 1
            assert row["resolution_note"] == resolution_note

    def test_query_unresolved_s0_issues(self, test_db, run_id):
        """Should query unresolved S0 issues blocking release."""
        issues = [
            Issue(
                run_id=run_id,
                code=IssueCode.DOSE_WITHOUT_EVIDENCE,
                severity=IssueSeverity.S0,
                message="S0 issue 1",
            ),
            Issue(
                run_id=run_id,
                code=IssueCode.CONFLICTING_DOSES,
                severity=IssueSeverity.S0,
                message="S0 issue 2",
            ),
            Issue(
                run_id=run_id,
                code=IssueCode.CLAIM_BINDING_FAILED,
                severity=IssueSeverity.S1,
                message="S1 issue",
            ),
        ]

        # Store all using to_db_row() for consistent conversion
        with _connect(test_db) as conn:
            for issue in issues:
                conn.execute(
                    """
                    INSERT INTO issues (
                        id, run_id, code, severity, message, line_number,
                        claim_id, source_id, auto_detected, resolved,
                        resolution_note, resolved_at_utc, created_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    issue.to_db_row(),
                )

        # Query S0 unresolved
        with _connect(test_db) as conn:
            rows = conn.execute(
                """
                SELECT * FROM issues
                WHERE run_id = ? AND severity = 's0' AND resolved = 0
                """,
                (run_id,),
            ).fetchall()

            assert len(rows) == 2


class TestGateWorkflow:
    """End-to-end tests for pipeline gates."""

    def test_create_and_evaluate_gate(self, test_db, run_id):
        """Should create a gate and evaluate it."""
        gate = Gate(
            run_id=run_id,
            gate_type=GateType.S0_SAFETY,
            status=GateStatus.PENDING,
        )

        # Store pending gate using to_db_row() for consistent conversion
        with _connect(test_db) as conn:
            conn.execute(
                """
                INSERT INTO gates (
                    id, run_id, gate_type, status, issues_checked,
                    issues_failed, message, created_at_utc, evaluated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                gate.to_db_row(),
            )

        # Evaluate gate (simulate checking 10 issues, 0 failed)
        with _connect(test_db) as conn:
            conn.execute(
                """
                UPDATE gates
                SET status = 'pass', issues_checked = 10, issues_failed = 0,
                    message = 'All safety checks passed',
                    evaluated_at_utc = ?
                WHERE id = ?
                """,
                ("2024-12-22T12:00:00Z", gate.to_db_row()[0]),
            )

        # Verify
        with _connect(test_db) as conn:
            row = conn.execute(
                "SELECT * FROM gates WHERE id = ?", (gate.to_db_row()[0],)
            ).fetchone()

            assert row["status"] == "pass"
            assert row["issues_checked"] == 10
            assert row["issues_failed"] == 0

    def test_failing_gate_blocks_release(self, test_db, run_id):
        """A gate with failures should have FAIL status."""
        gate = Gate(
            run_id=run_id,
            gate_type=GateType.S0_SAFETY,
            status=GateStatus.FAIL,
            issues_checked=10,
            issues_failed=2,
            message="2 S0 issues found - release blocked",
        )

        assert not gate.is_passed
        assert gate.is_safety_gate

        # Store using to_db_row() for consistent conversion
        with _connect(test_db) as conn:
            conn.execute(
                """
                INSERT INTO gates (
                    id, run_id, gate_type, status, issues_checked,
                    issues_failed, message, created_at_utc, evaluated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                gate.to_db_row(),
            )

        # Query failed gates
        with _connect(test_db) as conn:
            rows = conn.execute(
                "SELECT * FROM gates WHERE run_id = ? AND status = 'fail'",
                (run_id,),
            ).fetchall()

            assert len(rows) == 1
            assert rows[0]["issues_failed"] == 2


class TestFullClaimSystemWorkflow:
    """Integration test for complete claim system workflow."""

    def test_full_workflow(self, test_db, run_id):
        """Test the complete claim extraction → binding → eval → gate workflow."""
        # 1. Create evidence chunks
        chunks = [
            EvidenceChunk(
                run_id=run_id,
                source_id="SRC001",
                text="Amoxicillin dosering: 50 mg/kg/dag fordelt på 3 doser",
                chunk_index=0,
            ),
            EvidenceChunk(
                run_id=run_id,
                source_id="SRC002",
                text="Ved pneumoni anbefales 7-10 dages behandling",
                chunk_index=0,
            ),
        ]

        # 2. Create claims from procedure
        claims = [
            Claim(
                run_id=run_id,
                claim_type=ClaimType.DOSE,
                text="Amoxicillin 50 mg/kg/dag",
                line_number=5,
                confidence=0.95,
            ),
            Claim(
                run_id=run_id,
                claim_type=ClaimType.RECOMMENDATION,
                text="Behandlingsvarighed 7-10 dage",
                line_number=8,
                confidence=0.9,
            ),
        ]

        # 3. Create links (claims bound to evidence)
        links = [
            ClaimEvidenceLink(
                claim_id=claims[0].id,
                evidence_chunk_id=chunks[0].id,
                binding_type=BindingType.KEYWORD,
                binding_score=0.88,
            ),
            ClaimEvidenceLink(
                claim_id=claims[1].id,
                evidence_chunk_id=chunks[1].id,
                binding_type=BindingType.SEMANTIC,
                binding_score=0.91,
            ),
        ]

        # 4. No issues (all claims bound with high confidence)
        # 5. Gate passes
        gate = Gate(
            run_id=run_id,
            gate_type=GateType.S0_SAFETY,
            status=GateStatus.PASS,
            issues_checked=2,
            issues_failed=0,
            message="All claims bound to evidence",
        )

        # Store everything using to_db_row() for consistent conversion
        with _connect(test_db) as conn:
            for chunk in chunks:
                conn.execute(
                    """
                    INSERT INTO evidence_chunks (
                        id, run_id, source_id, text, chunk_index,
                        start_char, end_char, embedding_vector_json,
                        metadata_json, created_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    chunk.to_db_row(),
                )

            for claim in claims:
                conn.execute(
                    """
                    INSERT INTO claims (
                        id, run_id, claim_type, text, normalized_value, unit,
                        source_refs_json, line_number, confidence, created_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    claim.to_db_row(),
                )

            for link in links:
                conn.execute(
                    """
                    INSERT INTO claim_evidence_links (
                        id, claim_id, evidence_chunk_id, binding_type,
                        binding_score, created_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    link.to_db_row(),
                )

            conn.execute(
                """
                INSERT INTO gates (
                    id, run_id, gate_type, status, issues_checked,
                    issues_failed, message, created_at_utc, evaluated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                gate.to_db_row(),
            )

        # Verify complete workflow
        with _connect(test_db) as conn:
            # All claims stored
            claim_count = conn.execute(
                "SELECT COUNT(*) FROM claims WHERE run_id = ?", (run_id,)
            ).fetchone()[0]
            assert claim_count == 2

            # All chunks stored
            chunk_count = conn.execute(
                "SELECT COUNT(*) FROM evidence_chunks WHERE run_id = ?", (run_id,)
            ).fetchone()[0]
            assert chunk_count == 2

            # All links stored
            link_count = conn.execute(
                "SELECT COUNT(*) FROM claim_evidence_links"
            ).fetchone()[0]
            assert link_count == 2

            # Gate passed
            gate_row = conn.execute(
                "SELECT * FROM gates WHERE run_id = ? AND gate_type = 's0_safety'",
                (run_id,),
            ).fetchone()
            assert gate_row["status"] == "pass"
            assert gate_row["issues_failed"] == 0

            # Verify binding coverage (all claims have at least one link)
            bound_claims = conn.execute(
                """
                SELECT DISTINCT c.id
                FROM claims c
                JOIN claim_evidence_links l ON c.id = l.claim_id
                WHERE c.run_id = ?
                """,
                (run_id,),
            ).fetchall()
            assert len(bound_claims) == 2  # 100% binding rate
