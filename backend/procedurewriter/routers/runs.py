"""Runs API router - handles procedure run endpoints."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

import anyio
from anthropic import AsyncAnthropic
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from procedurewriter.db import (
    get_run,
    get_version_chain,
    iter_jsonl,
    list_runs,
)
from procedurewriter.file_utils import UnsafePathError, safe_path_within
from procedurewriter.pipeline.events import get_emitter_if_exists
from procedurewriter.pipeline.versioning import (
    create_version_diff,
    diff_to_dict,
    load_procedure_markdown,
    load_source_ids,
)
from procedurewriter.protocols import (
    get_protocol,
    get_validation_results,
    save_validation_result,
    validate_run_against_protocol,
    validate_run_against_protocol_llm,
    find_similar_protocols,
)
from procedurewriter.run_bundle import build_run_bundle_zip, read_run_manifest
from procedurewriter.schemas import RunDetail, RunSummary, SourceRecord, SourcesResponse
from procedurewriter.settings import settings

router = APIRouter(prefix="/api/runs", tags=["runs"])

# Secret names for API key access
_OPENAI_SECRET_NAME = "openai_api_key"
_ANTHROPIC_SECRET_NAME = "anthropic_api_key"
_NCBI_SECRET_NAME = "ncbi_api_key"


def _effective_openai_api_key() -> str | None:
    """Get effective OpenAI API key from DB or environment."""
    from procedurewriter.db import get_secret
    return get_secret(settings.db_path, name=_OPENAI_SECRET_NAME) or os.getenv("OPENAI_API_KEY")


def _effective_ncbi_api_key() -> str | None:
    """Get effective NCBI API key from DB or settings."""
    from procedurewriter.db import get_secret
    return get_secret(settings.db_path, name=_NCBI_SECRET_NAME) or settings.ncbi_api_key


def _effective_anthropic_api_key() -> str | None:
    """Get effective Anthropic API key from DB or environment."""
    from procedurewriter.db import get_secret
    return get_secret(settings.db_path, name=_ANTHROPIC_SECRET_NAME) or os.getenv("ANTHROPIC_API_KEY")


def _sanitize_filename(name: str) -> str:
    """Sanitize a string for use as a filename.

    Preserves Danish characters (æ, ø, å) for display purposes.
    For HTTP headers, use _encode_filename_rfc5987() instead.
    """
    # Replace spaces and special chars with underscores, keep Danish chars
    sanitized = re.sub(r'[^\w\sæøåÆØÅ-]', '', name)
    sanitized = re.sub(r'\s+', '_', sanitized.strip())
    return sanitized[:100] if sanitized else "Procedure"


def _encode_filename_rfc5987(filename: str) -> str:
    """Encode filename for Content-Disposition header per RFC 5987.

    RFC 5987 allows non-ASCII characters in HTTP headers using:
    filename*=UTF-8''percent-encoded-filename

    This ensures Danish characters (æ, ø, å) work in all browsers:
    - Chrome, Firefox, Edge: Support RFC 5987
    - Safari: Falls back to ASCII filename parameter
    - IE11: Falls back to ASCII filename parameter

    Args:
        filename: The filename including extension (e.g., "Akut_hypoækmi.docx")

    Returns:
        RFC 5987 encoded string (e.g., "UTF-8''Akut_hypo%C3%A6kmi.docx")
    """
    # Encode as UTF-8 and percent-encode
    # quote() with safe='' encodes everything except unreserved chars
    # We keep some safe chars that are valid in filenames
    encoded = quote(filename, safe='')
    return f"UTF-8''{encoded}"


def _make_content_disposition(filename: str) -> str:
    """Create Content-Disposition header value with RFC 5987 support.

    Returns a header that works across all browsers:
    - Modern browsers use filename* (RFC 5987) for full Unicode support
    - Legacy browsers fall back to ASCII filename parameter

    Args:
        filename: The desired filename (may contain Danish chars)

    Returns:
        Complete Content-Disposition header value
    """
    # Create ASCII-safe fallback (replace non-ASCII with underscore)
    ascii_safe = re.sub(r'[^\x00-\x7F]', '_', filename)

    # RFC 5987 encoded version with full Unicode support
    rfc5987_encoded = _encode_filename_rfc5987(filename)

    # Return both: filename for legacy, filename* for modern browsers
    return f'attachment; filename="{ascii_safe}"; filename*={rfc5987_encoded}'


def _find_source(run_dir: Path, source_id: str) -> SourceRecord | None:
    """Find a source record by ID in a run directory."""
    sources_path = run_dir / "sources.jsonl"
    if not sources_path.exists():
        return None
    for obj in iter_jsonl(sources_path):
        if obj.get("source_id") == source_id:
            return SourceRecord.model_validate(obj)
    return None


@router.get("", response_model=list[RunSummary])
def api_runs() -> list[RunSummary]:
    """List all procedure runs."""
    return [
        RunSummary(
            run_id=r.run_id,
            created_at_utc=r.created_at_utc,
            updated_at_utc=r.updated_at_utc,
            procedure=r.procedure,
            status=r.status,
            quality_score=r.quality_score,
            iterations_used=r.iterations_used,
            total_cost_usd=r.total_cost_usd,
        )
        for r in list_runs(settings.db_path)
    ]


@router.get("/{run_id}", response_model=RunDetail)
def api_run(run_id: str) -> RunDetail:
    """Get details for a specific run."""
    run = get_run(settings.db_path, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    procedure_md_path = Path(run.run_dir) / "procedure.md"
    procedure_md = procedure_md_path.read_text(encoding="utf-8") if procedure_md_path.exists() else None

    # Check for meta-analysis report
    meta_analysis_path = Path(run.run_dir) / "Procedure_MetaAnalysis.docx"
    has_meta_analysis = meta_analysis_path.exists()

    source_count: int | None = None
    sources_path = Path(run.run_dir) / "sources.jsonl"
    if sources_path.exists():
        with sources_path.open("r", encoding="utf-8") as f:
            source_count = sum(1 for line in f if line.strip())

    warnings: list[str] | None = None
    manifest_path = Path(run.run_dir) / "run_manifest.json"
    if manifest_path.exists():
        try:
            manifest = read_run_manifest(Path(run.run_dir))
            runtime = manifest.get("runtime")
            if isinstance(runtime, dict):
                w = runtime.get("warnings")
                if isinstance(w, list):
                    warnings = [str(x) for x in w]
        except Exception:
            warnings = None

    return RunDetail(
        run_id=run.run_id,
        created_at_utc=run.created_at_utc,
        updated_at_utc=run.updated_at_utc,
        procedure=run.procedure,
        context=run.context,
        status=run.status,
        error=run.error,
        procedure_md=procedure_md,
        source_count=source_count,
        warnings=warnings,
        quality_score=run.quality_score,
        iterations_used=run.iterations_used,
        total_cost_usd=run.total_cost_usd,
        total_input_tokens=run.total_input_tokens,
        total_output_tokens=run.total_output_tokens,
        has_meta_analysis_report=has_meta_analysis,
    )


@router.get("/{run_id}/docx")
def api_docx(run_id: str) -> FileResponse:
    """Download the main procedure document as DOCX."""
    run = get_run(settings.db_path, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    docx = Path(run.run_dir) / "Procedure.docx"
    if not docx.exists():
        raise HTTPException(status_code=404, detail="DOCX not available")

    # Use procedure name for download filename with RFC 5987 encoding
    # This ensures Danish characters (æ, ø, å) work in all browsers
    filename = f"{_sanitize_filename(run.procedure)}.docx"
    content_disposition = _make_content_disposition(filename)

    return FileResponse(
        path=str(docx),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": content_disposition},
    )


@router.get("/{run_id}/docx/meta-analysis")
def api_meta_analysis_docx(run_id: str) -> FileResponse:
    """Download the meta-analysis report document."""
    run = get_run(settings.db_path, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    docx_path = Path(run.run_dir) / "Procedure_MetaAnalysis.docx"
    if not docx_path.exists():
        raise HTTPException(status_code=404, detail="Meta-analysis document not found for this run.")

    # Use procedure name for download filename with RFC 5987 encoding
    filename = f"{_sanitize_filename(run.procedure)}_MetaAnalysis.docx"
    content_disposition = _make_content_disposition(filename)

    return FileResponse(
        path=str(docx_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": content_disposition},
    )


@router.get("/{run_id}/docx/source-analysis")
def api_source_analysis_docx(run_id: str) -> FileResponse:
    """Download the source analysis documentation."""
    run = get_run(settings.db_path, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    docx_path = Path(run.run_dir) / "source_analysis.docx"
    if not docx_path.exists():
        raise HTTPException(status_code=404, detail="Source analysis document not found for this run.")

    filename = f"{_sanitize_filename(run.procedure)}_Kildeanalyse.docx"
    content_disposition = _make_content_disposition(filename)

    return FileResponse(
        path=str(docx_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": content_disposition},
    )


@router.get("/{run_id}/docx/evidence-review")
def api_evidence_review_docx(run_id: str) -> FileResponse:
    """Download the evidence review documentation."""
    run = get_run(settings.db_path, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    docx_path = Path(run.run_dir) / "evidence_review.docx"
    if not docx_path.exists():
        raise HTTPException(status_code=404, detail="Evidence review document not found for this run.")

    filename = f"{_sanitize_filename(run.procedure)}_Evidensgennemgang.docx"
    content_disposition = _make_content_disposition(filename)

    return FileResponse(
        path=str(docx_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": content_disposition},
    )


@router.get("/{run_id}/manifest")
def api_manifest(run_id: str) -> dict[str, Any]:
    """Get the run manifest with metadata and execution details."""
    run = get_run(settings.db_path, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    run_dir = Path(run.run_dir)
    path = run_dir / "run_manifest.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Manifest not available")
    return read_run_manifest(run_dir)


@router.get("/{run_id}/evidence")
def api_evidence(run_id: str) -> dict[str, Any]:
    """Get the evidence report for a run."""
    run = get_run(settings.db_path, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    run_dir = Path(run.run_dir)
    path = run_dir / "evidence_report.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Evidence report not available")
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise HTTPException(status_code=500, detail="Invalid evidence report")
    return obj


@router.post("/{run_id}/verify-evidence")
async def api_verify_evidence(run_id: str) -> dict[str, Any]:
    """
    Verify citations in a run's procedure using LLM.

    This performs semantic verification of each citation to check if the
    cited source actually supports the claim being made.

    Requires Anthropic API key to be configured.
    """
    from procedurewriter.pipeline.evidence_verifier import (
        read_source_content,
        summary_to_dict,
        verify_all_citations,
    )

    # Check for API key
    anthropic_key = _effective_anthropic_api_key()
    if not anthropic_key:
        raise HTTPException(
            status_code=400,
            detail="Anthropic API key required for evidence verification. Configure in Settings.",
        )

    # Get run data
    run = get_run(settings.db_path, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    run_dir = Path(run.run_dir)

    # Read procedure markdown
    procedure_path = run_dir / "procedure.md"
    if not procedure_path.exists():
        raise HTTPException(status_code=404, detail="Procedure not available")
    procedure_md = procedure_path.read_text(encoding="utf-8")

    # Read sources
    sources_path = run_dir / "sources.jsonl"
    if not sources_path.exists():
        raise HTTPException(status_code=404, detail="Sources not available")

    sources: dict[str, str] = {}
    for obj in iter_jsonl(sources_path):
        source_id = obj.get("source_id", "")
        normalized_path = obj.get("normalized_path")
        if source_id and normalized_path:
            content = read_source_content(normalized_path)
            if content:
                sources[source_id] = content

    if not sources:
        return {
            "run_id": run_id,
            "status": "error",
            "message": "No source content available for verification",
        }

    # Run verification
    client = AsyncAnthropic(api_key=anthropic_key)
    try:
        summary, cost = await verify_all_citations(
            procedure_md,
            sources,
            client,
            max_concurrent=5,
            max_verifications=50,
        )
    finally:
        await client.close()

    # Save verification results
    result = summary_to_dict(summary)
    result["run_id"] = run_id
    result["verification_cost_usd"] = round(cost, 4)

    verification_path = run_dir / "evidence_verification.json"
    verification_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    return result


@router.get("/{run_id}/verify-evidence")
def api_get_evidence_verification(run_id: str) -> dict[str, Any]:
    """
    Get cached evidence verification results for a run.

    Returns 404 if verification has not been run yet.
    Use POST to /api/runs/{run_id}/verify-evidence to run verification.
    """
    run = get_run(settings.db_path, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    run_dir = Path(run.run_dir)
    verification_path = run_dir / "evidence_verification.json"

    if not verification_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Evidence verification not available. POST to this endpoint to run verification.",
        )

    obj = json.loads(verification_path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise HTTPException(status_code=500, detail="Invalid verification data")
    return obj


@router.get("/{run_id}/bundle")
def api_bundle(run_id: str) -> FileResponse:
    """Download a complete bundle of all run artifacts as a ZIP file."""
    run = get_run(settings.db_path, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    run_dir = Path(run.run_dir)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="Run dir not found")
    bundle_path = run_dir / "run_bundle.zip"
    build_run_bundle_zip(run_dir, output_path=bundle_path)
    return FileResponse(path=str(bundle_path), filename=f"{run_id}.zip", media_type="application/zip")


@router.get("/{run_id}/sources", response_model=SourcesResponse)
def api_sources(run_id: str) -> SourcesResponse:
    """Get all sources used in a run."""
    run = get_run(settings.db_path, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    sources_path = Path(run.run_dir) / "sources.jsonl"
    if not sources_path.exists():
        return SourcesResponse(run_id=run_id, sources=[])
    sources = [SourceRecord.model_validate(obj) for obj in iter_jsonl(sources_path)]
    return SourcesResponse(run_id=run_id, sources=sources)


@router.get("/{run_id}/sources/scores")
def api_source_scores(run_id: str) -> dict[str, Any]:
    """
    Get composite trust scores for all sources in a run.

    Returns scored sources ranked by composite score (highest first).
    Each score includes evidence level, recency, quality factors, and reasoning.
    """
    run = get_run(settings.db_path, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    scores_path = Path(run.run_dir) / "source_scores.json"
    if not scores_path.exists():
        return {"run_id": run_id, "scores": [], "message": "Scores not available for this run"}
    try:
        scores = json.loads(scores_path.read_text(encoding="utf-8"))
        return {"run_id": run_id, "count": len(scores), "scores": scores}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read scores: {e}") from e


@router.get("/{run_id}/events")
async def api_events(run_id: str) -> StreamingResponse:
    """
    Server-Sent Events stream for pipeline progress.

    Streams real-time events during procedure generation.
    Connect when run status is RUNNING, events stop when complete.
    """
    emitter = get_emitter_if_exists(run_id)
    if emitter is None:
        # Run may not be active yet or already complete
        run = get_run(settings.db_path, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        if run.status == "DONE":
            # Return empty stream with completion event
            async def done_stream():
                yield f'data: {{"event": "complete", "data": {{"success": true, "quality_score": {run.quality_score or 0}}}, "timestamp": 0}}\n\n'
            return StreamingResponse(done_stream(), media_type="text/event-stream")
        if run.status == "FAILED":
            async def error_stream():
                yield f'data: {{"event": "error", "data": {{"stage": "pipeline", "error": "{run.error or "Unknown error"}"}}, "timestamp": 0}}\n\n'
            return StreamingResponse(error_stream(), media_type="text/event-stream")
        # Not started yet - return empty stream
        async def empty_stream():
            yield 'data: {"event": "progress", "data": {"message": "Waiting for pipeline to start"}, "timestamp": 0}\n\n'
        return StreamingResponse(empty_stream(), media_type="text/event-stream")

    # Subscribe to event stream
    queue = emitter.subscribe()

    async def event_stream():
        try:
            while True:
                # Poll the queue with a small timeout to allow cancellation
                try:
                    event = await anyio.to_thread.run_sync(
                        lambda: queue.get(timeout=0.1)
                    )
                except Exception:
                    # Timeout - continue polling
                    continue

                if event is None:
                    # Sentinel - stream ended
                    break

                yield event.to_sse()
        finally:
            emitter.unsubscribe(queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.get("/{run_id}/sources/{source_id}/normalized")
def api_source_normalized(run_id: str, source_id: str) -> FileResponse:
    """Download normalized text content for a specific source."""
    run = get_run(settings.db_path, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    run_dir = Path(run.run_dir)
    src = _find_source(run_dir, source_id)
    if src is None:
        raise HTTPException(status_code=404, detail="Source not found")
    try:
        path = safe_path_within(Path(src.normalized_path), root_dir=run_dir)
    except UnsafePathError as e:
        raise HTTPException(status_code=400, detail="Unsafe source path") from e
    if not path.exists():
        raise HTTPException(status_code=404, detail="Normalized file not found")
    return FileResponse(path=str(path), filename=f"{source_id}.txt", media_type="text/plain")


@router.get("/{run_id}/sources/{source_id}/raw")
def api_source_raw(run_id: str, source_id: str) -> FileResponse:
    """Download raw original file for a specific source."""
    run = get_run(settings.db_path, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    run_dir = Path(run.run_dir)
    src = _find_source(run_dir, source_id)
    if src is None:
        raise HTTPException(status_code=404, detail="Source not found")
    try:
        path = safe_path_within(Path(src.raw_path), root_dir=run_dir)
    except UnsafePathError as e:
        raise HTTPException(status_code=400, detail="Unsafe source path") from e
    if not path.exists():
        raise HTTPException(status_code=404, detail="Raw file not found")
    return FileResponse(path=str(path), filename=path.name, media_type="application/octet-stream")


@router.post("/{run_id}/validate")
async def api_validate_run(run_id: str, protocol_id: str | None = None, use_llm: bool = True) -> dict[str, Any]:
    """
    Validate a run against protocols using LLM semantic comparison.

    If protocol_id is provided, validates against that protocol.
    Otherwise, finds similar protocols automatically.

    Args:
        use_llm: If True (default), uses LLM for semantic comparison. If False, uses legacy pattern matching.
    """
    import anthropic

    run = get_run(settings.db_path, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    run_md_path = Path(run.run_dir) / "procedure.md"
    if not run_md_path.exists():
        raise HTTPException(status_code=400, detail="Run has no procedure output")

    run_markdown = run_md_path.read_text(encoding="utf-8")

    # Check for API key if using LLM
    anthropic_key = _effective_anthropic_api_key()
    if use_llm and not anthropic_key:
        raise HTTPException(
            status_code=400,
            detail="LLM validation requires Anthropic API key. Configure in Settings or set use_llm=false."
        )

    # Find protocols to validate against
    if protocol_id:
        protocol = get_protocol(settings.db_path, protocol_id, load_text=True)
        if not protocol:
            raise HTTPException(status_code=404, detail="Protocol not found")
        protocols_to_check = [(protocol, 1.0)]
    else:
        # Find similar protocols automatically
        similar = find_similar_protocols(settings.db_path, run.procedure, threshold=0.3)
        # Load text for each
        protocols_to_check = [
            (get_protocol(settings.db_path, p.protocol_id, load_text=True), score)
            for p, score in similar[:5]  # Limit to top 5
        ]

    results = []
    total_validation_cost = 0.0

    for protocol, name_similarity in protocols_to_check:
        if not protocol or not protocol.normalized_text:
            continue

        if use_llm and anthropic_key:
            # Use LLM-based semantic validation
            client = anthropic.AsyncAnthropic(api_key=anthropic_key)
            result = await validate_run_against_protocol_llm(
                run_markdown=run_markdown,
                protocol_text=protocol.normalized_text,
                protocol_id=protocol.protocol_id,
                protocol_name=protocol.name,
                anthropic_client=client,
            )
            if result.validation_cost_usd:
                total_validation_cost += result.validation_cost_usd
        else:
            # Fallback to legacy pattern matching
            result = validate_run_against_protocol(
                run_markdown=run_markdown,
                protocol_text=protocol.normalized_text,
                protocol_id=protocol.protocol_id,
                protocol_name=protocol.name,
            )

        validation_id = save_validation_result(settings.db_path, run_id, result)

        results.append({
            "validation_id": validation_id,
            "protocol_id": protocol.protocol_id,
            "protocol_name": protocol.name,
            "name_similarity": name_similarity,
            "content_similarity": result.similarity_score,
            "compatibility_score": result.compatibility_score,
            "summary": result.summary,
            "conflict_count": len(result.conflicts),
            "conflicts": [
                {
                    "section": c.section,
                    "type": c.conflict_type,
                    "severity": c.severity,
                    "explanation": c.explanation,
                    "generated_text": c.generated_text,
                    "approved_text": c.approved_text,
                }
                for c in result.conflicts
            ],
            "validation_cost_usd": result.validation_cost_usd,
        })

    return {
        "run_id": run_id,
        "validations": results,
        "total_validation_cost_usd": total_validation_cost,
    }


@router.get("/{run_id}/validations")
def api_get_validations(run_id: str) -> dict[str, Any]:
    """Get validation results for a run."""
    run = get_run(settings.db_path, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    results = get_validation_results(settings.db_path, run_id)
    return {"run_id": run_id, "validations": results}


@router.get("/{run_id}/version-chain")
def api_version_chain(run_id: str) -> dict[str, Any]:
    """Get the complete version chain for a run."""
    chain = get_version_chain(settings.db_path, run_id)
    if not chain:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "run_id": run_id,
        "chain_length": len(chain),
        "chain": [
            {
                "run_id": v.run_id,
                "version_number": v.version_number,
                "created_at_utc": v.created_at_utc,
                "parent_run_id": v.parent_run_id,
                "version_note": v.version_note,
                "quality_score": v.quality_score,
            }
            for v in chain
        ],
    }


@router.get("/{run_id}/diff/{other_run_id}")
def api_diff_runs(run_id: str, other_run_id: str) -> dict[str, Any]:
    """Generate a diff between two runs.

    Compares `other_run_id` (older) to `run_id` (newer).
    """
    run = get_run(settings.db_path, run_id)
    other_run = get_run(settings.db_path, other_run_id)

    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    if other_run is None:
        raise HTTPException(status_code=404, detail=f"Run {other_run_id} not found")

    # Load markdown content
    run_dir = Path(run.run_dir)
    other_run_dir = Path(other_run.run_dir)

    run_md = load_procedure_markdown(run_dir)
    other_md = load_procedure_markdown(other_run_dir)

    if run_md is None:
        raise HTTPException(status_code=404, detail=f"Procedure markdown not found for {run_id}")
    if other_md is None:
        raise HTTPException(status_code=404, detail=f"Procedure markdown not found for {other_run_id}")

    # Load source IDs
    run_sources = load_source_ids(run_dir)
    other_sources = load_source_ids(other_run_dir)

    # Create diff (other is old, run is new)
    diff = create_version_diff(
        old_run_id=other_run_id,
        new_run_id=run_id,
        old_version=other_run.version_number,
        new_version=run.version_number,
        procedure=run.procedure,
        old_markdown=other_md,
        new_markdown=run_md,
        old_source_ids=other_sources,
        new_source_ids=run_sources,
    )

    return diff_to_dict(diff)
