from __future__ import annotations

from procedurewriter.pipeline.fetcher import CachedHttpClient
from procedurewriter.pipeline.pubmed import PubMedClient


def check_ncbi_status(
    *,
    http: CachedHttpClient,
    tool: str,
    email: str | None,
    api_key: str | None,
) -> tuple[bool, str]:
    try:
        client = PubMedClient(http, tool=tool, email=email, api_key=api_key)
        _pmids, _resp = client.search("asthma", retmax=1)
        if api_key:
            return True, "OK"
        return True, "OK (no API key configured)"
    except Exception as e:  # noqa: BLE001
        return False, str(e)

