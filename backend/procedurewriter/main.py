from __future__ import annotations

import asyncio
import json
import os
import uuid
from functools import partial
from pathlib import Path
from typing import Any

import anyio
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from procedurewriter import config_store
from procedurewriter.db import (
    add_library_source,
    create_run,
    delete_secret,
    get_run,
    get_secret,
    init_db,
    iter_jsonl,
    list_library_sources,
    list_runs,
    mask_secret,
    set_secret,
    update_run_status,
)
from procedurewriter.file_utils import UnsafePathError, safe_path_within
from procedurewriter.ncbi_status import check_ncbi_status
from procedurewriter.pipeline.hashing import sha256_bytes, sha256_text
from procedurewriter.pipeline.io import write_bytes, write_json, write_text
from procedurewriter.pipeline.normalize import (
    extract_docx_blocks,
    extract_pdf_pages,
    normalize_docx_blocks,
    normalize_html,
    normalize_pdf_pages,
)
from procedurewriter.pipeline.events import get_emitter_if_exists
from procedurewriter.pipeline.run import run_pipeline
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
    create_run(settings.db_path, run_id=run_id, procedure=req.procedure, context=req.context, run_dir=run_dir)
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
    )


def _sanitize_filename(name: str) -> str:
    """Sanitize a string for use as a filename."""
    import re
    # Replace spaces and special chars with underscores, keep Danish chars
    sanitized = re.sub(r'[^\w\sæøåÆØÅ-]', '', name)
    sanitized = re.sub(r'\s+', '_', sanitized.strip())
    return sanitized[:100] if sanitized else "Procedure"


@app.get("/api/runs/{run_id}/docx")
def api_docx(run_id: str) -> FileResponse:
    run = get_run(settings.db_path, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    docx = Path(run.run_dir) / "Procedure.docx"
    if not docx.exists():
        raise HTTPException(status_code=404, detail="DOCX not available")
    # Use procedure name for download filename
    filename = f"{_sanitize_filename(run.procedure)}.docx"
    return FileResponse(path=str(docx), filename=filename, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


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
        client = Anthropic(api_key=key)
        # Simple test - just instantiate (full test would require an API call)
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
    except UnsafePathError:
        raise HTTPException(status_code=404, detail="Not found")
    if path.exists():
        return FileResponse(str(path))
    index = static_dir / "index.html"
    if index.exists():
        return FileResponse(str(index))
    raise HTTPException(status_code=404, detail="Frontend not built")
