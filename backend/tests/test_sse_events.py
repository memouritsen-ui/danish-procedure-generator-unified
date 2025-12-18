"""
Tests for SSE event system.

Tests the EventEmitter and event management functions.
"""

from procedurewriter.pipeline.events import (
    EventEmitter,
    EventType,
    PipelineEvent,
    get_emitter,
    get_emitter_if_exists,
    list_active_runs,
    remove_emitter,
)


class TestPipelineEvent:
    """Test PipelineEvent dataclass."""

    def test_event_creation(self):
        """Events are created with correct fields."""
        event = PipelineEvent(
            event_type=EventType.PROGRESS,
            data={"message": "test"},
        )
        assert event.event_type == EventType.PROGRESS
        assert event.data["message"] == "test"
        assert event.timestamp > 0

    def test_to_sse_format(self):
        """Events format correctly as SSE."""
        event = PipelineEvent(
            event_type=EventType.AGENT_START,
            data={"agent": "WriterAgent"},
        )
        sse = event.to_sse()

        assert sse.startswith("data: ")
        assert sse.endswith("\n\n")
        assert '"event": "agent_start"' in sse
        assert '"agent": "WriterAgent"' in sse


class TestEventEmitter:
    """Test EventEmitter class."""

    def test_emit_and_receive(self):
        """Events emitted are received by subscribers."""
        emitter = EventEmitter()
        queue = emitter.subscribe()

        emitter.emit(EventType.PROGRESS, {"message": "test"})

        event = queue.get_nowait()
        assert event is not None
        assert event.event_type == EventType.PROGRESS
        assert event.data["message"] == "test"

    def test_multiple_subscribers(self):
        """Multiple subscribers all receive events."""
        emitter = EventEmitter()
        q1 = emitter.subscribe()
        q2 = emitter.subscribe()

        emitter.emit(EventType.AGENT_START, {"agent": "Writer"})

        e1 = q1.get_nowait()
        e2 = q2.get_nowait()
        assert e1 is not None and e2 is not None
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

        sentinel = queue.get_nowait()
        assert sentinel is None

    def test_emit_after_close_ignored(self):
        """Events after close are ignored."""
        emitter = EventEmitter()
        queue = emitter.subscribe()
        emitter.close()

        # Drain the sentinel
        queue.get_nowait()

        # This should be ignored
        emitter.emit(EventType.PROGRESS, {"message": "ignored"})

        assert queue.empty()

    def test_has_subscribers(self):
        """has_subscribers reflects subscription state."""
        emitter = EventEmitter()

        assert not emitter.has_subscribers

        queue = emitter.subscribe()
        assert emitter.has_subscribers

        emitter.unsubscribe(queue)
        assert not emitter.has_subscribers


class TestEmitterRegistry:
    """Test global emitter registry functions."""

    def test_get_emitter_creates_new(self):
        """get_emitter creates new emitter if not exists."""
        run_id = "test-run-001"
        try:
            emitter = get_emitter(run_id)
            assert emitter is not None
            assert run_id in list_active_runs()
        finally:
            remove_emitter(run_id)

    def test_get_emitter_returns_existing(self):
        """get_emitter returns existing emitter."""
        run_id = "test-run-002"
        try:
            emitter1 = get_emitter(run_id)
            emitter2 = get_emitter(run_id)
            assert emitter1 is emitter2
        finally:
            remove_emitter(run_id)

    def test_get_emitter_if_exists(self):
        """get_emitter_if_exists returns None for unknown run."""
        assert get_emitter_if_exists("nonexistent") is None

        run_id = "test-run-003"
        try:
            get_emitter(run_id)
            assert get_emitter_if_exists(run_id) is not None
        finally:
            remove_emitter(run_id)

    def test_remove_emitter_closes_subscribers(self):
        """remove_emitter closes all subscribers."""
        run_id = "test-run-004"
        emitter = get_emitter(run_id)
        queue = emitter.subscribe()

        remove_emitter(run_id)

        # Should receive sentinel
        sentinel = queue.get_nowait()
        assert sentinel is None
        assert run_id not in list_active_runs()

    def test_list_active_runs(self):
        """list_active_runs returns all active run_ids."""
        run_ids = ["test-a", "test-b", "test-c"]
        try:
            for rid in run_ids:
                get_emitter(rid)

            active = list_active_runs()
            for rid in run_ids:
                assert rid in active
        finally:
            for rid in run_ids:
                remove_emitter(rid)


class TestEventTypes:
    """Test all event types are defined."""

    def test_all_event_types_exist(self):
        """All required event types are defined."""
        required = [
            "PROGRESS",
            "SOURCES_FOUND",
            "AGENT_START",
            "AGENT_COMPLETE",
            "QUALITY_CHECK",
            "ITERATION_START",
            "COMPLETE",
            "ERROR",
            "COST_UPDATE",
        ]
        for name in required:
            assert hasattr(EventType, name), f"Missing event type: {name}"

    def test_event_type_values(self):
        """Event type values are lowercase strings."""
        for event_type in EventType:
            assert event_type.value == event_type.name.lower()
