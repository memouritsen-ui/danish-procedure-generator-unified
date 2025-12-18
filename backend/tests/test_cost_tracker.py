"""
Tests for Sprint 4: Cost Tracking.

Tests the CostTracker utility and session-level cost tracking.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from procedurewriter.llm import (
    CostEntry,
    CostSummary,
    CostTracker,
    get_session_tracker,
    reset_session_tracker,
)


@dataclass
class MockLLMResponse:
    """Mock LLM response for testing."""

    content: str = "Test response"
    model: str = "gpt-4o-mini"
    input_tokens: int = 100
    output_tokens: int = 50
    total_tokens: int = 150
    cost_usd: float = 0.001


class TestCostEntry:
    """Tests for CostEntry dataclass."""

    def test_cost_entry_creation(self):
        """Test CostEntry can be created with all fields."""
        entry = CostEntry(
            timestamp="2024-01-01T00:00:00+00:00",
            model="gpt-4o-mini",
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            cost_usd=0.001,
            operation="test",
        )
        assert entry.model == "gpt-4o-mini"
        assert entry.input_tokens == 100
        assert entry.output_tokens == 50
        assert entry.total_tokens == 150
        assert entry.cost_usd == 0.001
        assert entry.operation == "test"

    def test_cost_entry_default_operation(self):
        """Test CostEntry defaults operation to 'unknown'."""
        entry = CostEntry(
            timestamp="2024-01-01T00:00:00+00:00",
            model="gpt-4o-mini",
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            cost_usd=0.001,
        )
        assert entry.operation == "unknown"


class TestCostSummary:
    """Tests for CostSummary dataclass."""

    def test_cost_summary_empty(self):
        """Test CostSummary starts with zero values."""
        summary = CostSummary()
        assert summary.total_input_tokens == 0
        assert summary.total_output_tokens == 0
        assert summary.total_tokens == 0
        assert summary.total_cost_usd == 0.0
        assert summary.call_count == 0
        assert summary.entries == []

    def test_cost_summary_add_entry(self):
        """Test adding entries to CostSummary."""
        summary = CostSummary()
        entry = CostEntry(
            timestamp="2024-01-01T00:00:00+00:00",
            model="gpt-4o-mini",
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            cost_usd=0.001,
            operation="test",
        )
        summary.add_entry(entry)

        assert summary.total_input_tokens == 100
        assert summary.total_output_tokens == 50
        assert summary.total_tokens == 150
        assert summary.total_cost_usd == 0.001
        assert summary.call_count == 1
        assert len(summary.entries) == 1

    def test_cost_summary_add_multiple_entries(self):
        """Test adding multiple entries accumulates correctly."""
        summary = CostSummary()
        for i in range(3):
            entry = CostEntry(
                timestamp=f"2024-01-01T00:0{i}:00+00:00",
                model="gpt-4o-mini",
                input_tokens=100,
                output_tokens=50,
                total_tokens=150,
                cost_usd=0.001,
                operation=f"test_{i}",
            )
            summary.add_entry(entry)

        assert summary.total_input_tokens == 300
        assert summary.total_output_tokens == 150
        assert summary.total_tokens == 450
        assert summary.total_cost_usd == pytest.approx(0.003)
        assert summary.call_count == 3
        assert len(summary.entries) == 3

    def test_cost_summary_to_dict(self):
        """Test CostSummary.to_dict() method."""
        summary = CostSummary()
        entry = CostEntry(
            timestamp="2024-01-01T00:00:00+00:00",
            model="gpt-4o-mini",
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            cost_usd=0.001234,
            operation="test",
        )
        summary.add_entry(entry)

        d = summary.to_dict()
        assert d["total_input_tokens"] == 100
        assert d["total_output_tokens"] == 50
        assert d["total_tokens"] == 150
        assert d["total_cost_usd"] == 0.001234
        assert d["call_count"] == 1
        # Note: entries are not included in to_dict()
        assert "entries" not in d


class TestCostTracker:
    """Tests for CostTracker class."""

    def test_tracker_initialization(self):
        """Test CostTracker initializes with empty summary."""
        tracker = CostTracker()
        summary = tracker.get_summary()
        assert summary.call_count == 0
        assert summary.total_cost_usd == 0.0

    def test_tracker_track_response(self):
        """Test tracking an LLM response."""
        tracker = CostTracker()
        response = MockLLMResponse()
        entry = tracker.track(response, operation="test_op")

        assert entry.model == "gpt-4o-mini"
        assert entry.input_tokens == 100
        assert entry.output_tokens == 50
        assert entry.cost_usd == 0.001
        assert entry.operation == "test_op"

        summary = tracker.get_summary()
        assert summary.call_count == 1
        assert summary.total_cost_usd == 0.001

    def test_tracker_properties(self):
        """Test CostTracker convenience properties."""
        tracker = CostTracker()
        response = MockLLMResponse(input_tokens=200, output_tokens=100, total_tokens=300, cost_usd=0.002)
        tracker.track(response)

        assert tracker.total_cost_usd == 0.002
        assert tracker.total_tokens == 300
        assert tracker.call_count == 1

    def test_tracker_reset(self):
        """Test CostTracker.reset() returns summary and clears state."""
        tracker = CostTracker()
        tracker.track(MockLLMResponse())
        tracker.track(MockLLMResponse())

        final = tracker.reset()
        assert final.call_count == 2
        assert final.total_cost_usd == pytest.approx(0.002)

        # After reset, should be empty
        new_summary = tracker.get_summary()
        assert new_summary.call_count == 0
        assert new_summary.total_cost_usd == 0.0


class TestSessionTracker:
    """Tests for global session tracker functions."""

    def test_get_session_tracker_creates_singleton(self):
        """Test get_session_tracker returns same instance."""
        # Reset first to start clean
        reset_session_tracker()

        tracker1 = get_session_tracker()
        tracker2 = get_session_tracker()
        assert tracker1 is tracker2

    def test_reset_session_tracker(self):
        """Test reset_session_tracker clears and returns summary."""
        # Ensure clean state
        reset_session_tracker()

        tracker = get_session_tracker()
        tracker.track(MockLLMResponse())

        summary = reset_session_tracker()
        assert summary.call_count == 1

        # After reset, get_session_tracker returns new instance
        new_tracker = get_session_tracker()
        assert new_tracker.get_summary().call_count == 0

    def test_reset_session_tracker_when_none(self):
        """Test reset_session_tracker handles None tracker."""
        # Force _session_tracker to None by resetting twice
        reset_session_tracker()
        summary = reset_session_tracker()

        # Should return empty summary, not raise
        assert summary.call_count == 0
        assert summary.total_cost_usd == 0.0


class TestCostSummarySchema:
    """Tests for CostSummaryResponse Pydantic schema."""

    def test_cost_summary_response_schema(self):
        """Test CostSummaryResponse schema has all fields."""
        from procedurewriter.schemas import CostSummaryResponse

        summary = CostSummaryResponse(
            total_runs=10,
            total_cost_usd=0.5,
            total_input_tokens=10000,
            total_output_tokens=5000,
            total_tokens=15000,
            avg_cost_per_run=0.05,
        )
        assert summary.total_runs == 10
        assert summary.total_cost_usd == 0.5
        assert summary.total_input_tokens == 10000
        assert summary.total_output_tokens == 5000
        assert summary.total_tokens == 15000
        assert summary.avg_cost_per_run == 0.05

    def test_cost_summary_response_nullable_avg(self):
        """Test CostSummaryResponse allows null avg_cost_per_run."""
        from procedurewriter.schemas import CostSummaryResponse

        summary = CostSummaryResponse(
            total_runs=0,
            total_cost_usd=0.0,
            total_input_tokens=0,
            total_output_tokens=0,
            total_tokens=0,
            avg_cost_per_run=None,
        )
        assert summary.avg_cost_per_run is None
