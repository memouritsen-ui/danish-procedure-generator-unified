from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import sqlite3
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from procedurewriter import config_store
from procedurewriter.db import (
    add_library_source,
    create_run,
    delete_secret,
    get_run,
    get_secret,
    get_version_chain,
    init_db,
    iter_jsonl,
    list_library_sources,
    list_procedure_versions,
    list_runs,
    list_unique_procedures,
    mask_secret,
    set_secret,
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
from procedurewriter.crypto import get_or_create_key
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
from procedurewriter.settings import settings
from procedurewriter.worker import run_worker

logger = logging.getLogger(__name__)

# R5-001: Rate limiting setup
limiter = Limiter(key_func=get_remote_address)

# R5-002: Request timeout (seconds)
REQUEST_TIMEOUT_SECONDS = 300  # 5 minutes for LLM operations


class TimeoutMiddleware(BaseHTTPMiddleware):
    """R5-002: Middleware to enforce request timeout."""

    async def dispatch(self, request: Request, call_next):
        try:
            return await asyncio.wait_for(
                call_next(request),
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            return JSONResponse(
                status_code=504,
                content={"detail": f"Request timed out after {REQUEST_TIMEOUT_SECONDS} seconds"}
            )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown lifecycle.

    R5-014: Log startup errors
    R5-015: Cleanup on shutdown
    """
    # Startup
    try:
        logger.info("Starting Procedure Writer API...")
        settings.runs_dir.mkdir(parents=True, exist_ok=True)
        settings.cache_dir.mkdir(parents=True, exist_ok=True)
        settings.uploads_dir.mkdir(parents=True, exist_ok=True)
        (settings.resolved_data_dir / "index").mkdir(parents=True, exist_ok=True)
        init_db(settings.db_path)
        # Fail fast if encryption key is missing
        get_or_create_key()
        logger.info("Database initialized, encryption key ready")

        # Start background worker loop if enabled
        worker_task = None
        stop_event = None
        if settings.queue_start_worker_on_startup:
            stop_event = asyncio.Event()
            app.state.worker_stop_event = stop_event
            worker_task = asyncio.create_task(
                run_worker(settings=settings, stop_event=stop_event)
            )
            app.state.worker_task = worker_task
            logger.info("Background worker started")

        logger.info("Procedure Writer API started successfully")
    except Exception as e:
        logger.error(f"FATAL: Startup failed: {e}", exc_info=True)
        raise

    yield  # Application runs here

    # Shutdown
    logger.info("Shutting down Procedure Writer API...")
    try:
        stop_event = getattr(app.state, "worker_stop_event", None)
        task = getattr(app.state, "worker_task", None)
        if stop_event is not None:
            stop_event.set()
            logger.info("Worker stop signal sent")
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            logger.info("Worker task cancelled")
        logger.info("Shutdown complete")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}", exc_info=True)


app = FastAPI(title="Akut procedure writer", version="0.1.0", lifespan=lifespan)

# R5-001: Attach rate limiter to app state
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """R5-001: Handle rate limit exceeded errors."""
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Try again later."}
    )


_OPENAI_SECRET_NAME = "openai_api_key"
_ANTHROPIC_SECRET_NAME = "anthropic_api_key"
_NCBI_SECRET_NAME = "ncbi_api_key"

# File upload limits
MAX_UPLOAD_SIZE_MB = 50
MAX_UPLOAD_SIZE = MAX_UPLOAD_SIZE_MB * 1024 * 1024  # 50MB
ALLOWED_UPLOAD_TYPES = {
    "application/pdf": b"%PDF",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": b"PK",
}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# R5-002: Add timeout middleware
app.add_middleware(TimeoutMiddleware)

# Include routers
from procedurewriter.api.meta_analysis import router as meta_analysis_router
from procedurewriter.routers import config as config_router
from procedurewriter.routers import keys as keys_router
from procedurewriter.routers import runs as runs_router
from procedurewriter.routers import styles as styles_router
from procedurewriter.routers import templates as templates_router
from procedurewriter.routers.keys import (
    _effective_anthropic_api_key,
    _effective_ncbi_api_key,
    _effective_openai_api_key,
)

app.include_router(meta_analysis_router)
app.include_router(config_router.router)
app.include_router(keys_router.router)
app.include_router(runs_router.router)
app.include_router(styles_router.router)
app.include_router(templates_router.router)


@app.get("/health")
@limiter.limit("60/minute")
def health_check(request: Request) -> dict:
    """Health check endpoint for load balancers and monitoring.

    R5-013: Includes DB connectivity check. Returns 200 if healthy, 503 if degraded.
    For detailed status, use /api/status.
    """
    from procedurewriter.db import _connect

    db_ok = False
    try:
        with _connect(settings.db_path) as conn:
            conn.execute("SELECT 1").fetchone()
            db_ok = True
    except sqlite3.Error:
        # Database unavailable or corrupted
        pass

    if not db_ok:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "db": "unavailable"}
        )

    return {"status": "healthy", "db": "ok"}


# Startup/shutdown now handled by lifespan context manager (R5-014, R5-015)


@app.get("/api/status", response_model=AppStatus)
@limiter.limit("60/minute")
def api_status(request: Request) -> AppStatus:
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
@limiter.limit("5/minute")
async def api_write(request: Request, req: WriteRequest) -> WriteResponse:
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
    return WriteResponse(run_id=run_id)
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
@app.post("/api/ingest/pdf", response_model=IngestResponse)
@limiter.limit("5/minute")
async def api_ingest_pdf(request: Request, file: UploadFile) -> IngestResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    # Read file content with size check
    raw_bytes = await file.read()
    if len(raw_bytes) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {MAX_UPLOAD_SIZE_MB}MB",
        )

    # Validate magic bytes (PDF must start with %PDF)
    if not raw_bytes.startswith(b"%PDF"):
        raise HTTPException(
            status_code=400,
            detail="Invalid PDF file: content does not match PDF format",
        )

    source_id = f"LIB_{uuid.uuid4().hex}"
    raw_path = settings.uploads_dir / f"{source_id}.pdf"
    write_bytes(raw_path, raw_bytes)

    pages = await run_in_threadpool(extract_pdf_pages, raw_path)
    normalized_text = await run_in_threadpool(normalize_pdf_pages, pages)
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
@limiter.limit("5/minute")
async def api_ingest_docx(request: Request, file: UploadFile) -> IngestResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    # Read file content with size check
    raw_bytes = await file.read()
    if len(raw_bytes) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {MAX_UPLOAD_SIZE_MB}MB",
        )

    # Validate magic bytes (DOCX/ZIP must start with PK)
    if not raw_bytes.startswith(b"PK"):
        raise HTTPException(
            status_code=400,
            detail="Invalid DOCX file: content does not match DOCX format",
        )

    source_id = f"LIB_{uuid.uuid4().hex}"
    raw_path = settings.uploads_dir / f"{source_id}.docx"
    write_bytes(raw_path, raw_bytes)

    blocks = await run_in_threadpool(extract_docx_blocks, raw_path)
    normalized_text = await run_in_threadpool(normalize_docx_blocks, blocks)
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


def _fetch_url_sync(url: str, cache_dir: Path) -> Any:
    from procedurewriter.pipeline.fetcher import CachedHttpClient

    http = CachedHttpClient(cache_dir=cache_dir)
    try:
        return http.get(url)
    finally:
        http.close()


@app.post("/api/ingest/url", response_model=IngestResponse)
@limiter.limit("5/minute")
async def api_ingest_url(request: Request, req: IngestUrlRequest) -> IngestResponse:
    allowlist = config_store.load_yaml(settings.allowlist_path)
    prefixes = allowlist.get("allowed_url_prefixes", []) if isinstance(allowlist, dict) else []
    if not any(req.url.startswith(str(p)) for p in prefixes):
        raise HTTPException(status_code=400, detail="URL not allowed by allowlist")

    source_id = f"LIB_{uuid.uuid4().hex}"

    resp = await run_in_threadpool(_fetch_url_sync, req.url, settings.cache_dir)

    raw_path = settings.uploads_dir / f"{source_id}.html"
    write_bytes(raw_path, resp.content)
    normalized_text = await run_in_threadpool(normalize_html, resp.content)
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




# --- Protocol API Endpoints ---


@app.get("/api/protocols")
def api_list_protocols(
    status: str = "active",
    skip: int = 0,
    limit: int = 100,
) -> dict[str, Any]:
    """List protocols with pagination, optionally filtered by status."""
    # R3-009: Bound pagination to prevent unbounded responses.
    limit = min(max(limit, 1), 1000)
    skip = max(skip, 0)

    protocols = list_protocols(settings.db_path, status if status != "all" else None)
    paginated = protocols[skip : skip + limit]
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
            for p in paginated
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
@limiter.limit("5/minute")
async def api_upload_protocol(
    request: Request,
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

        protocol_id = await run_in_threadpool(
            upload_protocol,
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


@app.delete("/api/protocols/{protocol_id}", status_code=204)
def api_delete_protocol(protocol_id: str) -> None:
    """Delete a protocol.

    R5-007: Returns 204 No Content on success per REST conventions.
    """
    success = delete_protocol(settings.db_path, protocol_id)
    if not success:
        raise HTTPException(status_code=404, detail="Protocol not found")

    return None
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
