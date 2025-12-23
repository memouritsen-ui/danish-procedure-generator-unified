# Implementation Plan (Local-First Hardening)

Scope: Replace in-memory background tasks with a SQLite-backed job queue, enforce stable encryption key handling, add cost-capped quality loop, and implement evidence-gap acknowledgements while preserving STRICT evidence policy defaults.

Selected Configuration
- Queue backend: SQLite (no Redis/Postgres dependency)
- Evidence policy: STRICT + allow_with_ack for missing tiers
- Quality loop: auto with cost cap

## Phase 1 — SQLite Job Queue + Worker
- Extend the existing `runs` table with queue fields (attempts, locks, heartbeat, ack metadata)
- Add DB helpers: enqueue, claim_next, heartbeat, mark_stale, complete/fail
- Update `/api/write` to enqueue only (no `asyncio.create_task`)
- Add worker process (`procedurewriter/worker.py`) that:
  - claims jobs
  - runs `run_pipeline`
  - heartbeats during long runs
  - re-queues stale RUNNING jobs or marks FAILED after max attempts
- Add CLI/script to run worker and update `scripts/start` to run API + worker

## Phase 2 — Secret Key Hardening
- Fail fast if `PROCEDUREWRITER_SECRET_KEY` missing
- Add CLI `procedurewriter init-secret` to generate and persist key
- Add CLI `procedurewriter rotate-secret` to re-encrypt stored secrets
- Update tests to require explicit key

## Phase 3 — Quality Loop Cost Cap
- Add settings:
  - `quality_loop_policy = auto`
  - `quality_loop_max_iterations`
  - `quality_loop_max_additional_cost_usd`
- Stop loop if cost cap reached or improvement plateaus
- Emit events when loop stops due to cost cap

## Phase 4 — Evidence Gap Acknowledgement
- Add `allow_with_ack` behavior for missing tiers (strict still default)
- Store evidence gap details in run metadata
- Add API endpoint to acknowledge gaps and resume job
- Update UI/API status flow to show `NEEDS_ACK`

## Phase 5 — Docs + Tests
- Update `ARCHITECTURE.md` to match SQLite queue
- Add targeted tests:
  - queue claim/heartbeat/stale recovery
  - ack flow for evidence gaps
  - quality loop cost cap
  - secret key hard fail

## Definition of Done
- Jobs survive API restarts
- Secrets persist across restarts
- Cost caps prevent runaway loops
- Evidence gaps require explicit user acknowledgement
- Docs and tests aligned with behavior
