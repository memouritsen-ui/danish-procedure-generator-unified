from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class WriteRequest(BaseModel):
    procedure: str = Field(min_length=1)
    context: str | None = None


class WriteResponse(BaseModel):
    run_id: str


class RunSummary(BaseModel):
    run_id: str
    created_at_utc: str
    updated_at_utc: str
    procedure: str
    status: str


class RunDetail(BaseModel):
    run_id: str
    created_at_utc: str
    updated_at_utc: str
    procedure: str
    context: str | None
    status: str
    error: str | None
    procedure_md: str | None
    source_count: int | None = None
    warnings: list[str] | None = None


class SourceRecord(BaseModel):
    source_id: str
    fetched_at_utc: str
    kind: str
    title: str | None = None
    year: int | None = None
    url: str | None = None
    doi: str | None = None
    pmid: str | None = None
    raw_path: str
    normalized_path: str
    raw_sha256: str
    normalized_sha256: str
    extraction_notes: str | None = None
    terms_licence_note: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class SourcesResponse(BaseModel):
    run_id: str
    sources: list[SourceRecord]


class IngestUrlRequest(BaseModel):
    url: str = Field(min_length=1)


class IngestResponse(BaseModel):
    source_id: str


class ConfigText(BaseModel):
    text: str


class ApiKeySetRequest(BaseModel):
    api_key: str = Field(min_length=1)


class ApiKeyInfo(BaseModel):
    present: bool
    masked: str | None = None


class ApiKeyStatus(BaseModel):
    present: bool
    ok: bool
    message: str


class AppStatus(BaseModel):
    version: str
    dummy_mode: bool
    use_llm: bool
    llm_model: str
    openai_embeddings_model: str
    openai_base_url: str
    openai_key_present: bool
    openai_key_source: str
    ncbi_api_key_present: bool
    ncbi_api_key_source: str
    ncbi_tool: str
    ncbi_email: str | None = None
