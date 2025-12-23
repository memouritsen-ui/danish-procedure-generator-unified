"""
Cost Tracker - Tracks LLM usage and costs across operations.

Provides session-level and persistent cost tracking for LLM API calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from procedurewriter.llm.providers import LLMResponse


@dataclass
class CostEntry:
    """Single cost entry for an LLM call."""
    timestamp: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    operation: str = "unknown"


@dataclass
class CostSummary:
    """Aggregated cost summary."""
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    call_count: int = 0
    entries: list[CostEntry] = field(default_factory=list)
    # R7-012: Maximum entries to retain (oldest are dropped)
    max_entries: int = 10000

    def add_entry(self, entry: CostEntry) -> None:
        """Add a cost entry to the summary.

        R7-012: Rotates oldest entries when max_entries exceeded.
        """
        self.total_input_tokens += entry.input_tokens
        self.total_output_tokens += entry.output_tokens
        self.total_tokens += entry.total_tokens
        self.total_cost_usd += entry.cost_usd
        self.call_count += 1
        self.entries.append(entry)

        # R7-012: Rotate oldest entries if over limit
        if len(self.entries) > self.max_entries:
            # Keep only the most recent entries
            self.entries = self.entries[-self.max_entries:]

    def to_dict(self) -> dict:
        """Convert summary to dictionary."""
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "call_count": self.call_count,
        }


class CostTracker:
    """
    Tracks LLM costs across operations within a session.

    Usage:
        tracker = CostTracker()

        # Track an LLM response
        tracker.track(response, operation="research")

        # Get summary
        summary = tracker.get_summary()
        print(f"Total cost: ${summary.total_cost_usd:.4f}")
    """

    def __init__(self):
        self._summary = CostSummary()

    def track(self, response: LLMResponse, operation: str = "unknown") -> CostEntry:
        """
        Track an LLM response.

        Args:
            response: LLM response with usage info
            operation: Description of the operation (e.g., "research", "write")

        Returns:
            CostEntry for this call
        """
        entry = CostEntry(
            timestamp=datetime.now(UTC).replace(microsecond=0).isoformat(),
            model=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            total_tokens=response.total_tokens,
            cost_usd=response.cost_usd,
            operation=operation,
        )
        self._summary.add_entry(entry)
        return entry

    def get_summary(self) -> CostSummary:
        """Get the current cost summary."""
        return self._summary

    def reset(self) -> CostSummary:
        """Reset tracker and return final summary."""
        final = self._summary
        self._summary = CostSummary()
        return final

    @property
    def total_cost_usd(self) -> float:
        """Get total cost in USD."""
        return self._summary.total_cost_usd

    @property
    def total_tokens(self) -> int:
        """Get total tokens used."""
        return self._summary.total_tokens

    @property
    def call_count(self) -> int:
        """Get number of LLM calls."""
        return self._summary.call_count


# Global tracker for session-level costs
_session_tracker: CostTracker | None = None


def get_session_tracker() -> CostTracker:
    """Get or create the global session tracker."""
    global _session_tracker
    if _session_tracker is None:
        _session_tracker = CostTracker()
    return _session_tracker


def reset_session_tracker() -> CostSummary:
    """Reset the global session tracker and return final summary."""
    global _session_tracker
    if _session_tracker is None:
        return CostSummary()
    summary = _session_tracker.reset()
    _session_tracker = None
    return summary
