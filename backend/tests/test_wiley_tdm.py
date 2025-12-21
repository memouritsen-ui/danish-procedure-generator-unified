from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path

import pytest

from procedurewriter.pipeline import run as run_module
from procedurewriter.pipeline.run import _apply_wiley_tdm_fulltext, _resolve_wiley_tdm_token
from procedurewriter.pipeline.types import SourceRecord
from procedurewriter.settings import Settings


class DummyHttp:
    def __init__(self, content: bytes) -> None:
        self.content = content
        self.calls: list[dict[str, object]] = []

    def get(self, url: str, *, params=None, headers=None):
        self.calls.append({"url": url, "params": params, "headers": headers})
        return SimpleNamespace(status_code=200, content=self.content)


def _make_source(*, url: str | None, doi: str | None = None) -> SourceRecord:
    return SourceRecord(
        source_id="SRC0001",
        fetched_at_utc="2024-01-01T00:00:00Z",
        kind="pubmed",
        title="Test source",
        year=2024,
        url=url,
        doi=doi,
        pmid=None,
        raw_path="raw/SRC0001.xml",
        normalized_path="normalized/SRC0001.txt",
        raw_sha256="rawhash",
        normalized_sha256="normhash",
        extraction_notes=None,
        terms_licence_note=None,
        extra={},
    )


def test_resolve_wiley_tdm_token_prefers_settings(monkeypatch) -> None:
    monkeypatch.setenv("TDM_API_TOKEN", "env-token")
    settings = Settings(wiley_tdm_token="settings-token")
    assert _resolve_wiley_tdm_token(settings) == "settings-token"


def test_resolve_wiley_tdm_token_falls_back_to_env(monkeypatch) -> None:
    monkeypatch.delenv("TDM_API_TOKEN", raising=False)
    monkeypatch.setenv("WILEY_TDM_TOKEN", "env-token")
    settings = Settings(wiley_tdm_token=None)
    assert _resolve_wiley_tdm_token(settings) == "env-token"


def test_apply_wiley_tdm_fulltext_updates_source(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(run_module, "extract_pdf_pages", lambda _p: ["PAGE 1"])
    monkeypatch.setattr(run_module, "normalize_pdf_pages", lambda _pages: "FULLTEXT")

    http = DummyHttp(content=b"%PDF-1.4 fake pdf")
    sources = [
        _make_source(url="https://doi.org/10.1002/14651858.CD000001")
    ]

    stats = _apply_wiley_tdm_fulltext(
        sources=sources,
        http=http,
        run_dir=tmp_path,
        token="tdm-token",
        base_url="https://api.wiley.com/onlinelibrary/tdm/v1",
        max_downloads=5,
        allow_non_wiley_doi=False,
        strict_mode=True,
    )

    assert stats["downloaded"] == 1
    assert sources[0].doi == "10.1002/14651858.CD000001"
    assert sources[0].raw_path.endswith(".pdf")
    assert Path(sources[0].raw_path).exists()
    assert Path(sources[0].normalized_path).read_text(encoding="utf-8") == "FULLTEXT"
    assert sources[0].extra.get("tdm_fulltext") is True
    assert sources[0].extra.get("tdm_original_raw_path") == "raw/SRC0001.xml"
    assert http.calls
    assert http.calls[0]["headers"]["Wiley-TDM-Client-Token"] == "tdm-token"


def test_apply_wiley_tdm_fulltext_skips_non_wiley_doi(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(run_module, "extract_pdf_pages", lambda _p: ["PAGE 1"])
    monkeypatch.setattr(run_module, "normalize_pdf_pages", lambda _pages: "FULLTEXT")

    http = DummyHttp(content=b"%PDF-1.4 fake pdf")
    sources = [
        _make_source(url="https://example.com/10.0000/ABC123", doi="10.0000/ABC123")
    ]

    stats = _apply_wiley_tdm_fulltext(
        sources=sources,
        http=http,
        run_dir=tmp_path,
        token="tdm-token",
        base_url="https://api.wiley.com/onlinelibrary/tdm/v1",
        max_downloads=5,
        allow_non_wiley_doi=False,
        strict_mode=False,
    )

    assert stats["downloaded"] == 0
    assert stats["skipped_non_wiley"] == 1
    assert http.calls == []
