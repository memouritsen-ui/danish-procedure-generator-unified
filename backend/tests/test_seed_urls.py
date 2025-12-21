import httpx
import respx

from procedurewriter.pipeline.evidence_hierarchy import EvidenceHierarchy
from procedurewriter.pipeline.fetcher import CachedHttpClient
from procedurewriter.pipeline.run import _append_seed_url_sources


@respx.mock
def test_seed_urls_are_fetched_and_written(tmp_path):
    url = "https://www.nice.org.uk/guidance/example"
    respx.get(url).mock(return_value=httpx.Response(200, content=b"<html><head><title>T</title></head><body>Hi</body></html>"))

    http = CachedHttpClient(cache_dir=tmp_path, per_host_min_interval_s={}, backoff_s=0.0, sleep_fn=lambda _s: None)
    hierarchy = EvidenceHierarchy()  # Use default config
    try:
        run_dir = tmp_path / "run"
        sources = []
        warnings = []
        next_n = _append_seed_url_sources(
            allowlist={"allowed_url_prefixes": ["https://www.nice.org.uk/"], "seed_urls": [url]},
            http=http,
            run_dir=run_dir,
            source_n=1,
            sources=sources,
            warnings=warnings,
            evidence_hierarchy=hierarchy,
            procedure="Test Procedure",
            context=None,
        )
        assert next_n == 2
        assert len(sources) == 1
        assert sources[0].kind == "guideline_url"
        assert sources[0].title == "T"
        # Check evidence level is added
        assert sources[0].extra.get("evidence_level") is not None
        assert sources[0].extra.get("evidence_badge") is not None
        assert not warnings
    finally:
        http.close()


def test_seed_urls_respect_allowlist(tmp_path):
    http = CachedHttpClient(cache_dir=tmp_path, per_host_min_interval_s={}, backoff_s=0.0, sleep_fn=lambda _s: None)
    hierarchy = EvidenceHierarchy()  # Use default config
    try:
        run_dir = tmp_path / "run"
        sources = []
        warnings = []
        next_n = _append_seed_url_sources(
            allowlist={"allowed_url_prefixes": ["https://www.nice.org.uk/"], "seed_urls": ["https://evil.example/x"]},
            http=http,
            run_dir=run_dir,
            source_n=1,
            sources=sources,
            warnings=warnings,
            evidence_hierarchy=hierarchy,
            procedure="Test Procedure",
            context=None,
        )
        assert next_n == 1
        assert sources == []
        assert warnings and "not allowed" in warnings[0].lower()
    finally:
        http.close()


def test_seed_urls_filter_by_procedure_keywords(tmp_path):
    """Test that seed URLs are filtered by procedure_keywords."""
    http = CachedHttpClient(cache_dir=tmp_path, per_host_min_interval_s={}, backoff_s=0.0, sleep_fn=lambda _s: None)
    hierarchy = EvidenceHierarchy()
    try:
        run_dir = tmp_path / "run"
        sources = []
        warnings = []
        # Seed URL with keywords that don't match the procedure
        allowlist = {
            "allowed_url_prefixes": ["https://www.nice.org.uk/"],
            "seed_urls": [
                {"url": "https://www.nice.org.uk/cardiac", "procedure_keywords": ["heart", "cardiac"]},
            ],
        }
        next_n = _append_seed_url_sources(
            allowlist=allowlist,
            http=http,
            run_dir=run_dir,
            source_n=1,
            sources=sources,
            warnings=warnings,
            evidence_hierarchy=hierarchy,
            procedure="Lumbar Puncture",  # Does not match "heart" or "cardiac"
            context=None,
        )
        # URL should be filtered out - no sources added
        assert next_n == 1
        assert sources == []
        # Should have a warning about filtered URLs
        assert any("filtered out" in w.lower() for w in warnings)
    finally:
        http.close()

