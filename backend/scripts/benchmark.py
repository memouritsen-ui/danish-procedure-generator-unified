#!/usr/bin/env python3
"""
Benchmark script for profiling pipeline performance.

Usage:
    python scripts/benchmark.py [--iterations N] [--procedure "name"]
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from procedurewriter.db import init_db
from procedurewriter.pipeline.profiler import PipelineProfile
from procedurewriter.pipeline.run import run_pipeline
from procedurewriter.settings import Settings


def run_benchmark(
    procedure: str = "Blodprøvetagning",
    context: str = "Voksen patient på akutmodtagelse",
    iterations: int = 1,
    dummy_mode: bool = True,
) -> list[dict]:
    """Run the pipeline and collect timing data."""
    settings = Settings()
    settings.dummy_mode = dummy_mode

    # Initialize database
    settings.runs_dir.mkdir(parents=True, exist_ok=True)
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    (settings.resolved_data_dir / "index").mkdir(parents=True, exist_ok=True)
    init_db(settings.db_path)

    results = []

    for i in range(iterations):
        run_id = f"bench_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_{i}"
        created_at = datetime.now(UTC).isoformat()

        profile = PipelineProfile()

        print(f"\n{'='*60}")
        print(f"Benchmark run {i+1}/{iterations}")
        print(f"Procedure: {procedure}")
        print(f"Dummy mode: {dummy_mode}")
        print(f"{'='*60}")

        start = time.perf_counter()

        with profile.time("pipeline:total"):
            with profile.time("pipeline:initialization"):
                pass  # Settings already loaded

            run_pipeline(
                run_id=run_id,
                created_at_utc=created_at,
                procedure=procedure,
                context=context,
                settings=settings,
                library_sources=[],
                openai_api_key=None,
                anthropic_api_key=None,
            )

        total_time = (time.perf_counter() - start) * 1000

        profile.print_summary()

        results.append({
            "iteration": i + 1,
            "total_ms": round(total_time, 2),
            "run_id": run_id,
            "status": "success",
        })

    # Print summary
    if len(results) > 1:
        avg_time = sum(r["total_ms"] for r in results) / len(results)
        min_time = min(r["total_ms"] for r in results)
        max_time = max(r["total_ms"] for r in results)
        print(f"\n{'='*60}")
        print(f"Benchmark Summary ({iterations} iterations)")
        print(f"{'='*60}")
        print(f"Average: {avg_time:.0f}ms")
        print(f"Min: {min_time:.0f}ms")
        print(f"Max: {max_time:.0f}ms")
        print(f"{'='*60}")

    return results


def profile_components():
    """Profile individual pipeline components."""
    print("\n" + "="*60)
    print("Component Profiling")
    print("="*60)

    profile = PipelineProfile()
    settings = Settings()

    # Profile config loading
    from procedurewriter.config_store import load_yaml
    with profile.time("config:load_author_guide"):
        load_yaml(settings.author_guide_path)

    with profile.time("config:load_allowlist"):
        load_yaml(settings.allowlist_path)

    with profile.time("config:load_evidence_hierarchy"):
        from procedurewriter.pipeline.evidence_hierarchy import EvidenceHierarchy
        EvidenceHierarchy.from_config(settings.evidence_hierarchy_path)

    # Profile HTTP client initialization
    from procedurewriter.pipeline.fetcher import CachedHttpClient
    with profile.time("http:client_init"):
        http = CachedHttpClient(cache_dir=settings.cache_dir)
        http.close()

    # Profile text processing
    sample_text = "This is sample text for benchmarking text processing operations. " * 100
    from procedurewriter.pipeline.text_units import split_sentences
    with profile.time("text:split_sentences"):
        for _ in range(100):
            split_sentences(sample_text)

    # Profile snippet building
    # Create temp files for snippets
    import tempfile

    from procedurewriter.pipeline.retrieve import build_snippets
    from procedurewriter.pipeline.types import SourceRecord
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create sources with correct paths
        dummy_sources = []
        for i in range(10):
            path = Path(tmpdir) / f"SRC{i:04d}.txt"
            path.write_text(sample_text)
            dummy_sources.append(
                SourceRecord(
                    source_id=f"SRC{i:04d}",
                    fetched_at_utc=datetime.now(UTC).isoformat(),
                    kind="dummy",
                    title=f"Test source {i}",
                    year=2024,
                    url=None,
                    doi=None,
                    pmid=None,
                    raw_path=str(path),
                    normalized_path=str(path),
                    raw_sha256="abc123",
                    normalized_sha256="abc123",
                    extraction_notes=None,
                    terms_licence_note=None,
                    extra={},
                )
            )

        with profile.time("snippets:build"):
            snippets = build_snippets(dummy_sources)

        # Profile retrieval
        from procedurewriter.pipeline.retrieve import retrieve
        with profile.time("retrieve:bm25"):
            retrieve("blood test procedure", snippets, top_k=20, prefer_embeddings=False)

    profile.print_summary()


def main():
    parser = argparse.ArgumentParser(description="Benchmark pipeline performance")
    parser.add_argument("--iterations", "-n", type=int, default=1, help="Number of iterations")
    parser.add_argument("--procedure", "-p", type=str, default="Blodprøvetagning", help="Procedure name")
    parser.add_argument("--context", "-c", type=str, default="Voksen patient", help="Context")
    parser.add_argument("--live", action="store_true", help="Run with live API calls (not dummy mode)")
    parser.add_argument("--components", action="store_true", help="Profile individual components")

    args = parser.parse_args()

    if args.components:
        profile_components()
    else:
        run_benchmark(
            procedure=args.procedure,
            context=args.context,
            iterations=args.iterations,
            dummy_mode=not args.live,
        )


if __name__ == "__main__":
    main()
