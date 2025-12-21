"""Tests for SQLite-backed job queue behavior."""
from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from procedurewriter.db import (
    acknowledge_run,
    claim_next_run,
    create_run,
    get_run,
    init_db,
    mark_stale_runs,
    set_run_needs_ack,
)


def _create_run(db_path: Path, run_id: str, run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    create_run(
        db_path,
        run_id=run_id,
        procedure="Test procedure",
        context=None,
        run_dir=run_dir,
    )


def test_claim_next_run_marks_running(tmp_path: Path) -> None:
    db_path = tmp_path / "runs.sqlite3"
    init_db(db_path)

    run_dir = tmp_path / "runs" / "run-1"
    _create_run(db_path, "run-1", run_dir)

    claimed = claim_next_run(db_path, worker_id="worker-1", max_attempts=3)
    assert claimed is not None
    assert claimed.run_id == "run-1"
    assert claimed.status == "RUNNING"
    assert claimed.locked_by == "worker-1"
    assert claimed.attempts == 1
    assert claimed.locked_at_utc is not None
    assert claimed.heartbeat_at_utc is not None


def test_claim_next_run_skips_needs_ack(tmp_path: Path) -> None:
    db_path = tmp_path / "runs.sqlite3"
    init_db(db_path)

    run_dir = tmp_path / "runs" / "run-ack"
    _create_run(db_path, "run-ack", run_dir)
    set_run_needs_ack(
        db_path,
        run_id="run-ack",
        ack_details={"missing_tiers": ["Cochrane"]},
        error="Missing tiers",
    )

    claimed = claim_next_run(db_path, worker_id="worker-1", max_attempts=3)
    assert claimed is None


def test_mark_stale_runs_requeues(tmp_path: Path) -> None:
    db_path = tmp_path / "runs.sqlite3"
    init_db(db_path)

    run_dir = tmp_path / "runs" / "run-stale"
    _create_run(db_path, "run-stale", run_dir)

    stale_time = (datetime.now(UTC) - timedelta(seconds=120)).isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE runs
            SET status='RUNNING',
                attempts=1,
                locked_at_utc=?,
                heartbeat_at_utc=?
            WHERE run_id=?
            """,
            (stale_time, stale_time, "run-stale"),
        )

    updated = mark_stale_runs(db_path, stale_after_s=60, max_attempts=3)
    assert updated == 1
    run = get_run(db_path, "run-stale")
    assert run is not None
    assert run.status == "QUEUED"


def test_mark_stale_runs_fails_after_max_attempts(tmp_path: Path) -> None:
    db_path = tmp_path / "runs.sqlite3"
    init_db(db_path)

    run_dir = tmp_path / "runs" / "run-fail"
    _create_run(db_path, "run-fail", run_dir)

    stale_time = (datetime.now(UTC) - timedelta(seconds=120)).isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE runs
            SET status='RUNNING',
                attempts=3,
                locked_at_utc=?,
                heartbeat_at_utc=?
            WHERE run_id=?
            """,
            (stale_time, stale_time, "run-fail"),
        )

    updated = mark_stale_runs(db_path, stale_after_s=60, max_attempts=3)
    assert updated == 1
    run = get_run(db_path, "run-fail")
    assert run is not None
    assert run.status == "FAILED"
    assert run.error is not None


def test_acknowledge_run_requeues(tmp_path: Path) -> None:
    db_path = tmp_path / "runs.sqlite3"
    init_db(db_path)

    run_dir = tmp_path / "runs" / "run-ack2"
    _create_run(db_path, "run-ack2", run_dir)
    set_run_needs_ack(
        db_path,
        run_id="run-ack2",
        ack_details={"missing_tiers": ["NICE", "Cochrane"]},
        error="Missing tiers",
    )

    acknowledge_run(db_path, run_id="run-ack2", ack_note="Proceed anyway")
    run = get_run(db_path, "run-ack2")
    assert run is not None
    assert run.status == "QUEUED"
    assert run.ack_required is False
    assert run.ack_note == "Proceed anyway"
