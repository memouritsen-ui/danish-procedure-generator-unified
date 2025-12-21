"""SQLite-backed job worker for procedure runs."""
from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import uuid
from pathlib import Path
from typing import Any

import anyio

from procedurewriter.db import (
    claim_next_run,
    get_run,
    get_secret,
    list_library_sources,
    mark_stale_runs,
    release_run_lock,
    set_run_needs_ack,
    update_run_heartbeat,
    update_run_status,
)
from procedurewriter.pipeline.evidence import EvidenceGapAcknowledgementRequired
from procedurewriter.pipeline.io import write_json
from procedurewriter.pipeline.run import run_pipeline
from procedurewriter.settings import Settings

logger = logging.getLogger(__name__)

_OPENAI_SECRET_NAME = "openai_api_key"
_ANTHROPIC_SECRET_NAME = "anthropic_api_key"
_NCBI_SECRET_NAME = "ncbi_api_key"
_SERPAPI_SECRET_NAME = "serpapi_api_key"


def _effective_openai_api_key(settings: Settings) -> str | None:
    return get_secret(settings.db_path, name=_OPENAI_SECRET_NAME) or os.getenv("OPENAI_API_KEY")


def _effective_anthropic_api_key(settings: Settings) -> str | None:
    return get_secret(settings.db_path, name=_ANTHROPIC_SECRET_NAME) or os.getenv("ANTHROPIC_API_KEY")


def _effective_ncbi_api_key(settings: Settings) -> str | None:
    return get_secret(settings.db_path, name=_NCBI_SECRET_NAME) or settings.ncbi_api_key


def _effective_serpapi_api_key(settings: Settings) -> str | None:
    return (
        get_secret(settings.db_path, name=_SERPAPI_SECRET_NAME)
        or os.getenv("SERPAPI_API_KEY")
        or os.getenv("PROCEDUREWRITER_SERPAPI_API_KEY")
        or settings.serpapi_api_key
    )


async def _heartbeat_loop(
    *,
    run_id: str,
    worker_id: str,
    settings: Settings,
    stop_event: asyncio.Event,
) -> None:
    while not stop_event.is_set():
        await asyncio.sleep(settings.queue_heartbeat_interval_s)
        update_run_heartbeat(settings.db_path, run_id=run_id, worker_id=worker_id)


async def _run_job(
    *,
    run_id: str,
    worker_id: str,
    settings: Settings,
    semaphore: asyncio.Semaphore,
) -> None:
    async with semaphore:
        stop_hb = asyncio.Event()
        hb_task = asyncio.create_task(
            _heartbeat_loop(run_id=run_id, worker_id=worker_id, settings=settings, stop_event=stop_hb)
        )
        try:
            run = get_run(settings.db_path, run_id)
            if run is None:
                return

            libs = list_library_sources(settings.db_path)
            openai_api_key = _effective_openai_api_key(settings)
            anthropic_api_key = _effective_anthropic_api_key(settings)
            ncbi_api_key = _effective_ncbi_api_key(settings)
            serpapi_api_key = _effective_serpapi_api_key(settings)

            job = lambda: run_pipeline(
                run_id=run_id,
                created_at_utc=run.created_at_utc,
                procedure=run.procedure,
                context=run.context,
                settings=settings,
                library_sources=libs,
                openai_api_key=openai_api_key,
                anthropic_api_key=anthropic_api_key,
                ollama_base_url=settings.ollama_base_url,
                ncbi_api_key=ncbi_api_key,
                serpapi_api_key=serpapi_api_key,
            )
            result = await anyio.to_thread.run_sync(job)
            update_run_status(
                settings.db_path,
                run_id=run_id,
                status="DONE",
                manifest_path=Path(result["manifest_path"]),
                docx_path=Path(result["docx_path"]),
                quality_score=result.get("quality_score"),
                iterations_used=result.get("iterations_used"),
                total_cost_usd=result.get("total_cost_usd"),
                total_input_tokens=result.get("total_input_tokens"),
                total_output_tokens=result.get("total_output_tokens"),
            )
        except EvidenceGapAcknowledgementRequired as e:
            run = get_run(settings.db_path, run_id)
            run_dir = Path(run.run_dir) if run else settings.runs_dir / run_id
            run_dir.mkdir(parents=True, exist_ok=True)
            ack_details = {
                "missing_tiers": e.missing_tiers,
                "availability": e.availability,
            }
            write_json(run_dir / "evidence_gap.json", ack_details)
            set_run_needs_ack(
                settings.db_path,
                run_id=run_id,
                ack_details=ack_details,
                error=str(e),
            )
        except Exception as e:  # noqa: BLE001
            update_run_status(settings.db_path, run_id=run_id, status="FAILED", error=str(e))
        finally:
            release_run_lock(settings.db_path, run_id=run_id)
            stop_hb.set()
            hb_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await hb_task


async def run_worker(
    *,
    settings: Settings,
    stop_event: asyncio.Event | None = None,
    worker_id: str | None = None,
) -> None:
    """Run the SQLite-backed job worker loop."""
    stop_event = stop_event or asyncio.Event()
    worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
    semaphore = asyncio.Semaphore(settings.queue_max_concurrency)
    tasks: set[asyncio.Task[None]] = set()

    logger.info("Worker %s starting (max_concurrency=%s)", worker_id, settings.queue_max_concurrency)
    while not stop_event.is_set():
        # Clean finished tasks
        tasks = {t for t in tasks if not t.done()}

        # Requeue stale RUNNING jobs
        mark_stale_runs(
            settings.db_path,
            stale_after_s=settings.queue_stale_timeout_s,
            max_attempts=settings.queue_max_attempts,
        )

        if len(tasks) >= settings.queue_max_concurrency:
            await asyncio.sleep(settings.queue_poll_interval_s)
            continue

        claimed = claim_next_run(
            settings.db_path,
            worker_id=worker_id,
            max_attempts=settings.queue_max_attempts,
        )
        if claimed is None:
            await asyncio.sleep(settings.queue_poll_interval_s)
            continue

        task = asyncio.create_task(
            _run_job(run_id=claimed.run_id, worker_id=worker_id, settings=settings, semaphore=semaphore)
        )
        tasks.add(task)

    for task in tasks:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
