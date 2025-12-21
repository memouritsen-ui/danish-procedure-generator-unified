from __future__ import annotations

import pytest

from procedurewriter.pipeline.evidence import EvidencePolicyError
from procedurewriter.pipeline.run import (
    _build_source_selection_report,
    _enforce_source_requirements,
)
from procedurewriter.pipeline.types import SourceRecord
from procedurewriter.settings import Settings


def _make_source(
    source_id: str,
    kind: str,
    *,
    evidence_level: str | None = None,
    evidence_priority: int | None = None,
) -> SourceRecord:
    extra: dict[str, object] = {}
    if evidence_level is not None:
        extra["evidence_level"] = evidence_level
    if evidence_priority is not None:
        extra["evidence_priority"] = evidence_priority
    return SourceRecord(
        source_id=source_id,
        fetched_at_utc="2025-01-01T00:00:00Z",
        kind=kind,
        title=f"Title for {source_id}",
        year=2024,
        url="https://example.com",
        doi=None,
        pmid=None,
        raw_path="raw",
        normalized_path="normalized",
        raw_sha256="rawhash",
        normalized_sha256="normhash",
        extraction_notes=None,
        terms_licence_note=None,
        extra=extra,
    )


def test_build_source_selection_report_counts_and_requirements() -> None:
    settings = Settings(require_international_sources=True, require_danish_guidelines=True, dummy_mode=False)
    warnings = ["seed warning"]
    sources = [
        _make_source("SRC0001", "danish_guideline", evidence_level="guideline", evidence_priority=1000),
        _make_source("SRC0002", "nice_guideline", evidence_level="guideline", evidence_priority=900),
        _make_source("SRC0003", "pubmed", evidence_level="meta_analysis", evidence_priority=800),
    ]

    report = _build_source_selection_report(sources=sources, settings=settings, warnings=warnings)

    assert report["counts"]["total_sources"] == 3
    assert report["counts"]["by_kind"]["danish_guideline"] == 1
    assert report["counts"]["by_kind"]["nice_guideline"] == 1
    assert report["counts"]["by_kind"]["pubmed"] == 1
    assert report["requirements"]["has_international_sources"] is True
    assert report["requirements"]["has_danish_guidelines"] is True
    assert report["requirements"]["missing"] == []
    assert report["warnings"] == warnings


def test_enforce_source_requirements_missing_international_raises() -> None:
    settings = Settings(require_international_sources=True, require_danish_guidelines=False, dummy_mode=False)
    warnings: list[str] = []
    sources = [_make_source("SRC0001", "danish_guideline")]

    with pytest.raises(EvidencePolicyError):
        _enforce_source_requirements(sources=sources, settings=settings, warnings=warnings)

    assert "No international sources found (NICE/Cochrane)." in warnings


def test_enforce_source_requirements_missing_danish_raises() -> None:
    settings = Settings(require_international_sources=False, require_danish_guidelines=True, dummy_mode=False)
    warnings: list[str] = []
    sources = [_make_source("SRC0001", "nice_guideline")]

    with pytest.raises(EvidencePolicyError):
        _enforce_source_requirements(sources=sources, settings=settings, warnings=warnings)

    assert "No Danish guideline sources found in local library." in warnings


def test_enforce_source_requirements_allows_when_present() -> None:
    """Test that no error is raised when all required source tiers are present."""
    settings = Settings(require_international_sources=True, require_danish_guidelines=True, dummy_mode=False)
    warnings: list[str] = []
    # Include all required source types: Danish, NICE, Cochrane, PubMed meta-analysis
    sources = [
        _make_source("SRC0001", "danish_guideline"),
        _make_source("SRC0002", "nice_guideline"),
        _make_source("SRC0003", "cochrane_review"),
        _make_source(
            "SRC0004",
            "pubmed",
            evidence_level="systematic_review",
            evidence_priority=700,
        ),
    ]
    # Add publication_types to PubMed source for meta-analysis detection
    sources[3].extra["publication_types"] = ["Systematic Review"]

    _enforce_source_requirements(sources=sources, settings=settings, warnings=warnings)


def test_enforce_source_requirements_warns_missing_tier_in_warn_mode() -> None:
    """Test that warn mode adds warnings but doesn't raise errors."""
    settings = Settings(require_international_sources=True, require_danish_guidelines=True, dummy_mode=False)
    warnings: list[str] = []
    sources = [
        _make_source("SRC0001", "danish_guideline"),
        _make_source("SRC0002", "cochrane_review"),
    ]

    # Should not raise in warn mode, just add warnings
    _enforce_source_requirements(sources=sources, settings=settings, warnings=warnings, evidence_policy="warn")


def test_enforce_source_requirements_skips_in_dummy_mode() -> None:
    settings = Settings(require_international_sources=True, require_danish_guidelines=True, dummy_mode=True)
    warnings: list[str] = []

    _enforce_source_requirements(sources=[], settings=settings, warnings=warnings)
