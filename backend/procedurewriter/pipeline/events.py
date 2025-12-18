"""
Pipeline event system for SSE streaming.

Provides real-time progress updates during procedure generation.
Events are emitted at key stages: source gathering, agent execution, quality checks.

NO MOCKS - This integrates with real pipeline execution.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from queue import Full, Queue
from typing import Any


class EventType(Enum):
    """Event types for pipeline progress tracking."""

    # Source gathering phase
    PROGRESS = "progress"
    SOURCES_FOUND = "sources_found"

    # Agent execution (orchestrator)
    AGENT_START = "agent_start"
    AGENT_COMPLETE = "agent_complete"

    # Quality loop
    QUALITY_CHECK = "quality_check"
    ITERATION_START = "iteration_start"

    # Completion
    COMPLETE = "complete"
    ERROR = "error"
    COST_UPDATE = "cost_update"


@dataclass
class PipelineEvent:
    """A single event from the pipeline."""

    event_type: EventType
    data: dict[str, Any]
    timestamp: float = field(default_factory=time.time)

    def to_sse(self) -> str:
        """Format as Server-Sent Event."""
        import json
        payload = {
            "event": self.event_type.value,
            "data": self.data,
            "timestamp": self.timestamp,
        }
        return f"data: {json.dumps(payload)}\n\n"


class EventEmitter:
    """
    Real event emitter that integrates with pipeline execution.

    Supports multiple subscribers (SSE connections) per run.
    Thread-safe for use from sync pipeline code.

    Usage in pipeline:
        emitter = get_emitter(run_id)
        emitter.emit(EventType.AGENT_START, {"agent": "WriterAgent"})
        # ... do work ...
        emitter.emit(EventType.AGENT_COMPLETE, {"agent": "WriterAgent"})
    """

    def __init__(self) -> None:
        self._subscribers: list[Queue[PipelineEvent | None]] = []
        self._closed = False

    def subscribe(self) -> Queue[PipelineEvent | None]:
        """Create a new subscriber queue for SSE connection."""
        queue: Queue[PipelineEvent | None] = Queue()
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: Queue[PipelineEvent | None]) -> None:
        """Remove a subscriber when SSE connection closes."""
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    def emit(self, event_type: EventType, data: dict[str, Any]) -> None:
        """
        Emit event to all subscribers.

        Safe to call from sync code - uses put_nowait.
        """
        if self._closed:
            return

        event = PipelineEvent(event_type=event_type, data=data)

        for queue in self._subscribers:
            try:
                queue.put_nowait(event)
            except Full:
                # Skip if queue is full (slow consumer)
                pass

    def close(self) -> None:
        """Signal end of events to all subscribers."""
        self._closed = True
        for queue in self._subscribers:
            try:
                queue.put_nowait(None)  # Sentinel value
            except Full:
                pass

    @property
    def has_subscribers(self) -> bool:
        """Check if any SSE connections are active."""
        return len(self._subscribers) > 0


# Global registry of active emitters by run_id
_active_emitters: dict[str, EventEmitter] = {}


def get_emitter(run_id: str) -> EventEmitter:
    """
    Get or create emitter for a run.

    Called at pipeline start to get emitter for event broadcasting.
    """
    if run_id not in _active_emitters:
        _active_emitters[run_id] = EventEmitter()
    return _active_emitters[run_id]


def get_emitter_if_exists(run_id: str) -> EventEmitter | None:
    """
    Get emitter if it exists, None otherwise.

    Used by SSE endpoint to check if run is active.
    """
    return _active_emitters.get(run_id)


def remove_emitter(run_id: str) -> None:
    """
    Clean up emitter after run completes.

    Closes all subscriber connections and removes from registry.
    """
    if run_id in _active_emitters:
        _active_emitters[run_id].close()
        del _active_emitters[run_id]


def list_active_runs() -> list[str]:
    """List all run_ids with active emitters."""
    return list(_active_emitters.keys())
