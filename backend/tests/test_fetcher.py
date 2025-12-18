import httpx
import respx

from procedurewriter.pipeline.fetcher import CachedHttpClient


@respx.mock
def test_cached_http_client_retries_on_429(tmp_path):
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    route = respx.get(url).mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "0"}, content=b"Too Many Requests"),
            httpx.Response(200, content=b"<ok/>"),
        ]
    )

    http = CachedHttpClient(
        cache_dir=tmp_path,
        per_host_min_interval_s={},
        backoff_s=0.0,
        sleep_fn=lambda _s: None,
        max_retries=2,
    )
    try:
        resp = http.get(url, params={"db": "pubmed", "id": "1"})
        assert resp.status_code == 200
        assert resp.content == b"<ok/>"
        assert route.call_count == 2
    finally:
        http.close()

