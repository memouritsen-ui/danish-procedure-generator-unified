"""Performance profiling utilities for the pipeline."""
from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Generator


@dataclass
class TimingEntry:
    """A single timing measurement."""
    name: str
    duration_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineProfile:
    """Collects timing data for a pipeline run."""
    entries: list[TimingEntry] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)

    @contextmanager
    def time(self, name: str, **metadata: Any) -> Generator[None, None, None]:
        """Context manager to time a block of code."""
        start = time.perf_counter()
        try:
            yield
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            self.entries.append(TimingEntry(name=name, duration_ms=duration_ms, metadata=metadata))

    def add(self, name: str, duration_ms: float, **metadata: Any) -> None:
        """Add a timing entry directly."""
        self.entries.append(TimingEntry(name=name, duration_ms=duration_ms, metadata=metadata))

    @property
    def total_ms(self) -> float:
        """Total time across all entries."""
        return sum(e.duration_ms for e in self.entries)

    def summary(self) -> dict[str, Any]:
        """Generate a summary of timing data."""
        if not self.entries:
            return {"total_ms": 0, "entries": [], "by_category": {}}

        # Group by category (first part of name before ":")
        by_category: dict[str, float] = {}
        for e in self.entries:
            category = e.name.split(":")[0] if ":" in e.name else e.name
            by_category[category] = by_category.get(category, 0) + e.duration_ms

        # Sort entries by duration
        sorted_entries = sorted(self.entries, key=lambda x: x.duration_ms, reverse=True)

        return {
            "total_ms": round(self.total_ms, 2),
            "elapsed_ms": round((time.time() - self.start_time) * 1000, 2),
            "entries": [
                {
                    "name": e.name,
                    "duration_ms": round(e.duration_ms, 2),
                    "pct": round(e.duration_ms / self.total_ms * 100, 1) if self.total_ms > 0 else 0,
                    **e.metadata,
                }
                for e in sorted_entries[:20]  # Top 20 slowest
            ],
            "by_category": {k: round(v, 2) for k, v in sorted(by_category.items(), key=lambda x: -x[1])},
        }

    def print_summary(self) -> None:
        """Print a formatted summary to stdout."""
        summary = self.summary()
        print(f"\n{'='*60}")
        print(f"Pipeline Performance Profile")
        print(f"{'='*60}")
        print(f"Total time: {summary['total_ms']:.0f}ms")
        print(f"\nBy Category:")
        for cat, ms in summary["by_category"].items():
            pct = ms / summary["total_ms"] * 100 if summary["total_ms"] > 0 else 0
            print(f"  {cat:<25} {ms:>8.0f}ms ({pct:>5.1f}%)")
        print(f"\nSlowest Operations:")
        for i, entry in enumerate(summary["entries"][:10], 1):
            print(f"  {i}. {entry['name']:<35} {entry['duration_ms']:>8.0f}ms ({entry['pct']:>5.1f}%)")
        print(f"{'='*60}\n")


# Global profiler instance (can be None when profiling is disabled)
_profiler: PipelineProfile | None = None


def get_profiler() -> PipelineProfile | None:
    """Get the current profiler instance."""
    return _profiler


def start_profiling() -> PipelineProfile:
    """Start a new profiling session."""
    global _profiler
    _profiler = PipelineProfile()
    return _profiler


def stop_profiling() -> PipelineProfile | None:
    """Stop profiling and return the profile data."""
    global _profiler
    profile = _profiler
    _profiler = None
    return profile


@contextmanager
def profile_section(name: str, **metadata: Any) -> Generator[None, None, None]:
    """Context manager to profile a section (no-op if profiling is disabled)."""
    profiler = get_profiler()
    if profiler is None:
        yield
    else:
        with profiler.time(name, **metadata):
            yield
