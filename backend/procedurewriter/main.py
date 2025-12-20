from __future__ import annotations

import asyncio
import json
import os
import uuid
from functools import partial
from pathlib import Path
from typing import Any

import anyio
from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from procedurewriter import config_store
from procedurewriter.db import (
    add_library_source,
    create_run,
    create_style_profile,
    delete_secret,
    delete_style_profile,
    get_default_style_profile,
    get_run,
    get_secret,
    get_style_profile,
    get_version_chain,
    init_db,
    iter_jsonl,
    list_library_sources,
    list_procedure_versions,
    list_runs,
    list_style_profiles,
    list_unique_procedures,
    mask_secret,
    set_default_style_profile,
    set_secret,
    update_run_status,
    update_style_profile,
)
from procedurewriter.file_utils import UnsafePathError, safe_path_within
from procedurewriter.ncbi_status import check_ncbi_status
from procedurewriter.pipeline.events import get_emitter_if_exists
from procedurewriter.pipeline.hashing import sha256_bytes, sha256_text
from procedurewriter.pipeline.io import write_bytes, write_json, write_text
from procedurewriter.pipeline.normalize import (
    extract_docx_blocks,
    extract_pdf_pages,
    normalize_docx_blocks,
    normalize_html,
    normalize_pdf_pages,
)
from procedurewriter.pipeline.run import run_pipeline
from procedurewriter.pipeline.versioning import (
    create_version_diff,
    diff_to_dict,
    load_procedure_markdown,
    load_source_ids,
)
from procedurewriter.protocols import (
    delete_protocol,
    find_similar_protocols,
    get_protocol,
    get_validation_results,
    list_protocols,
    save_validation_result,
    update_protocol,
    upload_protocol,
    validate_run_against_protocol,
    validate_run_against_protocol_llm,
)
from procedurewriter.run_bundle import build_run_bundle_zip, read_run_manifest
from procedurewriter.schemas import (
    ApiKeyInfo,
    ApiKeySetRequest,
    ApiKeyStatus,
    AppStatus,
    ConfigText,
    CostSummaryResponse,
    IngestResponse,
    IngestUrlRequest,
    RunDetail,
    RunSummary,
    SourceRecord,
    SourcesResponse,
    WriteRequest,
    WriteResponse,
)
from procedurewriter.settings import Settings
from procedurewriter.templates import (
    SectionConfig,
    TemplateConfig,
    create_template,
    delete_template,
    get_template,
    list_templates,
    set_default_template,
    update_template,
)
from procedurewriter.models.style_profile import StyleProfile

settings = Settings()
app = FastAPI(title="Akut procedure writer", version="0.1.0")

_OPENAI_SECRET_NAME = "openai_api_key"
_ANTHROPIC_SECRET_NAME = "anthropic_api_key"
_NCBI_SECRET_NAME = "ncbi_api_key"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include meta-analysis router
from procedurewriter.api.meta_analysis import router as meta_analysis_router

app.include_router(meta_analysis_router)


@app.on_event("startup")
def _startup() -> None:
    settings.runs_dir.mkdir(parents=True, exist_ok=True)
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    (settings.resolved_data_dir / "index").mkdir(parents=True, exist_ok=True)
    init_db(settings.db_path)


@app.get("/api/status", response_model=AppStatus)
def api_status() -> AppStatus:
    key_db = get_secret(settings.db_path, name=_OPENAI_SECRET_NAME)
    key_env = os.getenv("OPENAI_API_KEY")
    if key_db:
        key_source = "db"
    elif key_env:
        key_source = "env"
    else:
        key_source = "none"

    ncbi_db = get_secret(settings.db_path, name=_NCBI_SECRET_NAME)
    ncbi_env = settings.ncbi_api_key
    if ncbi_db:
        ncbi_source = "db"
    elif ncbi_env:
        ncbi_source = "env"
    else:
        ncbi_source = "none"

    base_url = os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1"

    anthropic_db = get_secret(settings.db_path, name=_ANTHROPIC_SECRET_NAME)
    anthropic_env = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_db:
        anthropic_source = "db"
    elif anthropic_env:
        anthropic_source = "env"
    else:
        anthropic_source = "none"

    return AppStatus(
        version=str(app.version),
        dummy_mode=settings.dummy_mode,
        use_llm=settings.use_llm,
        llm_provider=settings.llm_provider.value,
        llm_model=settings.llm_model,
        openai_embeddings_model=settings.openai_embeddings_model,
        openai_base_url=base_url,
        openai_key_present=bool(_effective_openai_api_key()),
        openai_key_source=key_source,
        anthropic_key_present=bool(_effective_anthropic_api_key()),
        anthropic_key_source=anthropic_source,
        ollama_base_url=settings.ollama_base_url,
        ncbi_api_key_present=bool(_effective_ncbi_api_key()),
        ncbi_api_key_source=ncbi_source,
        ncbi_tool=settings.ncbi_tool,
        ncbi_email=settings.ncbi_email,
    )


@app.post("/api/write", response_model=WriteResponse)
async def api_write(req: WriteRequest) -> WriteResponse:
    run_id = uuid.uuid4().hex
    run_dir = settings.runs_dir / run_id
    create_run(
        settings.db_path,
        run_id=run_id,
        procedure=req.procedure,
        context=req.context,
        run_dir=run_dir,
        template_id=req.template_id,
    )
    asyncio.create_task(_run_background(run_id))
    return WriteResponse(run_id=run_id)


async def _run_background(run_id: str) -> None:
    run = get_run(settings.db_path, run_id)
    if run is None:
        return
    update_run_status(settings.db_path, run_id=run_id, status="RUNNING")
    try:
        libs = list_library_sources(settings.db_path)
        openai_api_key = _effective_openai_api_key()
        anthropic_api_key = _effective_anthropic_api_key()
        ncbi_api_key = _effective_ncbi_api_key()
        job = partial(
            run_pipeline,
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
    except Exception as e:  # noqa: BLE001
        update_run_status(settings.db_path, run_id=run_id, status="FAILED", error=str(e))


@app.get("/api/runs", response_model=list[RunSummary])
def api_runs() -> list[RunSummary]:
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


@app.get("/api/costs", response_model=CostSummaryResponse)
def api_costs() -> CostSummaryResponse:
    """Get aggregated cost summary across all runs."""
    runs = list_runs(settings.db_path)
    total_cost = 0.0
    total_input = 0
    total_output = 0
    runs_with_cost = 0

    for r in runs:
        if r.total_cost_usd is not None:
            total_cost += r.total_cost_usd
            runs_with_cost += 1
        if r.total_input_tokens is not None:
            total_input += r.total_input_tokens
        if r.total_output_tokens is not None:
            total_output += r.total_output_tokens

    avg_cost = total_cost / runs_with_cost if runs_with_cost > 0 else None

    return CostSummaryResponse(
        total_runs=len(runs),
        total_cost_usd=round(total_cost, 6),
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        total_tokens=total_input + total_output,
        avg_cost_per_run=round(avg_cost, 6) if avg_cost is not None else None,
    )


@app.get("/api/runs/{run_id}", response_model=RunDetail)
def api_run(run_id: str) -> RunDetail:
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


def _sanitize_filename(name: str) -> str:
    """Sanitize a string for use as a filename.

    Preserves Danish characters (æ, ø, å) for display purposes.
    For HTTP headers, use _encode_filename_rfc5987() instead.
    """
    import re
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
    from urllib.parse import quote

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
    import re

    # Create ASCII-safe fallback (replace non-ASCII with underscore)
    ascii_safe = re.sub(r'[^\x00-\x7F]', '_', filename)

    # RFC 5987 encoded version with full Unicode support
    rfc5987_encoded = _encode_filename_rfc5987(filename)

    # Return both: filename for legacy, filename* for modern browsers
    return f'attachment; filename="{ascii_safe}"; filename*={rfc5987_encoded}'


@app.get("/api/runs/{run_id}/docx")
def api_docx(run_id: str) -> FileResponse:
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


@app.get("/api/runs/{run_id}/docx/meta-analysis")
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


@app.get("/api/runs/{run_id}/docx/source-analysis")
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


@app.get("/api/runs/{run_id}/docx/evidence-review")
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


@app.get("/api/runs/{run_id}/manifest")
def api_manifest(run_id: str) -> dict[str, Any]:
    run = get_run(settings.db_path, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    run_dir = Path(run.run_dir)
    path = run_dir / "run_manifest.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Manifest not available")
    return read_run_manifest(run_dir)


@app.get("/api/runs/{run_id}/evidence")
def api_evidence(run_id: str) -> dict[str, Any]:
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


@app.post("/api/runs/{run_id}/verify-evidence")
async def api_verify_evidence(run_id: str) -> dict[str, Any]:
    """
    Verify citations in a run's procedure using LLM.

    This performs semantic verification of each citation to check if the
    cited source actually supports the claim being made.

    Requires Anthropic API key to be configured.
    """
    from anthropic import AsyncAnthropic

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


@app.get("/api/runs/{run_id}/verify-evidence")
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


@app.get("/api/runs/{run_id}/bundle")
def api_bundle(run_id: str) -> FileResponse:
    run = get_run(settings.db_path, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    run_dir = Path(run.run_dir)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="Run dir not found")
    bundle_path = run_dir / "run_bundle.zip"
    build_run_bundle_zip(run_dir, output_path=bundle_path)
    return FileResponse(path=str(bundle_path), filename=f"{run_id}.zip", media_type="application/zip")


@app.get("/api/runs/{run_id}/sources", response_model=SourcesResponse)
def api_sources(run_id: str) -> SourcesResponse:
    run = get_run(settings.db_path, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    sources_path = Path(run.run_dir) / "sources.jsonl"
    if not sources_path.exists():
        return SourcesResponse(run_id=run_id, sources=[])
    sources = [SourceRecord.model_validate(obj) for obj in iter_jsonl(sources_path)]
    return SourcesResponse(run_id=run_id, sources=sources)


@app.get("/api/runs/{run_id}/sources/scores")
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


@app.get("/api/runs/{run_id}/events")
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


def _find_source(run_dir: Path, source_id: str) -> SourceRecord | None:
    sources_path = run_dir / "sources.jsonl"
    if not sources_path.exists():
        return None
    for obj in iter_jsonl(sources_path):
        if obj.get("source_id") == source_id:
            return SourceRecord.model_validate(obj)
    return None


@app.get("/api/runs/{run_id}/sources/{source_id}/normalized")
def api_source_normalized(run_id: str, source_id: str) -> FileResponse:
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


@app.get("/api/runs/{run_id}/sources/{source_id}/raw")
def api_source_raw(run_id: str, source_id: str) -> FileResponse:
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


def _effective_openai_api_key() -> str | None:
    return get_secret(settings.db_path, name=_OPENAI_SECRET_NAME) or os.getenv("OPENAI_API_KEY")

def _effective_ncbi_api_key() -> str | None:
    return get_secret(settings.db_path, name=_NCBI_SECRET_NAME) or settings.ncbi_api_key


def _effective_anthropic_api_key() -> str | None:
    return get_secret(settings.db_path, name=_ANTHROPIC_SECRET_NAME) or os.getenv("ANTHROPIC_API_KEY")


@app.get("/api/keys/openai", response_model=ApiKeyInfo)
def api_get_openai_key() -> ApiKeyInfo:
    key = _effective_openai_api_key()
    if not key:
        return ApiKeyInfo(present=False, masked=None)
    return ApiKeyInfo(present=True, masked=mask_secret(key))


@app.put("/api/keys/openai", response_model=ApiKeyInfo)
def api_set_openai_key(req: ApiKeySetRequest) -> ApiKeyInfo:
    set_secret(settings.db_path, name=_OPENAI_SECRET_NAME, value=req.api_key.strip())
    return api_get_openai_key()


@app.delete("/api/keys/openai", response_model=ApiKeyInfo)
def api_delete_openai_key() -> ApiKeyInfo:
    delete_secret(settings.db_path, name=_OPENAI_SECRET_NAME)
    return api_get_openai_key()


@app.get("/api/keys/openai/status", response_model=ApiKeyStatus)
def api_openai_status() -> ApiKeyStatus:
    key = _effective_openai_api_key()
    if not key:
        return ApiKeyStatus(present=False, ok=False, message="No OpenAI API key configured.")
    try:
        from openai import OpenAI

        client = OpenAI(api_key=key, timeout=10.0, max_retries=0)
        _ = client.models.list()
        return ApiKeyStatus(present=True, ok=True, message="OK")
    except Exception as e:  # noqa: BLE001
        return ApiKeyStatus(present=True, ok=False, message=str(e))


@app.get("/api/keys/ncbi", response_model=ApiKeyInfo)
def api_get_ncbi_key() -> ApiKeyInfo:
    key = _effective_ncbi_api_key()
    if not key:
        return ApiKeyInfo(present=False, masked=None)
    return ApiKeyInfo(present=True, masked=mask_secret(key))


@app.put("/api/keys/ncbi", response_model=ApiKeyInfo)
def api_set_ncbi_key(req: ApiKeySetRequest) -> ApiKeyInfo:
    set_secret(settings.db_path, name=_NCBI_SECRET_NAME, value=req.api_key.strip())
    return api_get_ncbi_key()


@app.delete("/api/keys/ncbi", response_model=ApiKeyInfo)
def api_delete_ncbi_key() -> ApiKeyInfo:
    delete_secret(settings.db_path, name=_NCBI_SECRET_NAME)
    return api_get_ncbi_key()


@app.get("/api/keys/ncbi/status", response_model=ApiKeyStatus)
def api_ncbi_status() -> ApiKeyStatus:
    key = _effective_ncbi_api_key()
    present = bool(key)
    from procedurewriter.pipeline.fetcher import CachedHttpClient

    http = CachedHttpClient(cache_dir=settings.cache_dir, timeout_s=10.0, max_retries=1, backoff_s=0.6)
    try:
        ok, message = check_ncbi_status(http=http, tool=settings.ncbi_tool, email=settings.ncbi_email, api_key=key)
        return ApiKeyStatus(present=present, ok=ok, message=message)
    except Exception as e:  # noqa: BLE001
        return ApiKeyStatus(present=present, ok=False, message=str(e))
    finally:
        http.close()


@app.get("/api/keys/anthropic", response_model=ApiKeyInfo)
def api_get_anthropic_key() -> ApiKeyInfo:
    key = _effective_anthropic_api_key()
    if not key:
        return ApiKeyInfo(present=False, masked=None)
    return ApiKeyInfo(present=True, masked=mask_secret(key))


@app.put("/api/keys/anthropic", response_model=ApiKeyInfo)
def api_set_anthropic_key(req: ApiKeySetRequest) -> ApiKeyInfo:
    set_secret(settings.db_path, name=_ANTHROPIC_SECRET_NAME, value=req.api_key.strip())
    return api_get_anthropic_key()


@app.delete("/api/keys/anthropic", response_model=ApiKeyInfo)
def api_delete_anthropic_key() -> ApiKeyInfo:
    delete_secret(settings.db_path, name=_ANTHROPIC_SECRET_NAME)
    return api_get_anthropic_key()


@app.get("/api/keys/anthropic/status", response_model=ApiKeyStatus)
def api_anthropic_status() -> ApiKeyStatus:
    key = _effective_anthropic_api_key()
    if not key:
        return ApiKeyStatus(present=False, ok=False, message="No Anthropic API key configured.")
    try:
        from anthropic import Anthropic
        Anthropic(api_key=key)  # Validate key format by instantiating
        return ApiKeyStatus(present=True, ok=True, message="OK (key format valid)")
    except ImportError:
        return ApiKeyStatus(present=True, ok=False, message="anthropic package not installed")
    except Exception as e:  # noqa: BLE001
        return ApiKeyStatus(present=True, ok=False, message=str(e))


@app.post("/api/ingest/pdf", response_model=IngestResponse)
async def api_ingest_pdf(file: UploadFile) -> IngestResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")
    source_id = f"LIB_{uuid.uuid4().hex}"
    raw_path = settings.uploads_dir / f"{source_id}.pdf"
    raw_bytes = await file.read()
    write_bytes(raw_path, raw_bytes)

    pages = extract_pdf_pages(raw_path)
    normalized_text = normalize_pdf_pages(pages)
    normalized_path = settings.uploads_dir / f"{source_id}.txt"
    write_text(normalized_path, normalized_text)

    pages_json_path = settings.uploads_dir / f"{source_id}_pages.json"
    write_json(pages_json_path, [{"page": i + 1, "text": t} for i, t in enumerate(pages)])

    add_library_source(
        settings.db_path,
        source_id=source_id,
        kind="pdf",
        url=None,
        title=file.filename,
        raw_path=raw_path,
        normalized_path=normalized_path,
        raw_sha256=sha256_bytes(raw_bytes),
        normalized_sha256=sha256_text(normalized_text),
        meta={
            "filename": file.filename,
            "pages_json": str(pages_json_path),
            "extraction_notes": "PDF upload.",
            "terms_licence_note": "Bruger-upload. Tjek rettigheder/fortrolighed.",
        },
    )
    return IngestResponse(source_id=source_id)


@app.post("/api/ingest/docx", response_model=IngestResponse)
async def api_ingest_docx(file: UploadFile) -> IngestResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")
    source_id = f"LIB_{uuid.uuid4().hex}"
    raw_path = settings.uploads_dir / f"{source_id}.docx"
    raw_bytes = await file.read()
    write_bytes(raw_path, raw_bytes)

    blocks = extract_docx_blocks(raw_path)
    normalized_text = normalize_docx_blocks(blocks)
    normalized_path = settings.uploads_dir / f"{source_id}.txt"
    write_text(normalized_path, normalized_text)

    blocks_json_path = settings.uploads_dir / f"{source_id}_blocks.json"
    write_json(blocks_json_path, blocks)

    add_library_source(
        settings.db_path,
        source_id=source_id,
        kind="docx",
        url=None,
        title=file.filename,
        raw_path=raw_path,
        normalized_path=normalized_path,
        raw_sha256=sha256_bytes(raw_bytes),
        normalized_sha256=sha256_text(normalized_text),
        meta={
            "filename": file.filename,
            "blocks_json": str(blocks_json_path),
            "extraction_notes": "DOCX upload.",
            "terms_licence_note": "Local upload.",
        },
    )
    return IngestResponse(source_id=source_id)


@app.post("/api/ingest/url", response_model=IngestResponse)
async def api_ingest_url(req: IngestUrlRequest) -> IngestResponse:
    allowlist = config_store.load_yaml(settings.allowlist_path)
    prefixes = allowlist.get("allowed_url_prefixes", []) if isinstance(allowlist, dict) else []
    if not any(req.url.startswith(str(p)) for p in prefixes):
        raise HTTPException(status_code=400, detail="URL not allowed by allowlist")

    source_id = f"LIB_{uuid.uuid4().hex}"
    from procedurewriter.pipeline.fetcher import CachedHttpClient

    http = CachedHttpClient(cache_dir=settings.cache_dir)
    try:
        resp = http.get(req.url)
    finally:
        http.close()

    raw_path = settings.uploads_dir / f"{source_id}.html"
    write_bytes(raw_path, resp.content)
    normalized_text = normalize_html(resp.content)
    normalized_path = settings.uploads_dir / f"{source_id}.txt"
    write_text(normalized_path, normalized_text)

    add_library_source(
        settings.db_path,
        source_id=source_id,
        kind="url",
        url=req.url,
        title=None,
        raw_path=raw_path,
        normalized_path=normalized_path,
        raw_sha256=sha256_bytes(resp.content),
        normalized_sha256=sha256_text(normalized_text),
        meta={
            "final_url": resp.url,
            "fetched_at_utc": resp.fetched_at_utc,
            "cache_path": resp.cache_path,
            "extraction_notes": "URL ingest.",
            "terms_licence_note": "Respektér source terms/licence. Ingen paywall scraping.",
        },
    )
    return IngestResponse(source_id=source_id)


@app.get("/api/config/author_guide", response_model=ConfigText)
def api_get_author_guide() -> ConfigText:
    return ConfigText(text=config_store.read_text(settings.author_guide_path))


@app.put("/api/config/author_guide", response_model=ConfigText)
def api_set_author_guide(cfg: ConfigText) -> ConfigText:
    config_store.write_text_validated_yaml(settings.author_guide_path, cfg.text)
    return cfg


@app.get("/api/config/source_allowlist", response_model=ConfigText)
def api_get_allowlist() -> ConfigText:
    return ConfigText(text=config_store.read_text(settings.allowlist_path))


@app.put("/api/config/source_allowlist", response_model=ConfigText)
def api_set_allowlist(cfg: ConfigText) -> ConfigText:
    config_store.write_text_validated_yaml(settings.allowlist_path, cfg.text)
    return cfg


@app.get("/api/config/docx_template", response_model=ConfigText)
def api_get_docx_template() -> ConfigText:
    """Get the DOCX template configuration."""
    return ConfigText(text=config_store.read_text(settings.docx_template_path))


@app.put("/api/config/docx_template", response_model=ConfigText)
def api_set_docx_template(cfg: ConfigText) -> ConfigText:
    """Update the DOCX template configuration."""
    config_store.write_text_validated_yaml(settings.docx_template_path, cfg.text)
    return cfg


@app.get("/api/library/stats")
def api_library_stats() -> dict[str, Any]:
    """Get statistics about the Danish guideline library."""
    from procedurewriter.pipeline.library_search import LibrarySearchProvider

    provider = LibrarySearchProvider(settings.resolved_guideline_library_path)
    if not provider.available():
        return {
            "available": False,
            "document_count": 0,
            "source_stats": {},
            "library_path": str(settings.resolved_guideline_library_path),
        }

    return {
        "available": True,
        "document_count": provider.get_document_count(),
        "source_stats": provider.get_source_stats(),
        "library_path": str(settings.resolved_guideline_library_path),
    }


@app.get("/api/library/search")
def api_library_search(q: str, limit: int = 20) -> dict[str, Any]:
    """Search the Danish guideline library."""
    from procedurewriter.pipeline.library_search import LibrarySearchProvider

    provider = LibrarySearchProvider(settings.resolved_guideline_library_path)
    if not provider.available():
        raise HTTPException(status_code=503, detail="Guideline library not available")

    results = provider.search(q, limit=limit)
    return {
        "query": q,
        "count": len(results),
        "results": [
            {
                "doc_id": r.doc_id,
                "source_id": r.source_id,
                "source_name": r.source_name,
                "title": r.title,
                "url": r.url,
                "publish_year": r.publish_year,
                "category": r.category,
                "relevance_score": r.relevance_score,
            }
            for r in results
        ],
    }


# --- Template API Endpoints ---


@app.get("/api/templates")
def api_list_templates() -> dict[str, Any]:
    """List all available templates."""
    templates = list_templates(settings.db_path)
    return {
        "templates": [
            {
                "template_id": t.template_id,
                "name": t.name,
                "description": t.description,
                "is_default": t.is_default,
                "is_system": t.is_system,
                "section_count": len(t.config.sections),
            }
            for t in templates
        ]
    }


@app.get("/api/templates/{template_id}")
def api_get_template(template_id: str) -> dict[str, Any]:
    """Get a specific template with full config."""
    template = get_template(settings.db_path, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return {
        "template_id": template.template_id,
        "name": template.name,
        "description": template.description,
        "is_default": template.is_default,
        "is_system": template.is_system,
        "created_at_utc": template.created_at_utc,
        "updated_at_utc": template.updated_at_utc,
        "config": {
            "title_prefix": template.config.title_prefix,
            "sections": [
                {"heading": s.heading, "format": s.format, "bundle": s.bundle}
                for s in template.config.sections
            ],
        },
    }


class CreateTemplateRequest(BaseModel):
    name: str
    description: str | None = None
    config: dict[str, Any]


@app.post("/api/templates")
def api_create_template(request: CreateTemplateRequest) -> dict[str, Any]:
    """Create a new template."""
    config = TemplateConfig(
        title_prefix=request.config.get("title_prefix", "Procedure"),
        sections=[
            SectionConfig(
                heading=s["heading"],
                format=s.get("format", "bullets"),
                bundle=s.get("bundle", "action"),
            )
            for s in request.config.get("sections", [])
        ],
    )

    if not config.sections:
        raise HTTPException(status_code=400, detail="Template must have at least one section")

    template_id = create_template(
        settings.db_path,
        name=request.name,
        description=request.description,
        config=config,
    )

    return {"template_id": template_id}


class UpdateTemplateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    config: dict[str, Any] | None = None


@app.put("/api/templates/{template_id}")
def api_update_template(template_id: str, request: UpdateTemplateRequest) -> dict[str, Any]:
    """Update a template."""
    config = None
    if request.config:
        config = TemplateConfig(
            title_prefix=request.config.get("title_prefix", "Procedure"),
            sections=[
                SectionConfig(
                    heading=s["heading"],
                    format=s.get("format", "bullets"),
                    bundle=s.get("bundle", "action"),
                )
                for s in request.config.get("sections", [])
            ],
        )

    try:
        success = update_template(
            settings.db_path,
            template_id,
            name=request.name,
            description=request.description,
            config=config,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if not success:
        raise HTTPException(status_code=404, detail="Template not found")

    return {"status": "updated"}


@app.delete("/api/templates/{template_id}")
def api_delete_template(template_id: str) -> dict[str, Any]:
    """Delete a template."""
    try:
        success = delete_template(settings.db_path, template_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if not success:
        raise HTTPException(status_code=404, detail="Template not found")

    return {"status": "deleted"}


@app.post("/api/templates/{template_id}/set-default")
def api_set_default_template(template_id: str) -> dict[str, Any]:
    """Set a template as the default."""
    success = set_default_template(settings.db_path, template_id)
    if not success:
        raise HTTPException(status_code=404, detail="Template not found")

    return {"status": "default_set"}


# --- Protocol API Endpoints ---


@app.get("/api/protocols")
def api_list_protocols(status: str = "active") -> dict[str, Any]:
    """List all protocols, optionally filtered by status."""
    protocols = list_protocols(settings.db_path, status if status != "all" else None)
    return {
        "protocols": [
            {
                "protocol_id": p.protocol_id,
                "name": p.name,
                "description": p.description,
                "status": p.status,
                "version": p.version,
                "approved_by": p.approved_by,
                "created_at_utc": p.created_at_utc,
            }
            for p in protocols
        ]
    }


@app.get("/api/protocols/search")
def api_search_protocols(q: str, threshold: float = 0.5) -> dict[str, Any]:
    """Search for protocols similar to a query."""
    results = find_similar_protocols(settings.db_path, q, threshold)
    return {
        "query": q,
        "results": [
            {
                "protocol_id": p.protocol_id,
                "name": p.name,
                "similarity": score,
            }
            for p, score in results
        ],
    }


@app.get("/api/protocols/{protocol_id}")
def api_get_protocol(protocol_id: str) -> dict[str, Any]:
    """Get a specific protocol."""
    protocol = get_protocol(settings.db_path, protocol_id, load_text=True)
    if not protocol:
        raise HTTPException(status_code=404, detail="Protocol not found")

    return {
        "protocol_id": protocol.protocol_id,
        "name": protocol.name,
        "description": protocol.description,
        "status": protocol.status,
        "version": protocol.version,
        "approved_by": protocol.approved_by,
        "approved_at_utc": protocol.approved_at_utc,
        "created_at_utc": protocol.created_at_utc,
        "has_text": protocol.normalized_text is not None,
    }


@app.post("/api/protocols/upload")
async def api_upload_protocol(
    file: UploadFile,
    name: str = Form(...),
    description: str = Form(None),
    version: str = Form(None),
    approved_by: str = Form(None),
) -> dict[str, Any]:
    """Upload a new protocol file (PDF, DOCX, or TXT)."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".pdf", ".docx", ".doc", ".txt"):
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")

    # Save uploaded file temporarily
    upload_dir = settings.uploads_dir
    upload_dir.mkdir(parents=True, exist_ok=True)
    temp_path = upload_dir / f"temp_{uuid.uuid4().hex}{suffix}"

    try:
        content = await file.read()
        temp_path.write_bytes(content)

        protocol_id = upload_protocol(
            settings.db_path,
            temp_path,
            name=name,
            description=description,
            version=version,
            approved_by=approved_by,
            storage_dir=Path("data/protocols"),
        )
    finally:
        temp_path.unlink(missing_ok=True)

    return {"protocol_id": protocol_id}


class UpdateProtocolRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None
    version: str | None = None
    approved_by: str | None = None


@app.put("/api/protocols/{protocol_id}")
def api_update_protocol(protocol_id: str, request: UpdateProtocolRequest) -> dict[str, Any]:
    """Update protocol metadata."""
    success = update_protocol(
        settings.db_path,
        protocol_id,
        name=request.name,
        description=request.description,
        status=request.status,
        version=request.version,
        approved_by=request.approved_by,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Protocol not found")

    return {"status": "updated"}


@app.delete("/api/protocols/{protocol_id}")
def api_delete_protocol(protocol_id: str) -> dict[str, Any]:
    """Delete a protocol."""
    success = delete_protocol(settings.db_path, protocol_id)
    if not success:
        raise HTTPException(status_code=404, detail="Protocol not found")

    return {"status": "deleted"}


# --- Validation API Endpoints ---


@app.post("/api/runs/{run_id}/validate")
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


@app.get("/api/runs/{run_id}/validations")
def api_get_validations(run_id: str) -> dict[str, Any]:
    """Get validation results for a run."""
    run = get_run(settings.db_path, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    results = get_validation_results(settings.db_path, run_id)
    return {"run_id": run_id, "validations": results}


# --- Versioning API Endpoints ---


@app.get("/api/procedures")
def api_list_procedures() -> dict[str, Any]:
    """List all unique procedures with completed runs."""
    procedures = list_unique_procedures(settings.db_path)
    return {"procedures": procedures, "count": len(procedures)}


@app.get("/api/procedures/{procedure}/versions")
def api_procedure_versions(procedure: str) -> dict[str, Any]:
    """List all versions of a procedure."""
    versions = list_procedure_versions(settings.db_path, procedure)
    return {
        "procedure": procedure,
        "count": len(versions),
        "versions": [
            {
                "run_id": v.run_id,
                "version_number": v.version_number,
                "created_at_utc": v.created_at_utc,
                "parent_run_id": v.parent_run_id,
                "version_note": v.version_note,
                "quality_score": v.quality_score,
                "status": v.status,
            }
            for v in versions
        ],
    }


@app.get("/api/runs/{run_id}/version-chain")
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


@app.get("/api/runs/{run_id}/diff/{other_run_id}")
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


# ─────────────────────────────────────────────────────────────────────────────
# Style Profile Endpoints
# ─────────────────────────────────────────────────────────────────────────────


class CreateStyleRequest(BaseModel):
    """Request body for creating a style profile."""

    name: str
    description: str | None = None
    tone_description: str = ""
    target_audience: str = ""
    detail_level: str = "moderate"
    section_order: list[str] = []
    include_clinical_pearls: bool = False
    include_evidence_badges: bool = True
    heading_style: str = "numbered"
    list_style: str = "bullets"
    citation_style: str = "superscript"
    color_scheme: str = "professional_blue"
    safety_box_style: str = "yellow_background"
    original_prompt: str | None = None


class UpdateStyleRequest(BaseModel):
    """Request body for updating a style profile."""

    name: str | None = None
    description: str | None = None
    tone_description: str | None = None
    target_audience: str | None = None
    detail_level: str | None = None
    section_order: list[str] | None = None
    include_clinical_pearls: bool | None = None
    include_evidence_badges: bool | None = None
    heading_style: str | None = None
    list_style: str | None = None
    citation_style: str | None = None
    color_scheme: str | None = None
    safety_box_style: str | None = None
    original_prompt: str | None = None


@app.get("/api/styles")
def api_list_styles() -> list[dict[str, Any]]:
    """List all style profiles."""
    profiles = list_style_profiles(settings.db_path)
    return [StyleProfile.from_db_dict(p).to_db_dict() for p in profiles]


@app.get("/api/styles/default")
def api_get_default_style() -> dict[str, Any]:
    """Get the default style profile."""
    profile = get_default_style_profile(settings.db_path)
    if profile is None:
        raise HTTPException(status_code=404, detail="No default style profile set")
    return StyleProfile.from_db_dict(profile).to_db_dict()


@app.get("/api/styles/{style_id}")
def api_get_style(style_id: str) -> dict[str, Any]:
    """Get a specific style profile."""
    profile = get_style_profile(settings.db_path, style_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Style profile {style_id} not found")
    return StyleProfile.from_db_dict(profile).to_db_dict()


@app.post("/api/styles")
def api_create_style(request: CreateStyleRequest) -> dict[str, Any]:
    """Create a new style profile."""
    # Construct config dicts from flat fields
    tone_config = {
        "tone_description": request.tone_description,
        "target_audience": request.target_audience,
        "detail_level": request.detail_level,
    }
    structure_config = {
        "section_order": request.section_order,
        "include_clinical_pearls": request.include_clinical_pearls,
        "include_evidence_badges": request.include_evidence_badges,
    }
    formatting_config = {
        "heading_style": request.heading_style,
        "list_style": request.list_style,
        "citation_style": request.citation_style,
    }
    visual_config = {
        "color_scheme": request.color_scheme,
        "safety_box_style": request.safety_box_style,
    }
    
    profile_id = create_style_profile(
        settings.db_path,
        name=request.name,
        description=request.description,
        tone_config=tone_config,
        structure_config=structure_config,
        formatting_config=formatting_config,
        visual_config=visual_config,
        original_prompt=request.original_prompt,
    )
    profile = get_style_profile(settings.db_path, profile_id)
    return StyleProfile.from_db_dict(profile).to_db_dict()


@app.put("/api/styles/{style_id}")
def api_update_style(style_id: str, request: UpdateStyleRequest) -> dict[str, Any]:
    """Update a style profile."""
    # Get existing profile
    existing = get_style_profile(settings.db_path, style_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Style profile {style_id} not found")
    
    # Build updates dict
    updates: dict[str, Any] = {}
    
    # Direct fields
    if request.name is not None:
        updates["name"] = request.name
    if request.description is not None:
        updates["description"] = request.description
    if request.original_prompt is not None:
        updates["original_prompt"] = request.original_prompt
    
    # Tone config updates
    tone_updates = {}
    if request.tone_description is not None:
        tone_updates["tone_description"] = request.tone_description
    if request.target_audience is not None:
        tone_updates["target_audience"] = request.target_audience
    if request.detail_level is not None:
        tone_updates["detail_level"] = request.detail_level
    if tone_updates:
        existing_tone = existing.get("tone_config", {})
        if isinstance(existing_tone, str):
            import json
            existing_tone = json.loads(existing_tone)
        updates["tone_config"] = {**existing_tone, **tone_updates}
    
    # Structure config updates
    structure_updates = {}
    if request.section_order is not None:
        structure_updates["section_order"] = request.section_order
    if request.include_clinical_pearls is not None:
        structure_updates["include_clinical_pearls"] = request.include_clinical_pearls
    if request.include_evidence_badges is not None:
        structure_updates["include_evidence_badges"] = request.include_evidence_badges
    if structure_updates:
        existing_structure = existing.get("structure_config", {})
        if isinstance(existing_structure, str):
            import json
            existing_structure = json.loads(existing_structure)
        updates["structure_config"] = {**existing_structure, **structure_updates}
    
    # Formatting config updates
    formatting_updates = {}
    if request.heading_style is not None:
        formatting_updates["heading_style"] = request.heading_style
    if request.list_style is not None:
        formatting_updates["list_style"] = request.list_style
    if request.citation_style is not None:
        formatting_updates["citation_style"] = request.citation_style
    if formatting_updates:
        existing_formatting = existing.get("formatting_config", {})
        if isinstance(existing_formatting, str):
            import json
            existing_formatting = json.loads(existing_formatting)
        updates["formatting_config"] = {**existing_formatting, **formatting_updates}
    
    # Visual config updates
    visual_updates = {}
    if request.color_scheme is not None:
        visual_updates["color_scheme"] = request.color_scheme
    if request.safety_box_style is not None:
        visual_updates["safety_box_style"] = request.safety_box_style
    if visual_updates:
        existing_visual = existing.get("visual_config", {})
        if isinstance(existing_visual, str):
            import json
            existing_visual = json.loads(existing_visual)
        updates["visual_config"] = {**existing_visual, **visual_updates}
    
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    
    update_style_profile(settings.db_path, style_id, **updates)
    
    profile = get_style_profile(settings.db_path, style_id)
    return StyleProfile.from_db_dict(profile).to_db_dict()


@app.delete("/api/styles/{style_id}")
def api_delete_style(style_id: str) -> dict[str, str]:
    """Delete a style profile."""
    success = delete_style_profile(settings.db_path, style_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Style profile {style_id} not found")
    return {"status": "deleted", "id": style_id}


@app.post("/api/styles/{style_id}/set-default")
def api_set_default_style(style_id: str) -> dict[str, Any]:
    """Set a style profile as the default."""
    profile = get_style_profile(settings.db_path, style_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Style profile {style_id} not found")
    
    set_default_style_profile(settings.db_path, style_id)
    
    # Fetch updated profile
    profile = get_style_profile(settings.db_path, style_id)
    return StyleProfile.from_db_dict(profile).to_db_dict()


@app.get("/{full_path:path}")
def serve_frontend(full_path: str) -> FileResponse:
    static_dir = Path(__file__).resolve().parents[1] / "static"
    if not static_dir.exists():
        raise HTTPException(status_code=404, detail="Frontend not built")
    if full_path.startswith("api/") or full_path.startswith("api"):
        raise HTTPException(status_code=404, detail="Not found")

    path = static_dir / full_path
    if path.is_dir():
        path = path / "index.html"
    # Prevent path traversal attacks
    try:
        path = safe_path_within(path, root_dir=static_dir)
    except UnsafePathError as e:
        raise HTTPException(status_code=404, detail="Not found") from e
    if path.exists():
        return FileResponse(str(path))
    index = static_dir / "index.html"
    if index.exists():
        return FileResponse(str(index))
    raise HTTPException(status_code=404, detail="Frontend not built")
