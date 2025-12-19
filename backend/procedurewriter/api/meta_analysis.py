"""FastAPI endpoints for meta-analysis pipeline.

Provides endpoints for:
- POST /api/meta-analysis: Start new meta-analysis
- GET /api/meta-analysis/{run_id}/stream: SSE stream for live monitoring

Rectification: Handles ERROR and COMPLETE events with emitter cleanup.
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from procedurewriter.pipeline.events import EventEmitter, EventType

router = APIRouter(prefix="/api", tags=["meta-analysis"])

# In-memory store for active event emitters (production would use Redis)
_active_emitters: dict[str, EventEmitter] = {}

# Timestamp tracking for stale emitter cleanup (prevents memory leaks)
_emitter_timestamps: dict[str, float] = {}

# Cleanup timeout in seconds (30 minutes)
EMITTER_CLEANUP_TIMEOUT = 30 * 60


def cleanup_stale_emitters() -> int:
    """Remove emitters inactive for >30 minutes.

    Called periodically by background task to prevent memory leaks.

    Returns:
        Number of emitters removed.
    """
    current_time = time.time()
    stale_run_ids = [
        run_id
        for run_id, created_at in _emitter_timestamps.items()
        if current_time - created_at > EMITTER_CLEANUP_TIMEOUT
    ]

    for run_id in stale_run_ids:
        if run_id in _active_emitters:
            _active_emitters[run_id].close()
            del _active_emitters[run_id]
        if run_id in _emitter_timestamps:
            del _emitter_timestamps[run_id]

    return len(stale_run_ids)


def remove_emitter_on_completion(run_id: str) -> None:
    """Remove emitter when COMPLETE or ERROR event emitted.

    Called after pipeline completes to immediately free resources.

    Args:
        run_id: Run identifier to clean up.
    """
    if run_id in _active_emitters:
        _active_emitters[run_id].close()
        del _active_emitters[run_id]
    if run_id in _emitter_timestamps:
        del _emitter_timestamps[run_id]


# =============================================================================
# Request/Response Models
# =============================================================================


class StudySourceRequest(BaseModel):
    """Request model for study source data."""

    study_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    abstract: str = Field(..., min_length=1)
    methods: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    sample_size: int | None = None
    effect_size: float | None = None
    variance: float | None = None
    ci_lower: float | None = None
    ci_upper: float | None = None


class PICOQueryRequest(BaseModel):
    """Request model for PICO query."""

    population: str = Field(..., min_length=1)
    intervention: str = Field(..., min_length=1)
    comparison: str | None = None
    outcome: str = Field(..., min_length=1)


class MetaAnalysisRequest(BaseModel):
    """Request body for starting meta-analysis."""

    query: dict[str, Any]  # PICOQuery as dict for flexibility
    study_sources: list[dict[str, Any]]
    outcome_of_interest: str = Field(..., min_length=1)


class MetaAnalysisResponse(BaseModel):
    """Response for meta-analysis start."""

    run_id: str
    status: str = "QUEUED"
    message: str = "Meta-analysis started"


# =============================================================================
# Background Task Runner
# =============================================================================


def start_meta_analysis(
    run_id: str,
    request: MetaAnalysisRequest,
    emitter: EventEmitter,
) -> str:
    """Start meta-analysis in background.

    This function runs the orchestrator synchronously (wrapped in asyncio.to_thread
    when called from async context).

    Args:
        run_id: Unique run identifier.
        request: Meta-analysis request data.
        emitter: Event emitter for progress updates.

    Returns:
        run_id for tracking.
    """
    from procedurewriter.agents.meta_analysis.orchestrator import (
        MetaAnalysisOrchestrator,
        OrchestratorInput,
    )
    from procedurewriter.agents.meta_analysis.screener_agent import PICOQuery
    from procedurewriter.llm.providers import LLMProvider

    # Get LLM provider (would be injected in production)
    llm = LLMProvider.get_default()

    orchestrator = MetaAnalysisOrchestrator(llm=llm, emitter=emitter)

    pico_query = PICOQuery(
        population=request.query.get("population", ""),
        intervention=request.query.get("intervention", ""),
        comparison=request.query.get("comparison"),
        outcome=request.query.get("outcome", ""),
    )

    input_data = OrchestratorInput(
        query=pico_query,
        study_sources=request.study_sources,
        outcome_of_interest=request.outcome_of_interest,
        run_id=run_id,
    )

    result = orchestrator.execute(input_data)

    # Signal completion
    emitter.emit(EventType.SYNTHESIS_COMPLETE, {
        "run_id": run_id,
        "status": "DONE",
        "included_studies": len(result.output.included_study_ids),
    })

    return run_id


async def _run_meta_analysis_async(
    run_id: str,
    request: MetaAnalysisRequest,
    emitter: EventEmitter,
) -> None:
    """Async wrapper for meta-analysis execution."""
    await asyncio.to_thread(start_meta_analysis, run_id, request, emitter)


# =============================================================================
# API Endpoints
# =============================================================================


@router.post("/meta-analysis", status_code=202, response_model=MetaAnalysisResponse)
async def create_meta_analysis(
    request: MetaAnalysisRequest,
    background_tasks: BackgroundTasks,
) -> MetaAnalysisResponse:
    """Start a new meta-analysis.

    Returns 202 Accepted with run_id for tracking progress via SSE.
    """
    # Validate PICO query
    query = request.query
    if not query.get("population") or not query.get("intervention") or not query.get("outcome"):
        raise HTTPException(
            status_code=422,
            detail="PICO query must include population, intervention, and outcome",
        )

    run_id = f"ma-{uuid.uuid4().hex[:12]}"

    # Create event emitter for this run with timestamp
    emitter = EventEmitter()
    _active_emitters[run_id] = emitter
    _emitter_timestamps[run_id] = time.time()

    # Start background task
    background_tasks.add_task(_run_meta_analysis_async, run_id, request, emitter)

    return MetaAnalysisResponse(run_id=run_id)


async def get_meta_analysis_events(run_id: str) -> AsyncGenerator[dict[str, Any], None]:
    """Get SSE event generator for meta-analysis run.

    Subscribes to all event types including ERROR and COMPLETE for proper
    termination and cleanup.

    Args:
        run_id: Run identifier.

    Yields:
        Event dictionaries with type and data.
    """
    from procedurewriter.pipeline.events import PipelineEvent

    emitter = _active_emitters.get(run_id)
    if emitter is None:
        yield {"event": "error", "data": {"message": "Run not found"}}
        return

    # Subscribe to emitter (returns a Queue)
    queue = emitter.subscribe()

    try:
        while True:
            try:
                # Wait for event with timeout
                event: PipelineEvent | None = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None, queue.get, True, 30.0
                    ),
                    timeout=35.0,
                )

                if event is None:
                    # Sentinel value - emitter closed
                    break

                yield {"event": event.event_type.value, "data": event.data}

                # Terminate on completion events
                if event.event_type in (
                    EventType.SYNTHESIS_COMPLETE,
                    EventType.COMPLETE,
                    EventType.ERROR,
                ):
                    # Cleanup emitter on completion
                    remove_emitter_on_completion(run_id)
                    break

            except (asyncio.TimeoutError, Exception):
                # Send keepalive on timeout
                yield {"event": "keepalive", "data": {}}
    finally:
        # Unsubscribe from queue
        emitter.unsubscribe(queue)


@router.get("/meta-analysis/{run_id}/stream")
async def stream_meta_analysis(run_id: str) -> StreamingResponse:
    """Stream meta-analysis events via SSE.

    Args:
        run_id: Run identifier from POST /api/meta-analysis.

    Returns:
        SSE stream of pipeline events.
    """

    async def event_generator() -> AsyncGenerator[str, None]:
        async for event in get_meta_analysis_events(run_id):
            event_type = event.get("event", "message")
            data = json.dumps(event.get("data", {}))
            yield f"event: {event_type}\ndata: {data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
