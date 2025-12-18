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
from fastapi.responses import FileResponse

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
from procedurewriter.pipeline.run import run_pipeline
from procedurewriter.run_bundle import build_run_bundle_zip, read_run_manifest
from procedurewriter.schemas import (
    ApiKeyInfo,
    ApiKeySetRequest,
    ApiKeyStatus,
    AppStatus,
    ConfigText,
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
    return AppStatus(
        version=str(app.version),
        dummy_mode=settings.dummy_mode,
        use_llm=settings.use_llm,
        llm_model=settings.llm_model,
        openai_embeddings_model=settings.openai_embeddings_model,
        openai_base_url=base_url,
        openai_key_present=bool(_effective_openai_api_key()),
        openai_key_source=key_source,
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
        )
        for r in list_runs(settings.db_path)
    ]


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
    )


@app.get("/api/runs/{run_id}/docx")
def api_docx(run_id: str) -> FileResponse:
    run = get_run(settings.db_path, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    docx = Path(run.run_dir) / "Procedure.docx"
    if not docx.exists():
        raise HTTPException(status_code=404, detail="DOCX not available")
    return FileResponse(path=str(docx), filename="Procedure.docx", media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


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
    if path.exists():
        return FileResponse(str(path))
    index = static_dir / "index.html"
    if index.exists():
        return FileResponse(str(index))
    raise HTTPException(status_code=404, detail="Frontend not built")
