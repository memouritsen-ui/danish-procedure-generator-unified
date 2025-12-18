from __future__ import annotations

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
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


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
              error TEXT,
              run_dir TEXT NOT NULL,
              manifest_path TEXT,
              docx_path TEXT,
              quality_score INTEGER,
              iterations_used INTEGER,
              total_cost_usd REAL,
              total_input_tokens INTEGER,
              total_output_tokens INTEGER
            )
            """
        )
        # Add columns to existing tables (migration for existing DBs)
        for col, col_type in [
            ("quality_score", "INTEGER"),
            ("iterations_used", "INTEGER"),
            ("total_cost_usd", "REAL"),
            ("total_input_tokens", "INTEGER"),
            ("total_output_tokens", "INTEGER"),
        ]:
            try:
                conn.execute(f"ALTER TABLE runs ADD COLUMN {col} {col_type}")
            except sqlite3.OperationalError:
                pass  # Column already exists
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


def set_secret(db_path: Path, *, name: str, value: str) -> None:
    now = utc_now_iso()
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO secrets(name, updated_at_utc, value)
            VALUES(?, ?, ?)
            """,
            (name, now, value),
        )


def get_secret(db_path: Path, *, name: str) -> str | None:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT value FROM secrets WHERE name = ?", (name,)).fetchone()
        if row is None:
            return None
        value = row["value"]
        return str(value) if value is not None else None


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


def create_run(db_path: Path, *, run_id: str, procedure: str, context: str | None, run_dir: Path) -> None:
    now = utc_now_iso()
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO runs(run_id, created_at_utc, updated_at_utc, procedure, context, status, error, run_dir)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, now, now, procedure, context, "QUEUED", None, str(run_dir)),
        )


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
