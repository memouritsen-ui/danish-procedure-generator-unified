import httpx
import respx

from procedurewriter.ncbi_status import check_ncbi_status
from procedurewriter.pipeline.fetcher import CachedHttpClient


@respx.mock
def test_check_ncbi_status_ok_with_or_without_key(tmp_path):
    search_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<eSearchResult>
  <IdList>
    <Id>12345678</Id>
  </IdList>
</eSearchResult>
"""
    respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi").mock(
        return_value=httpx.Response(200, content=search_xml)
    )

    http = CachedHttpClient(cache_dir=tmp_path, per_host_min_interval_s={}, backoff_s=0.0, sleep_fn=lambda _s: None)
    try:
        ok, msg = check_ncbi_status(http=http, tool="test", email=None, api_key=None)
        assert ok is True
        assert "no api key" in msg.lower()

        ok2, msg2 = check_ncbi_status(http=http, tool="test", email=None, api_key="K")
        assert ok2 is True
        assert msg2 == "OK"
    finally:
        http.close()


@respx.mock
def test_check_ncbi_status_handles_http_error(tmp_path):
    respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi").mock(
        return_value=httpx.Response(500, content=b"err")
    )

    http = CachedHttpClient(
        cache_dir=tmp_path, per_host_min_interval_s={}, max_retries=0, backoff_s=0.0, sleep_fn=lambda _s: None
    )
    try:
        ok, _msg = check_ncbi_status(http=http, tool="test", email=None, api_key=None)
        assert ok is False
    finally:
        http.close()

