from __future__ import annotations

import contextlib
import json
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _connect(db_path: Path) -> sqlite3.Connection:
    """Create a database connection with proper configuration.

    CRITICAL: This function enables foreign key enforcement. SQLite disables
    foreign keys by default - they must be enabled per-connection. Without
    this, all FOREIGN KEY constraints in the schema are decorative only.

    Also sets a reasonable timeout for concurrent access scenarios and
    IMMEDIATE isolation level to prevent race conditions by acquiring
    a RESERVED lock at transaction start.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        str(db_path),
        timeout=30.0,
        isolation_level="IMMEDIATE"  # Acquire write lock at BEGIN
    )
    conn.row_factory = sqlite3.Row
    # CRITICAL: Enable foreign key enforcement (disabled by default in SQLite)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


DEFAULT_TEMPLATES = [
    {
        "template_id": "emergency_standard",
        "name": "Emergency Standard",
        "description": "Standard akutmedicinsk procedure format med alle sektioner",
        "is_default": True,
        "is_system": True,
        "config": {
            "title_prefix": "Procedure",
            "sections": [
                {"heading": "Indikationer", "format": "bullets", "bundle": "action"},
                {"heading": "Kontraindikationer", "format": "bullets", "bundle": "action"},
                {"heading": "Forberedelse", "format": "bullets", "bundle": "action"},
                {"heading": "Udstyr", "format": "bullets", "bundle": "action"},
                {"heading": "Fremgangsmåde (trin-for-trin)", "format": "numbered", "bundle": "action"},
                {"heading": "Forklaringslag (baggrund og rationale)", "format": "paragraphs", "bundle": "explanation"},
                {"heading": "Sikkerhedsboks", "format": "bullets", "bundle": "safety"},
                {"heading": "Komplikationer og fejlfinding", "format": "bullets", "bundle": "action"},
                {"heading": "Disposition og opfølgning", "format": "bullets", "bundle": "action"},
                {"heading": "Evidens og begrænsninger", "format": "bullets", "bundle": "explanation"},
            ],
        },
    },
    {
        "template_id": "surgical_procedure",
        "name": "Surgical Procedure",
        "description": "Kirurgisk procedure med præ-, intra- og postoperative faser",
        "is_default": False,
        "is_system": True,
        "config": {
            "title_prefix": "Kirurgisk Procedure",
            "sections": [
                {"heading": "Indikationer", "format": "bullets", "bundle": "action"},
                {"heading": "Kontraindikationer", "format": "bullets", "bundle": "action"},
                {"heading": "Præoperativ forberedelse", "format": "bullets", "bundle": "action"},
                {"heading": "Anæstesi", "format": "bullets", "bundle": "action"},
                {"heading": "Lejring og afvaskning", "format": "bullets", "bundle": "action"},
                {"heading": "Kirurgisk teknik", "format": "numbered", "bundle": "action"},
                {"heading": "Intraoperative observationer", "format": "bullets", "bundle": "safety"},
                {"heading": "Lukning og forbinding", "format": "numbered", "bundle": "action"},
                {"heading": "Postoperativ pleje", "format": "bullets", "bundle": "action"},
                {"heading": "Komplikationer", "format": "bullets", "bundle": "safety"},
            ],
        },
    },
    {
        "template_id": "pediatric_emergency",
        "name": "Pediatric Emergency",
        "description": "Pædiatrisk akut procedure med vægtbaseret dosering",
        "is_default": False,
        "is_system": True,
        "config": {
            "title_prefix": "Pædiatrisk Procedure",
            "sections": [
                {"heading": "Aldersgrupper og definitioner", "format": "bullets", "bundle": "explanation"},
                {"heading": "Indikationer", "format": "bullets", "bundle": "action"},
                {"heading": "Kontraindikationer", "format": "bullets", "bundle": "action"},
                {"heading": "Dosering per vægt", "format": "bullets", "bundle": "action"},
                {"heading": "Forberedelse", "format": "bullets", "bundle": "action"},
                {"heading": "Fremgangsmåde", "format": "numbered", "bundle": "action"},
                {"heading": "Observationer og monitorering", "format": "bullets", "bundle": "action"},
                {"heading": "Sikkerhed og advarsler", "format": "bullets", "bundle": "safety"},
                {"heading": "Forælder-information", "format": "paragraphs", "bundle": "explanation"},
            ],
        },
    },
]


def _seed_default_templates(conn: sqlite3.Connection) -> None:
    """Seed default templates if templates table is empty."""
    cursor = conn.execute("SELECT COUNT(*) FROM templates")
    count = cursor.fetchone()[0]
    if count > 0:
        return  # Already seeded

    now = utc_now_iso()
    for template in DEFAULT_TEMPLATES:
        conn.execute(
            """
            INSERT INTO templates
            (template_id, name, description, created_at_utc, updated_at_utc, is_default, is_system, config_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                template["template_id"],
                template["name"],
                template["description"],
                now,
                now,
                template["is_default"],
                template["is_system"],
                json.dumps(template["config"]),
            ),
        )


def init_db(db_path: Path) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
              run_id TEXT PRIMARY KEY,
              created_at_utc TEXT NOT NULL,
              updated_at_utc TEXT NOT NULL,
              procedure TEXT NOT NULL,
              context TEXT,
              status TEXT NOT NULL,
              attempts INTEGER DEFAULT 0,
              locked_by TEXT,
              locked_at_utc TEXT,
              heartbeat_at_utc TEXT,
              ack_required INTEGER DEFAULT 0,
              ack_details_json TEXT,
              ack_note TEXT,
              acked_at_utc TEXT,
              error TEXT,
              run_dir TEXT NOT NULL,
              manifest_path TEXT,
              docx_path TEXT,
              quality_score INTEGER,
              iterations_used INTEGER,
              total_cost_usd REAL,
              total_input_tokens INTEGER,
              total_output_tokens INTEGER,
              parent_run_id TEXT,
              version_number INTEGER DEFAULT 1,
              version_note TEXT,
              procedure_normalized TEXT
            )
            """
        )
        # Add columns to existing tables (migration for existing DBs)
        for col, col_type in [
            ("attempts", "INTEGER DEFAULT 0"),
            ("locked_by", "TEXT"),
            ("locked_at_utc", "TEXT"),
            ("heartbeat_at_utc", "TEXT"),
            ("ack_required", "INTEGER DEFAULT 0"),
            ("ack_details_json", "TEXT"),
            ("ack_note", "TEXT"),
            ("acked_at_utc", "TEXT"),
            ("quality_score", "INTEGER"),
            ("iterations_used", "INTEGER"),
            ("total_cost_usd", "REAL"),
            ("total_input_tokens", "INTEGER"),
            ("total_output_tokens", "INTEGER"),
            ("parent_run_id", "TEXT"),
            ("version_number", "INTEGER DEFAULT 1"),
            ("version_note", "TEXT"),
            ("procedure_normalized", "TEXT"),
        ]:
            with contextlib.suppress(sqlite3.OperationalError):
                conn.execute(f"ALTER TABLE runs ADD COLUMN {col} {col_type}")

        # Create indexes for version queries
        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_procedure_normalized ON runs(procedure_normalized)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_parent_run_id ON runs(parent_run_id)")
        except sqlite3.OperationalError:
            pass
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS library_sources (
              source_id TEXT PRIMARY KEY,
              created_at_utc TEXT NOT NULL,
              kind TEXT NOT NULL,
              url TEXT,
              title TEXT,
              raw_path TEXT NOT NULL,
              normalized_path TEXT NOT NULL,
              raw_sha256 TEXT NOT NULL,
              normalized_sha256 TEXT NOT NULL,
              meta_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS secrets (
              name TEXT PRIMARY KEY,
              updated_at_utc TEXT NOT NULL,
              value TEXT NOT NULL
            )
            """
        )

        # Templates table for procedure customization
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS templates (
              template_id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              description TEXT,
              created_at_utc TEXT NOT NULL,
              updated_at_utc TEXT NOT NULL,
              is_default BOOLEAN DEFAULT FALSE,
              is_system BOOLEAN DEFAULT FALSE,
              created_by TEXT,
              config_json TEXT NOT NULL
            )
            """
        )

        # Add template_id to runs if not exists
        with contextlib.suppress(sqlite3.OperationalError):
            conn.execute("ALTER TABLE runs ADD COLUMN template_id TEXT")

        # Create template indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_templates_default ON templates(is_default)")

        # Seed default templates if table is empty
        _seed_default_templates(conn)

        # Hospital protocol library for validation
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS protocols (
              protocol_id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              name_normalized TEXT NOT NULL,
              description TEXT,
              created_at_utc TEXT NOT NULL,
              updated_at_utc TEXT NOT NULL,
              status TEXT DEFAULT 'active',
              version TEXT,
              approved_by TEXT,
              approved_at_utc TEXT,
              raw_path TEXT,
              normalized_path TEXT,
              raw_sha256 TEXT,
              normalized_sha256 TEXT,
              meta_json TEXT
            )
            """
        )

        # Protocol indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_protocols_name ON protocols(name_normalized)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_protocols_status ON protocols(status)")

        # Validation results table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS validation_results (
              validation_id TEXT PRIMARY KEY,
              run_id TEXT NOT NULL,
              protocol_id TEXT NOT NULL,
              created_at_utc TEXT NOT NULL,
              similarity_score REAL,
              conflict_count INTEGER,
              result_json TEXT NOT NULL
            )
            """
        )

        # Validation indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_validation_run ON validation_results(run_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_validation_protocol ON validation_results(protocol_id)")

        # Meta-analysis runs table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS meta_analysis_runs (
              run_id TEXT PRIMARY KEY,
              created_at_utc TEXT NOT NULL,
              updated_at_utc TEXT NOT NULL,
              status TEXT NOT NULL,
              error TEXT,
              pico_query_json TEXT NOT NULL,
              outcome_of_interest TEXT NOT NULL,
              study_count INTEGER NOT NULL,
              included_studies INTEGER,
              excluded_studies INTEGER,
              pooled_effect REAL,
              ci_lower REAL,
              ci_upper REAL,
              i_squared REAL,
              tau_squared REAL,
              cochrans_q REAL,
              grade_certainty TEXT,
              docx_path TEXT,
              synthesis_json TEXT
            )
            """
        )

        # Meta-analysis indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_meta_runs_status ON meta_analysis_runs(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_meta_runs_created ON meta_analysis_runs(created_at_utc)")

        # =================================================================
        # CLAIM SYSTEM TABLES (Phase 1 - Auditable Medical Build System)
        # =================================================================

        # Claims table - stores extracted medical claims from procedures
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS claims (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                claim_type TEXT NOT NULL,
                text TEXT NOT NULL,
                normalized_value TEXT,
                unit TEXT,
                source_refs_json TEXT NOT NULL DEFAULT '[]',
                line_number INTEGER NOT NULL,
                confidence REAL NOT NULL,
                created_at_utc TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_claims_run ON claims(run_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_claims_type ON claims(claim_type)")

        # Evidence chunks table - stores chunks of evidence from sources
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS evidence_chunks (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                text TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                start_char INTEGER,
                end_char INTEGER,
                embedding_vector_json TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at_utc TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_run ON evidence_chunks(run_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_source ON evidence_chunks(source_id)")

        # Claim-evidence links table - links claims to supporting evidence
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS claim_evidence_links (
                id TEXT PRIMARY KEY,
                claim_id TEXT NOT NULL,
                evidence_chunk_id TEXT NOT NULL,
                binding_type TEXT NOT NULL,
                binding_score REAL NOT NULL,
                created_at_utc TEXT NOT NULL,
                FOREIGN KEY (claim_id) REFERENCES claims(id),
                FOREIGN KEY (evidence_chunk_id) REFERENCES evidence_chunks(id)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_links_claim ON claim_evidence_links(claim_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_links_chunk ON claim_evidence_links(evidence_chunk_id)")

        # Issues table - stores detected issues during evaluation
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS issues (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                code TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                line_number INTEGER,
                claim_id TEXT,
                source_id TEXT,
                auto_detected INTEGER NOT NULL DEFAULT 1,
                resolved INTEGER NOT NULL DEFAULT 0,
                resolution_note TEXT,
                resolved_at_utc TEXT,
                created_at_utc TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES runs(run_id),
                FOREIGN KEY (claim_id) REFERENCES claims(id)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_issues_run ON issues(run_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_issues_severity ON issues(severity)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_issues_resolved ON issues(resolved)")

        # Gates table - stores pipeline gate evaluation results
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS gates (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                gate_type TEXT NOT NULL,
                status TEXT NOT NULL,
                issues_checked INTEGER NOT NULL DEFAULT 0,
                issues_failed INTEGER NOT NULL DEFAULT 0,
                message TEXT,
                created_at_utc TEXT NOT NULL,
                evaluated_at_utc TEXT,
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_gates_run ON gates(run_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_gates_type ON gates(gate_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_gates_status ON gates(status)")

        # =================================================================
        # END CLAIM SYSTEM TABLES
        # =================================================================

        # Style profiles table for LLM-powered document formatting
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS style_profiles (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                is_default BOOLEAN DEFAULT FALSE,
                created_at_utc TEXT NOT NULL,
                updated_at_utc TEXT NOT NULL,
                tone_config TEXT NOT NULL,
                structure_config TEXT NOT NULL,
                formatting_config TEXT NOT NULL,
                visual_config TEXT NOT NULL,
                original_prompt TEXT
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_style_profiles_default ON style_profiles(is_default)")


def set_secret(db_path: Path, *, name: str, value: str) -> None:
    """Store a secret value encrypted in the database."""
    from procedurewriter.crypto import encrypt_value, is_encrypted
    now = utc_now_iso()
    # Only encrypt if not already encrypted
    encrypted_value = encrypt_value(value) if not is_encrypted(value) else value
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO secrets(name, updated_at_utc, value)
            VALUES(?, ?, ?)
            """,
            (name, now, encrypted_value),
        )


def get_secret(db_path: Path, *, name: str) -> str | None:
    """Retrieve and decrypt a secret value from the database."""
    from procedurewriter.crypto import decrypt_value, is_encrypted
    with _connect(db_path) as conn:
        row = conn.execute("SELECT value FROM secrets WHERE name = ?", (name,)).fetchone()
        if row is None:
            return None
        value = row["value"]
        if value is None:
            return None
        # Decrypt if encrypted, otherwise return as-is (for backwards compatibility)
        if is_encrypted(str(value)):
            return decrypt_value(str(value))
        return str(value)


def delete_secret(db_path: Path, *, name: str) -> None:
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM secrets WHERE name = ?", (name,))


def mask_secret(value: str) -> str:
    if len(value) <= 8:
        return "***"
    return f"{value[:3]}…{value[-4:]}"


@dataclass(frozen=True)
class RunRow:
    run_id: str
    created_at_utc: str
    updated_at_utc: str
    procedure: str
    context: str | None
    status: str
    error: str | None
    run_dir: str
    manifest_path: str | None
    docx_path: str | None
    quality_score: int | None
    iterations_used: int | None
    total_cost_usd: float | None
    total_input_tokens: int | None
    total_output_tokens: int | None
    # Queue + acknowledgement fields
    attempts: int = 0
    locked_by: str | None = None
    locked_at_utc: str | None = None
    heartbeat_at_utc: str | None = None
    ack_required: bool = False
    ack_details: dict[str, Any] | None = None
    ack_note: str | None = None
    acked_at_utc: str | None = None
    # Versioning fields
    parent_run_id: str | None = None
    version_number: int = 1
    version_note: str | None = None
    procedure_normalized: str | None = None
    # Template field
    template_id: str | None = None


def normalize_procedure_name(name: str) -> str:
    """Normalize procedure name for matching versions across runs.

    Lowercases, strips, and removes punctuation/special chars.
    """
    import re
    normalized = name.lower().strip()
    # Remove punctuation and special chars, keep only alphanumeric and spaces
    normalized = re.sub(r"[^\w\s]", "", normalized)
    # Collapse whitespace
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def create_run(
    db_path: Path,
    *,
    run_id: str,
    procedure: str,
    context: str | None,
    run_dir: Path,
    parent_run_id: str | None = None,
    version_note: str | None = None,
    template_id: str | None = None,
) -> None:
    """Create a new run record with proper version numbering.

    CRITICAL: Version number calculation and insertion are done in a single
    atomic transaction using BEGIN IMMEDIATE to prevent race conditions.
    Without this, concurrent create_run calls could get duplicate version
    numbers (classic TOCTOU vulnerability).

    The BEGIN IMMEDIATE acquires a RESERVED lock immediately, preventing
    other writers from modifying the table until we COMMIT.
    """
    now = utc_now_iso()
    procedure_normalized = normalize_procedure_name(procedure)

    with _connect(db_path) as conn:
        # BEGIN IMMEDIATE acquires write lock before any reads
        # This prevents race condition between SELECT and INSERT
        conn.execute("BEGIN IMMEDIATE")
        try:
            # Calculate version number within the same transaction
            version_number = 1
            if parent_run_id:
                # Get parent's version and increment
                row = conn.execute(
                    "SELECT version_number FROM runs WHERE run_id = ?",
                    (parent_run_id,),
                ).fetchone()
                if row and row["version_number"]:
                    version_number = row["version_number"] + 1
            else:
                # Check for existing versions with same normalized procedure name
                # CRITICAL: We use ALL runs (not just DONE) to ensure uniqueness
                # This prevents duplicate version numbers when multiple runs are
                # created concurrently. Each run gets a unique version number
                # regardless of status.
                row = conn.execute(
                    """
                    SELECT COALESCE(MAX(version_number), 0) + 1 as next_version
                    FROM runs
                    WHERE procedure_normalized = ?
                    """,
                    (procedure_normalized,),
                ).fetchone()
                version_number = row["next_version"]

            # Insert within the same transaction - no race window
            conn.execute(
                """
                INSERT INTO runs(
                    run_id, created_at_utc, updated_at_utc, procedure, context,
                    status, error, run_dir, parent_run_id, version_number,
                    version_note, procedure_normalized, template_id
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id, now, now, procedure, context, "QUEUED", None,
                    str(run_dir), parent_run_id, version_number, version_note,
                    procedure_normalized, template_id,
                ),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise


def update_run_status(
    db_path: Path,
    *,
    run_id: str,
    status: str,
    error: str | None = None,
    manifest_path: Path | None = None,
    docx_path: Path | None = None,
    quality_score: int | None = None,
    iterations_used: int | None = None,
    total_cost_usd: float | None = None,
    total_input_tokens: int | None = None,
    total_output_tokens: int | None = None,
) -> None:
    now = utc_now_iso()
    with _connect(db_path) as conn:
        conn.execute(
            """
            UPDATE runs
            SET updated_at_utc = ?,
                status = ?,
                error = ?,
                manifest_path = COALESCE(?, manifest_path),
                docx_path = COALESCE(?, docx_path),
                quality_score = COALESCE(?, quality_score),
                iterations_used = COALESCE(?, iterations_used),
                total_cost_usd = COALESCE(?, total_cost_usd),
                total_input_tokens = COALESCE(?, total_input_tokens),
                total_output_tokens = COALESCE(?, total_output_tokens)
            WHERE run_id = ?
            """,
            (
                now,
                status,
                error,
                str(manifest_path) if manifest_path else None,
                str(docx_path) if docx_path else None,
                quality_score,
                iterations_used,
                total_cost_usd,
                total_input_tokens,
                total_output_tokens,
                run_id,
            ),
        )


def _row_to_run(row: sqlite3.Row) -> RunRow:
    # Handle both old DBs (without versioning columns) and new DBs
    keys = row.keys()
    ack_details: dict[str, Any] | None = None
    if "ack_details_json" in keys and row["ack_details_json"]:
        with contextlib.suppress(json.JSONDecodeError, TypeError):
            ack_details = json.loads(row["ack_details_json"])
    return RunRow(
        run_id=row["run_id"],
        created_at_utc=row["created_at_utc"],
        updated_at_utc=row["updated_at_utc"],
        procedure=row["procedure"],
        context=row["context"],
        status=row["status"],
        error=row["error"],
        run_dir=row["run_dir"],
        manifest_path=row["manifest_path"],
        docx_path=row["docx_path"],
        quality_score=row["quality_score"],
        iterations_used=row["iterations_used"],
        total_cost_usd=row["total_cost_usd"],
        total_input_tokens=row["total_input_tokens"],
        total_output_tokens=row["total_output_tokens"],
        attempts=row["attempts"] if "attempts" in keys and row["attempts"] is not None else 0,
        locked_by=row["locked_by"] if "locked_by" in keys else None,
        locked_at_utc=row["locked_at_utc"] if "locked_at_utc" in keys else None,
        heartbeat_at_utc=row["heartbeat_at_utc"] if "heartbeat_at_utc" in keys else None,
        ack_required=bool(row["ack_required"]) if "ack_required" in keys and row["ack_required"] is not None else False,
        ack_details=ack_details,
        ack_note=row["ack_note"] if "ack_note" in keys else None,
        acked_at_utc=row["acked_at_utc"] if "acked_at_utc" in keys else None,
        parent_run_id=row["parent_run_id"] if "parent_run_id" in keys else None,
        version_number=row["version_number"] if "version_number" in keys and row["version_number"] else 1,
        version_note=row["version_note"] if "version_note" in keys else None,
        procedure_normalized=row["procedure_normalized"] if "procedure_normalized" in keys else None,
        template_id=row["template_id"] if "template_id" in keys else None,
    )


def get_run(db_path: Path, run_id: str) -> RunRow | None:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        return _row_to_run(row) if row else None


def list_runs(db_path: Path, limit: int = 200) -> list[RunRow]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM runs ORDER BY created_at_utc DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [_row_to_run(r) for r in rows]


def enqueue_run(db_path: Path, *, run_id: str) -> None:
    """Re-queue a run for processing."""
    now = utc_now_iso()
    with _connect(db_path) as conn:
        conn.execute(
            """
            UPDATE runs
            SET updated_at_utc = ?,
                status = 'QUEUED',
                error = NULL,
                ack_required = 0,
                ack_note = NULL,
                acked_at_utc = NULL
            WHERE run_id = ?
            """,
            (now, run_id),
        )


def claim_next_run(
    db_path: Path,
    *,
    worker_id: str,
    max_attempts: int = 3,
) -> RunRow | None:
    """Claim the next queued run for processing.

    CRITICAL: This uses BEGIN IMMEDIATE for atomic read-modify-write, plus
    a defense-in-depth check in the UPDATE WHERE clause to ensure the row
    is still QUEUED. If another worker somehow claimed it, rows_affected=0
    and we retry with the next QUEUED run.

    Marks the run as RUNNING and sets lock/heartbeat metadata.
    """
    now = utc_now_iso()
    with _connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            # Keep trying until we successfully claim a run or none are available
            while True:
                row = conn.execute(
                    """
                    SELECT * FROM runs
                    WHERE status = 'QUEUED'
                      AND (attempts < ? OR attempts IS NULL)
                    ORDER BY created_at_utc ASC
                    LIMIT 1
                    """,
                    (max_attempts,),
                ).fetchone()
                if row is None:
                    conn.execute("COMMIT")
                    return None

                run_id = row["run_id"]
                attempts = (row["attempts"] or 0) + 1

                # CRITICAL: Include status check in WHERE clause for defense-in-depth.
                # Even though BEGIN IMMEDIATE should prevent concurrent claims,
                # this guards against edge cases and provides audit clarity.
                cursor = conn.execute(
                    """
                    UPDATE runs
                    SET updated_at_utc = ?,
                        status = 'RUNNING',
                        attempts = ?,
                        locked_by = ?,
                        locked_at_utc = ?,
                        heartbeat_at_utc = ?
                    WHERE run_id = ?
                      AND status = 'QUEUED'
                    """,
                    (now, attempts, worker_id, now, now, run_id),
                )

                if cursor.rowcount == 1:
                    # Successfully claimed
                    conn.execute("COMMIT")
                    return get_run(db_path, run_id)
                # Row was claimed by someone else (shouldn't happen with BEGIN IMMEDIATE,
                # but defense-in-depth). Loop to try next queued run.
        except Exception:
            conn.execute("ROLLBACK")
            raise


def update_run_heartbeat(db_path: Path, *, run_id: str, worker_id: str) -> None:
    """Update heartbeat for a running job if the worker holds the lock."""
    now = utc_now_iso()
    with _connect(db_path) as conn:
        conn.execute(
            """
            UPDATE runs
            SET updated_at_utc = ?,
                heartbeat_at_utc = ?
            WHERE run_id = ? AND locked_by = ?
            """,
            (now, now, run_id, worker_id),
        )


def release_run_lock(db_path: Path, *, run_id: str) -> None:
    """Clear lock/heartbeat metadata for a run."""
    now = utc_now_iso()
    with _connect(db_path) as conn:
        conn.execute(
            """
            UPDATE runs
            SET updated_at_utc = ?,
                locked_by = NULL,
                locked_at_utc = NULL,
                heartbeat_at_utc = NULL
            WHERE run_id = ?
            """,
            (now, run_id),
        )


def mark_stale_runs(
    db_path: Path,
    *,
    stale_after_s: int,
    max_attempts: int = 3,
) -> int:
    """Mark stale RUNNING runs as QUEUED (or FAILED if max attempts reached).

    CRITICAL: This uses an atomic approach to avoid TOCTOU vulnerability.
    Instead of SELECT-then-UPDATE (where heartbeat could change between),
    we perform the entire staleness check and update in SQL within an
    IMMEDIATE transaction.

    The UPDATE includes a heartbeat check in its WHERE clause to ensure
    we only mark runs that are STILL stale at update time.
    """
    now_iso = utc_now_iso()
    now_ts = datetime.now(UTC).isoformat()
    updated = 0

    with _connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            # First: Mark runs as FAILED if they're stale AND max attempts reached
            # The heartbeat staleness check is done IN SQL to avoid TOCTOU
            cursor = conn.execute(
                """
                UPDATE runs
                SET updated_at_utc = ?,
                    status = 'FAILED',
                    error = 'Run marked failed due to stale worker lock.',
                    locked_by = NULL,
                    locked_at_utc = NULL,
                    heartbeat_at_utc = NULL
                WHERE status = 'RUNNING'
                  AND attempts >= ?
                  AND (
                      (heartbeat_at_utc IS NOT NULL
                       AND (julianday(?) - julianday(heartbeat_at_utc)) * 86400 >= ?)
                      OR
                      (heartbeat_at_utc IS NULL AND locked_at_utc IS NOT NULL
                       AND (julianday(?) - julianday(locked_at_utc)) * 86400 >= ?)
                  )
                """,
                (now_iso, max_attempts, now_ts, stale_after_s, now_ts, stale_after_s),
            )
            updated += cursor.rowcount

            # Second: Mark remaining stale runs as QUEUED (under max attempts)
            cursor = conn.execute(
                """
                UPDATE runs
                SET updated_at_utc = ?,
                    status = 'QUEUED',
                    error = NULL,
                    locked_by = NULL,
                    locked_at_utc = NULL,
                    heartbeat_at_utc = NULL
                WHERE status = 'RUNNING'
                  AND (attempts < ? OR attempts IS NULL)
                  AND (
                      (heartbeat_at_utc IS NOT NULL
                       AND (julianday(?) - julianday(heartbeat_at_utc)) * 86400 >= ?)
                      OR
                      (heartbeat_at_utc IS NULL AND locked_at_utc IS NOT NULL
                       AND (julianday(?) - julianday(locked_at_utc)) * 86400 >= ?)
                  )
                """,
                (now_iso, max_attempts, now_ts, stale_after_s, now_ts, stale_after_s),
            )
            updated += cursor.rowcount

            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    return updated


def set_run_needs_ack(
    db_path: Path,
    *,
    run_id: str,
    ack_details: dict[str, Any],
    error: str | None = None,
) -> None:
    """Mark a run as needing acknowledgement before proceeding."""
    now = utc_now_iso()
    with _connect(db_path) as conn:
        conn.execute(
            """
            UPDATE runs
            SET updated_at_utc = ?,
                status = 'NEEDS_ACK',
                error = ?,
                ack_required = 1,
                ack_details_json = ?,
                locked_by = NULL,
                locked_at_utc = NULL,
                heartbeat_at_utc = NULL
            WHERE run_id = ?
            """,
            (now, error, json.dumps(ack_details), run_id),
        )


def acknowledge_run(
    db_path: Path,
    *,
    run_id: str,
    ack_note: str | None = None,
) -> None:
    """Acknowledge evidence gaps and re-queue the run."""
    now = utc_now_iso()
    with _connect(db_path) as conn:
        conn.execute(
            """
            UPDATE runs
            SET updated_at_utc = ?,
                status = 'QUEUED',
                ack_required = 0,
                ack_note = ?,
                acked_at_utc = ?
            WHERE run_id = ?
            """,
            (now, ack_note, now, run_id),
        )


def add_library_source(
    db_path: Path,
    *,
    source_id: str,
    kind: str,
    url: str | None,
    title: str | None,
    raw_path: Path,
    normalized_path: Path,
    raw_sha256: str,
    normalized_sha256: str,
    meta: dict[str, Any],
) -> None:
    now = utc_now_iso()
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO library_sources(
              source_id, created_at_utc, kind, url, title, raw_path, normalized_path,
              raw_sha256, normalized_sha256, meta_json
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                now,
                kind,
                url,
                title,
                str(raw_path),
                str(normalized_path),
                raw_sha256,
                normalized_sha256,
                json.dumps(meta, ensure_ascii=False),
            ),
        )


@dataclass(frozen=True)
class LibrarySourceRow:
    source_id: str
    created_at_utc: str
    kind: str
    url: str | None
    title: str | None
    raw_path: str
    normalized_path: str
    raw_sha256: str
    normalized_sha256: str
    meta: dict[str, Any]


def list_library_sources(db_path: Path) -> list[LibrarySourceRow]:
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM library_sources ORDER BY created_at_utc DESC").fetchall()
    out: list[LibrarySourceRow] = []
    for r in rows:
        out.append(
            LibrarySourceRow(
                source_id=r["source_id"],
                created_at_utc=r["created_at_utc"],
                kind=r["kind"],
                url=r["url"],
                title=r["title"],
                raw_path=r["raw_path"],
                normalized_path=r["normalized_path"],
                raw_sha256=r["raw_sha256"],
                normalized_sha256=r["normalized_sha256"],
                meta=json.loads(r["meta_json"]),
            )
        )
    return out


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


# --- Versioning query functions ---


def list_procedure_versions(db_path: Path, procedure: str) -> list[RunRow]:
    """List all versions of a procedure, ordered by version number descending."""
    procedure_normalized = normalize_procedure_name(procedure)
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM runs
            WHERE procedure_normalized = ? AND status = 'DONE'
            ORDER BY version_number DESC
            """,
            (procedure_normalized,),
        ).fetchall()
    return [_row_to_run(r) for r in rows]


def get_latest_version(db_path: Path, procedure: str) -> RunRow | None:
    """Get the latest version of a procedure."""
    procedure_normalized = normalize_procedure_name(procedure)
    with _connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT * FROM runs
            WHERE procedure_normalized = ? AND status = 'DONE'
            ORDER BY version_number DESC
            LIMIT 1
            """,
            (procedure_normalized,),
        ).fetchone()
    return _row_to_run(row) if row else None


def list_unique_procedures(db_path: Path) -> list[str]:
    """List all unique procedure names that have completed runs."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT procedure FROM runs
            WHERE status = 'DONE'
            ORDER BY procedure
            """
        ).fetchall()
    return [str(r["procedure"]) for r in rows]


def get_version_chain(db_path: Path, run_id: str) -> list[RunRow]:
    """Get the complete version chain for a run (ancestors + self).

    Returns list ordered from oldest ancestor to the given run.
    """
    chain: list[RunRow] = []
    current_id: str | None = run_id

    while current_id:
        run = get_run(db_path, current_id)
        if not run:
            break
        chain.append(run)
        current_id = run.parent_run_id

    # Reverse to get oldest first
    return list(reversed(chain))


# --- Meta-analysis run functions ---


@dataclass(frozen=True)
class MetaAnalysisRunRow:
    """Row data for meta-analysis run."""

    run_id: str
    created_at_utc: str
    updated_at_utc: str
    status: str
    error: str | None
    pico_query: dict[str, Any]
    outcome_of_interest: str
    study_count: int
    included_studies: int | None
    excluded_studies: int | None
    pooled_effect: float | None
    ci_lower: float | None
    ci_upper: float | None
    i_squared: float | None
    tau_squared: float | None
    cochrans_q: float | None
    grade_certainty: str | None
    docx_path: str | None
    synthesis: dict[str, Any] | None


def create_meta_analysis_run(
    db_path: Path,
    *,
    run_id: str,
    pico_query: dict[str, Any],
    outcome_of_interest: str,
    study_count: int,
) -> None:
    """Create a new meta-analysis run record."""
    now = utc_now_iso()
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO meta_analysis_runs(
                run_id, created_at_utc, updated_at_utc, status,
                pico_query_json, outcome_of_interest, study_count
            )
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                now,
                now,
                "QUEUED",
                json.dumps(pico_query, ensure_ascii=False),
                outcome_of_interest,
                study_count,
            ),
        )


def update_meta_analysis_results(
    db_path: Path,
    *,
    run_id: str,
    pooled_effect: float | None = None,
    ci_lower: float | None = None,
    ci_upper: float | None = None,
    i_squared: float | None = None,
    tau_squared: float | None = None,
    cochrans_q: float | None = None,
    included_studies: int | None = None,
    excluded_studies: int | None = None,
    grade_certainty: str | None = None,
    status: str | None = None,
    error: str | None = None,
    docx_path: str | None = None,
    synthesis: dict[str, Any] | None = None,
) -> None:
    """Update meta-analysis run with results."""
    now = utc_now_iso()
    with _connect(db_path) as conn:
        conn.execute(
            """
            UPDATE meta_analysis_runs
            SET updated_at_utc = ?,
                status = COALESCE(?, status),
                error = COALESCE(?, error),
                pooled_effect = COALESCE(?, pooled_effect),
                ci_lower = COALESCE(?, ci_lower),
                ci_upper = COALESCE(?, ci_upper),
                i_squared = COALESCE(?, i_squared),
                tau_squared = COALESCE(?, tau_squared),
                cochrans_q = COALESCE(?, cochrans_q),
                included_studies = COALESCE(?, included_studies),
                excluded_studies = COALESCE(?, excluded_studies),
                grade_certainty = COALESCE(?, grade_certainty),
                docx_path = COALESCE(?, docx_path),
                synthesis_json = COALESCE(?, synthesis_json)
            WHERE run_id = ?
            """,
            (
                now,
                status,
                error,
                pooled_effect,
                ci_lower,
                ci_upper,
                i_squared,
                tau_squared,
                cochrans_q,
                included_studies,
                excluded_studies,
                grade_certainty,
                docx_path,
                json.dumps(synthesis, ensure_ascii=False) if synthesis else None,
                run_id,
            ),
        )


def _row_to_meta_run(row: sqlite3.Row) -> MetaAnalysisRunRow:
    """Convert database row to MetaAnalysisRunRow."""
    return MetaAnalysisRunRow(
        run_id=row["run_id"],
        created_at_utc=row["created_at_utc"],
        updated_at_utc=row["updated_at_utc"],
        status=row["status"],
        error=row["error"],
        pico_query=json.loads(row["pico_query_json"]),
        outcome_of_interest=row["outcome_of_interest"],
        study_count=row["study_count"],
        included_studies=row["included_studies"],
        excluded_studies=row["excluded_studies"],
        pooled_effect=row["pooled_effect"],
        ci_lower=row["ci_lower"],
        ci_upper=row["ci_upper"],
        i_squared=row["i_squared"],
        tau_squared=row["tau_squared"],
        cochrans_q=row["cochrans_q"],
        grade_certainty=row["grade_certainty"],
        docx_path=row["docx_path"],
        synthesis=json.loads(row["synthesis_json"]) if row["synthesis_json"] else None,
    )


def get_meta_analysis_run(db_path: Path, run_id: str) -> MetaAnalysisRunRow | None:
    """Get meta-analysis run by ID."""
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM meta_analysis_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        return _row_to_meta_run(row) if row else None


def list_meta_analysis_runs(db_path: Path, limit: int = 100) -> list[MetaAnalysisRunRow]:
    """List recent meta-analysis runs."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM meta_analysis_runs ORDER BY created_at_utc DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [_row_to_meta_run(r) for r in rows]


# =============================================================================
# Style Profile Functions
# =============================================================================


def create_style_profile(
    db_path: Path,
    *,
    name: str,
    tone_config: dict[str, Any],
    structure_config: dict[str, Any],
    formatting_config: dict[str, Any],
    visual_config: dict[str, Any],
    description: str | None = None,
    original_prompt: str | None = None,
) -> str:
    """Create a new style profile."""
    import uuid
    profile_id = str(uuid.uuid4())
    now = utc_now_iso()

    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO style_profiles
            (id, name, description, is_default, created_at_utc, updated_at_utc,
             tone_config, structure_config, formatting_config, visual_config, original_prompt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile_id,
                name,
                description,
                False,
                now,
                now,
                json.dumps(tone_config),
                json.dumps(structure_config),
                json.dumps(formatting_config),
                json.dumps(visual_config),
                original_prompt,
            ),
        )
        conn.commit()
    return profile_id


def get_style_profile(db_path: Path, profile_id: str) -> dict[str, Any] | None:
    """Get a style profile by ID."""
    with _connect(db_path) as conn:
        cursor = conn.execute(
            "SELECT * FROM style_profiles WHERE id = ?",
            (profile_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return _row_to_style_profile(row)


def _row_to_style_profile(row: sqlite3.Row) -> dict[str, Any]:
    """Convert a database row to a style profile dict."""
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "is_default": bool(row["is_default"]),
        "created_at_utc": row["created_at_utc"],
        "updated_at_utc": row["updated_at_utc"],
        "tone_config": json.loads(row["tone_config"]),
        "structure_config": json.loads(row["structure_config"]),
        "formatting_config": json.loads(row["formatting_config"]),
        "visual_config": json.loads(row["visual_config"]),
        "original_prompt": row["original_prompt"],
    }


def list_style_profiles(db_path: Path) -> list[dict[str, Any]]:
    """List all style profiles."""
    with _connect(db_path) as conn:
        cursor = conn.execute(
            "SELECT * FROM style_profiles ORDER BY name"
        )
        return [_row_to_style_profile(row) for row in cursor.fetchall()]


def update_style_profile(
    db_path: Path,
    profile_id: str,
    **updates: Any,
) -> bool:
    """Update a style profile. Returns True if updated."""
    allowed_fields = {
        "name", "description", "tone_config", "structure_config",
        "formatting_config", "visual_config", "original_prompt"
    }
    updates = {k: v for k, v in updates.items() if k in allowed_fields}
    if not updates:
        return False

    # JSON-encode dict fields
    for key in ["tone_config", "structure_config", "formatting_config", "visual_config"]:
        if key in updates and isinstance(updates[key], dict):
            updates[key] = json.dumps(updates[key])

    updates["updated_at_utc"] = utc_now_iso()

    set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
    values = list(updates.values()) + [profile_id]

    with _connect(db_path) as conn:
        cursor = conn.execute(
            f"UPDATE style_profiles SET {set_clause} WHERE id = ?",
            values,
        )
        conn.commit()
        return cursor.rowcount > 0


def delete_style_profile(db_path: Path, profile_id: str) -> bool:
    """Delete a style profile. Returns True if deleted."""
    with _connect(db_path) as conn:
        cursor = conn.execute(
            "DELETE FROM style_profiles WHERE id = ?",
            (profile_id,),
        )
        conn.commit()
        return cursor.rowcount > 0


def get_default_style_profile(db_path: Path) -> dict[str, Any] | None:
    """Get the default style profile."""
    with _connect(db_path) as conn:
        cursor = conn.execute(
            "SELECT * FROM style_profiles WHERE is_default = 1 LIMIT 1"
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return _row_to_style_profile(row)


def set_default_style_profile(db_path: Path, profile_id: str) -> None:
    """Set a profile as the default (unsets any existing default)."""
    with _connect(db_path) as conn:
        conn.execute("UPDATE style_profiles SET is_default = 0")
        conn.execute(
            "UPDATE style_profiles SET is_default = 1 WHERE id = ?",
            (profile_id,),
        )
        conn.commit()


# =============================================================================
# Claim System Rollback Functions (Phase 1 - Migration Safety)
# =============================================================================

# Tables that belong to the claim system
CLAIM_SYSTEM_TABLES = [
    "claim_evidence_links",  # Must be dropped first (FK to claims and evidence_chunks)
    "issues",  # FK to claims
    "gates",
    "claims",
    "evidence_chunks",
]


def rollback_claim_system_table(db_path: Path, table_name: str) -> None:
    """Drop a single claim system table if it exists.

    Args:
        db_path: Path to the SQLite database
        table_name: Name of the table to drop
    """
    with _connect(db_path) as conn:
        conn.execute(f"DROP TABLE IF EXISTS {table_name}")
        conn.commit()


def rollback_claim_system(db_path: Path) -> None:
    """Rollback all claim system tables.

    Drops tables in correct order to respect foreign key constraints.
    Safe to call multiple times (idempotent).

    Tables dropped:
    - claim_evidence_links
    - issues
    - gates
    - claims
    - evidence_chunks
    """
    with _connect(db_path) as conn:
        for table_name in CLAIM_SYSTEM_TABLES:
            conn.execute(f"DROP TABLE IF EXISTS {table_name}")
        conn.commit()
