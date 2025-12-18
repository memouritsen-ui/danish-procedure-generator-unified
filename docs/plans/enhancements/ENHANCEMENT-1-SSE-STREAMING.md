# Enhancement 1: Real-Time SSE Streaming Output

## Status: NOT STARTED

**Priority**: 1 (Highest)
**Estimated Effort**: 2-3 days
**Dependencies**: None (can start immediately)

---

## SESSION START CHECKLIST

Before implementing ANY part of this enhancement, execute:

```
Skill(superpowers:using-superpowers)
Skill(superpowers:test-driven-development)
Skill(superpowers:verification-before-completion)
```

**REMINDER**: NO DUMMY/MOCK IMPLEMENTATIONS. All code must be production-ready.

---

## Problem Statement

Current UX flow:
1. User clicks "Generér"
2. User sees "Kører..." for 45-90 seconds
3. User has no visibility into progress
4. User cannot abort if wrong procedure started

This creates poor user experience and wastes time when errors occur late in the process.

---

## Solution Overview

Replace HTTP polling with Server-Sent Events (SSE) to stream progress in real-time:

```
[User clicks Generate]
     ↓
[SSE Connection Established]
     ↓
[Stream: "Fetching sources..."] → User sees immediately
     ↓
[Stream: "Writing Indikationer..."] → User sees section progress
     ↓
[Stream: "Writing Kontraindikationer..."]
     ↓
[Stream: "Quality check: 8/10"] → User sees quality
     ↓
[Stream: "DONE" + full result]
```

---

## Technical Specification

### Backend Changes

#### File: `backend/procedurewriter/main.py`

**New Endpoint**: `GET /api/runs/{run_id}/stream`

```python
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator
import json

@app.get("/api/runs/{run_id}/stream")
async def api_run_stream(run_id: str) -> StreamingResponse:
    """
    Stream run progress via Server-Sent Events.

    SSE Format:
    data: {"event": "progress", "stage": "sources", "message": "Fetching 12 sources..."}
    data: {"event": "section", "name": "Indikationer", "status": "writing"}
    data: {"event": "section", "name": "Indikationer", "status": "complete", "preview": "..."}
    data: {"event": "quality", "score": 8, "iteration": 1}
    data: {"event": "complete", "run_id": "...", "quality_score": 9}
    data: {"event": "error", "message": "..."}
    """
    async def event_stream() -> AsyncGenerator[str, None]:
        # Implementation connects to real pipeline events
        pass

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )
```

#### File: `backend/procedurewriter/pipeline/events.py` (NEW)

```python
"""
Pipeline event system for SSE streaming.

NO MOCKS - This must integrate with real pipeline execution.
"""
from dataclasses import dataclass, field
from typing import Callable, Any
from enum import Enum
import asyncio
from collections.abc import AsyncGenerator

class EventType(Enum):
    PROGRESS = "progress"
    SECTION_START = "section_start"
    SECTION_COMPLETE = "section_complete"
    QUALITY_CHECK = "quality_check"
    ITERATION = "iteration"
    COMPLETE = "complete"
    ERROR = "error"
    COST_UPDATE = "cost_update"

@dataclass
class PipelineEvent:
    event_type: EventType
    data: dict[str, Any]
    timestamp: float = field(default_factory=lambda: __import__('time').time())

class EventEmitter:
    """
    Real event emitter that integrates with pipeline execution.

    Usage in pipeline:
        emitter = EventEmitter()
        emitter.emit(EventType.SECTION_START, {"name": "Indikationer"})
        # ... do work ...
        emitter.emit(EventType.SECTION_COMPLETE, {"name": "Indikationer", "preview": "..."})
    """

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[PipelineEvent]] = []
        self._closed = False

    def subscribe(self) -> asyncio.Queue[PipelineEvent]:
        """Create a new subscriber queue."""
        queue: asyncio.Queue[PipelineEvent] = asyncio.Queue()
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[PipelineEvent]) -> None:
        """Remove a subscriber."""
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    def emit(self, event_type: EventType, data: dict[str, Any]) -> None:
        """Emit event to all subscribers."""
        if self._closed:
            return
        event = PipelineEvent(event_type=event_type, data=data)
        for queue in self._subscribers:
            queue.put_nowait(event)

    def close(self) -> None:
        """Signal end of events."""
        self._closed = True
        for queue in self._subscribers:
            queue.put_nowait(None)  # Sentinel

# Global registry of active emitters by run_id
_active_emitters: dict[str, EventEmitter] = {}

def get_emitter(run_id: str) -> EventEmitter:
    """Get or create emitter for a run."""
    if run_id not in _active_emitters:
        _active_emitters[run_id] = EventEmitter()
    return _active_emitters[run_id]

def remove_emitter(run_id: str) -> None:
    """Clean up emitter after run completes."""
    if run_id in _active_emitters:
        _active_emitters[run_id].close()
        del _active_emitters[run_id]
```

#### File: `backend/procedurewriter/pipeline/run.py` (MODIFY)

Add event emissions at key points:

```python
from procedurewriter.pipeline.events import get_emitter, remove_emitter, EventType

def run_pipeline(...):
    emitter = get_emitter(run_id)

    try:
        # Source collection
        emitter.emit(EventType.PROGRESS, {
            "stage": "sources",
            "message": f"Collecting sources for {procedure}..."
        })

        # ... existing source collection code ...

        emitter.emit(EventType.PROGRESS, {
            "stage": "sources",
            "message": f"Found {len(sources)} sources"
        })

        # Section writing
        for section in sections:
            emitter.emit(EventType.SECTION_START, {
                "name": section["heading"],
                "index": section_index,
                "total": len(sections)
            })

            # ... existing section writing code ...

            emitter.emit(EventType.SECTION_COMPLETE, {
                "name": section["heading"],
                "preview": content[:200] + "..." if len(content) > 200 else content
            })

        # Quality check
        emitter.emit(EventType.QUALITY_CHECK, {
            "score": quality_score,
            "iteration": iteration,
            "max_iterations": 3
        })

        # Cost update
        emitter.emit(EventType.COST_UPDATE, {
            "total_cost_usd": tracker.total_cost,
            "tokens_used": tracker.total_tokens
        })

        # Complete
        emitter.emit(EventType.COMPLETE, {
            "run_id": run_id,
            "quality_score": quality_score,
            "total_cost_usd": tracker.total_cost
        })

    except Exception as e:
        emitter.emit(EventType.ERROR, {"message": str(e)})
        raise
    finally:
        remove_emitter(run_id)
```

### Frontend Changes

#### File: `frontend/src/hooks/useSSE.ts` (NEW)

```typescript
import { useEffect, useState, useCallback, useRef } from "react";

export interface SSEEvent {
  event: string;
  data: Record<string, unknown>;
}

export interface SSEState {
  connected: boolean;
  events: SSEEvent[];
  lastEvent: SSEEvent | null;
  error: string | null;
}

export function useSSE(url: string | null): SSEState {
  const [state, setState] = useState<SSEState>({
    connected: false,
    events: [],
    lastEvent: null,
    error: null,
  });

  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!url) {
      return;
    }

    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      setState(prev => ({ ...prev, connected: true, error: null }));
    };

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as SSEEvent;
        setState(prev => ({
          ...prev,
          events: [...prev.events, data],
          lastEvent: data,
        }));
      } catch (e) {
        console.error("Failed to parse SSE event:", e);
      }
    };

    eventSource.onerror = () => {
      setState(prev => ({
        ...prev,
        connected: false,
        error: "Connection lost",
      }));
      eventSource.close();
    };

    return () => {
      eventSource.close();
      eventSourceRef.current = null;
    };
  }, [url]);

  return state;
}
```

#### File: `frontend/src/pages/WritePage.tsx` (MODIFY)

Replace polling with SSE:

```typescript
import { useSSE } from "../hooks/useSSE";

// Inside component:
const [streamUrl, setStreamUrl] = useState<string | null>(null);
const { connected, lastEvent, error: sseError } = useSSE(streamUrl);

// When starting generation:
async function onGenerate() {
  setError(null);
  setRun(null);
  setSources([]);
  setStatus("running");
  setProgress([]);

  try {
    const id = await apiWrite({ procedure: procedure.trim(), context: context.trim() || undefined });
    setRunId(id);
    setStreamUrl(`/api/runs/${id}/stream`);
  } catch (e) {
    setStatus("failed");
    setError(e instanceof Error ? e.message : String(e));
  }
}

// Handle SSE events:
useEffect(() => {
  if (!lastEvent) return;

  switch (lastEvent.event) {
    case "progress":
      setProgress(prev => [...prev, lastEvent.data.message as string]);
      break;
    case "section_start":
      setCurrentSection(lastEvent.data.name as string);
      break;
    case "section_complete":
      setSectionPreviews(prev => ({
        ...prev,
        [lastEvent.data.name as string]: lastEvent.data.preview as string
      }));
      break;
    case "quality_check":
      setQualityScore(lastEvent.data.score as number);
      setIteration(lastEvent.data.iteration as number);
      break;
    case "cost_update":
      setCost(lastEvent.data.total_cost_usd as number);
      break;
    case "complete":
      setStatus("done");
      setStreamUrl(null);
      // Fetch full result
      void loadFullResult(runId!);
      break;
    case "error":
      setStatus("failed");
      setError(lastEvent.data.message as string);
      setStreamUrl(null);
      break;
  }
}, [lastEvent]);
```

#### File: `frontend/src/components/ProgressIndicator.tsx` (NEW)

```typescript
interface ProgressIndicatorProps {
  messages: string[];
  currentSection: string | null;
  sectionPreviews: Record<string, string>;
  qualityScore: number | null;
  iteration: number;
  cost: number | null;
}

export function ProgressIndicator({
  messages,
  currentSection,
  sectionPreviews,
  qualityScore,
  iteration,
  cost,
}: ProgressIndicatorProps) {
  return (
    <div className="progress-indicator">
      <div className="progress-header">
        {currentSection ? (
          <span>Writing: <strong>{currentSection}</strong></span>
        ) : (
          <span>Preparing...</span>
        )}
        {cost !== null && (
          <span className="cost-badge">${cost.toFixed(4)}</span>
        )}
      </div>

      <div className="progress-messages">
        {messages.map((msg, i) => (
          <div key={i} className="progress-message">
            <span className="checkmark">✓</span> {msg}
          </div>
        ))}
      </div>

      {Object.entries(sectionPreviews).length > 0 && (
        <div className="section-previews">
          {Object.entries(sectionPreviews).map(([name, preview]) => (
            <div key={name} className="section-preview">
              <strong>{name}</strong>
              <p className="muted">{preview}</p>
            </div>
          ))}
        </div>
      )}

      {qualityScore !== null && (
        <div className="quality-indicator">
          Quality: {qualityScore}/10 (Iteration {iteration}/3)
        </div>
      )}
    </div>
  );
}
```

---

## Database Changes

**No database schema changes required** for this enhancement.

---

## Test Requirements

### Backend Tests

#### File: `backend/tests/test_sse_streaming.py` (NEW)

```python
"""
SSE Streaming Tests

IMPORTANT: These tests use REAL pipeline execution.
NO MOCKS for LLM calls - use Ollama or real API keys.
"""
import pytest
import asyncio
from httpx import AsyncClient
from procedurewriter.main import app
from procedurewriter.pipeline.events import EventEmitter, EventType, get_emitter

class TestEventEmitter:
    """Test the event emitter system."""

    def test_emit_and_receive(self):
        """Events emitted are received by subscribers."""
        emitter = EventEmitter()
        queue = emitter.subscribe()

        emitter.emit(EventType.PROGRESS, {"message": "test"})

        event = queue.get_nowait()
        assert event.event_type == EventType.PROGRESS
        assert event.data["message"] == "test"

    def test_multiple_subscribers(self):
        """Multiple subscribers all receive events."""
        emitter = EventEmitter()
        q1 = emitter.subscribe()
        q2 = emitter.subscribe()

        emitter.emit(EventType.SECTION_START, {"name": "Test"})

        e1 = q1.get_nowait()
        e2 = q2.get_nowait()
        assert e1.data == e2.data

    def test_unsubscribe(self):
        """Unsubscribed queues don't receive events."""
        emitter = EventEmitter()
        queue = emitter.subscribe()
        emitter.unsubscribe(queue)

        emitter.emit(EventType.COMPLETE, {})

        assert queue.empty()

    def test_close_sends_sentinel(self):
        """Close sends None sentinel to all subscribers."""
        emitter = EventEmitter()
        queue = emitter.subscribe()

        emitter.close()

        assert queue.get_nowait() is None


class TestSSEEndpoint:
    """Integration tests for SSE endpoint."""

    @pytest.mark.asyncio
    async def test_sse_endpoint_streams_events(self):
        """SSE endpoint streams events from pipeline."""
        # This test requires a real pipeline run
        # Configure with Ollama or real API key
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Start a real run
            response = await client.post(
                "/api/write",
                json={"procedure": "Test procedure", "context": "test"}
            )
            run_id = response.json()["run_id"]

            # Connect to SSE stream
            events_received = []
            async with client.stream("GET", f"/api/runs/{run_id}/stream") as stream:
                async for line in stream.aiter_lines():
                    if line.startswith("data:"):
                        events_received.append(line)
                        if '"event": "complete"' in line or '"event": "error"' in line:
                            break

            # Verify we got progress events
            assert len(events_received) > 0
            assert any("progress" in e for e in events_received)
```

### Frontend Tests

#### File: `frontend/src/hooks/useSSE.test.ts` (NEW)

```typescript
import { renderHook, act } from "@testing-library/react";
import { useSSE } from "./useSSE";

describe("useSSE", () => {
  let mockEventSource: {
    onopen: (() => void) | null;
    onmessage: ((event: { data: string }) => void) | null;
    onerror: (() => void) | null;
    close: jest.Mock;
  };

  beforeEach(() => {
    mockEventSource = {
      onopen: null,
      onmessage: null,
      onerror: null,
      close: jest.fn(),
    };

    (global as any).EventSource = jest.fn(() => mockEventSource);
  });

  it("connects when URL is provided", () => {
    const { result } = renderHook(() => useSSE("/api/test/stream"));

    act(() => {
      mockEventSource.onopen?.();
    });

    expect(result.current.connected).toBe(true);
  });

  it("receives and parses events", () => {
    const { result } = renderHook(() => useSSE("/api/test/stream"));

    act(() => {
      mockEventSource.onmessage?.({
        data: JSON.stringify({ event: "progress", data: { message: "test" } }),
      });
    });

    expect(result.current.lastEvent?.event).toBe("progress");
  });

  it("handles connection errors", () => {
    const { result } = renderHook(() => useSSE("/api/test/stream"));

    act(() => {
      mockEventSource.onerror?.();
    });

    expect(result.current.connected).toBe(false);
    expect(result.current.error).toBe("Connection lost");
  });
});
```

---

## Implementation Checklist

### Phase 1: Backend Event System (Day 1)

- [ ] Create `backend/procedurewriter/pipeline/events.py`
- [ ] Add EventEmitter class with subscribe/emit/close
- [ ] Add global emitter registry
- [ ] Write unit tests for EventEmitter
- [ ] Run tests: `pytest backend/tests/test_sse_streaming.py -v`

### Phase 2: Pipeline Integration (Day 1-2)

- [ ] Modify `backend/procedurewriter/pipeline/run.py`
- [ ] Add event emissions at source collection
- [ ] Add event emissions at section writing
- [ ] Add event emissions at quality check
- [ ] Add event emissions at cost updates
- [ ] Add event emissions at completion/error
- [ ] Test with real pipeline execution

### Phase 3: SSE Endpoint (Day 2)

- [ ] Add `/api/runs/{run_id}/stream` endpoint to `main.py`
- [ ] Implement async generator for event streaming
- [ ] Add proper SSE headers
- [ ] Test endpoint with curl: `curl -N http://localhost:8000/api/runs/{id}/stream`

### Phase 4: Frontend (Day 2-3)

- [ ] Create `frontend/src/hooks/useSSE.ts`
- [ ] Create `frontend/src/components/ProgressIndicator.tsx`
- [ ] Modify `frontend/src/pages/WritePage.tsx`
- [ ] Replace polling with SSE connection
- [ ] Add progress UI components
- [ ] Test in browser with real generation

### Phase 5: Polish & Test (Day 3)

- [ ] Handle connection drops gracefully
- [ ] Add reconnection logic if needed
- [ ] Test with slow network simulation
- [ ] Test concurrent runs
- [ ] Run full test suite: `pytest`
- [ ] Manual E2E testing

---

## Current Status

**Status**: NOT STARTED

**Last Updated**: 2024-12-18

**Checkpoints Completed**:
- [ ] Phase 1: Backend Event System
- [ ] Phase 2: Pipeline Integration
- [ ] Phase 3: SSE Endpoint
- [ ] Phase 4: Frontend
- [ ] Phase 5: Polish & Test

**Blockers**: None

**Notes**: Ready to begin implementation.

---

## Session Handoff Notes

When continuing this enhancement in a new session:

1. Read this document first
2. Check "Current Status" above
3. Load skills: `Skill(superpowers:test-driven-development)`
4. Run existing tests to verify baseline: `pytest`
5. Continue from last incomplete checkbox

**REMEMBER**: No dummy/mock implementations. All code must work with real pipeline.
