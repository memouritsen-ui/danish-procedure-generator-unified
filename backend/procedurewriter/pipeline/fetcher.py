from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse
from xml.etree import ElementTree as ET

import httpx

from procedurewriter.pipeline.hashing import sha256_text
from procedurewriter.pipeline.io import write_bytes, write_json


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class CachedResponse:
    url: str
    status_code: int
    headers: dict[str, str]
    content: bytes
    fetched_at_utc: str
    cache_path: str


@dataclass(frozen=True)
class PmcFullText:
    pmc_id: str
    raw_xml: bytes
    text: str
    url: str
    source: str


# Default User-Agent for HTTP requests - identifies the tool for compliance
DEFAULT_USER_AGENT = (
    "DanishProcedureGenerator/1.0 "
    "(Medical evidence synthesis tool; https://github.com/danish-procedure-generator; "
    "contact: procedure-bot@example.com)"
)


class CachedHttpClient:
    def __init__(
        self,
        *,
        cache_dir: Path,
        timeout_s: float = 30.0,
        max_retries: int = 4,
        backoff_s: float = 0.6,
        per_host_min_interval_s: dict[str, float] | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        user_agent: str = DEFAULT_USER_AGENT,
        strict_mode: bool = False,
    ) -> None:
        self._cache_dir = cache_dir
        self._timeout_s = timeout_s
        self._user_agent = user_agent
        self._strict_mode = strict_mode
        self._client = httpx.Client(
            timeout=timeout_s,
            follow_redirects=True,
            headers={"User-Agent": user_agent},
        )
        self._max_retries = max_retries
        self._backoff_s = backoff_s
        self._per_host_min_interval_s = per_host_min_interval_s or {
            # NCBI recommends <= 3 req/sec without API key.
            "eutils.ncbi.nlm.nih.gov": 0.40,
            # NICE - polite crawling (1 req/sec)
            "www.nice.org.uk": 1.0,
            "nice.org.uk": 1.0,
            "api.nice.org.uk": 1.0,
            # Cochrane Library - polite crawling (1 req/sec)
            "www.cochranelibrary.com": 1.0,
            "cochranelibrary.com": 1.0,
            "api.onlinelibrary.wiley.com": 1.0,
            # Wiley TDM API - polite crawling (1 req/sec)
            "api.wiley.com": 1.0,
        }
        self._sleep_fn = sleep_fn
        self._last_request_at_by_host: dict[str, float] = {}

    def close(self) -> None:
        self._client.close()

    def _cache_key(self, url: str, params: dict[str, Any] | None) -> str:
        if not params:
            return sha256_text(url)
        encoded = urlencode(sorted((str(k), str(v)) for k, v in params.items()))
        return sha256_text(f"{url}?{encoded}")

    def get(
        self, url: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None
    ) -> CachedResponse:
        key = self._cache_key(url, params)
        content_path = self._cache_dir / "http" / f"{key}.bin"
        meta_path = self._cache_dir / "http" / f"{key}.json"

        if content_path.exists() and meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            return CachedResponse(
                url=meta["url"],
                status_code=int(meta["status_code"]),
                headers=dict(meta.get("headers", {})),
                content=content_path.read_bytes(),
                fetched_at_utc=str(meta["fetched_at_utc"]),
                cache_path=str(content_path),
            )

        host = urlparse(url).netloc.lower()
        last_err: Exception | None = None
        resp: httpx.Response | None = None
        for attempt in range(self._max_retries + 1):
            self._throttle(host)
            try:
                resp = self._client.get(url, params=params, headers=headers)
            except httpx.RequestError as e:
                last_err = e
                if attempt >= self._max_retries:
                    raise
                self._sleep_fn(self._backoff_delay(attempt))
                continue

            if resp.status_code in {429, 500, 502, 503, 504}:
                last_err = httpx.HTTPStatusError(
                    f"Server error '{resp.status_code}' for url '{resp.request.url}'",
                    request=resp.request,
                    response=resp,
                )
                if attempt >= self._max_retries:
                    resp.raise_for_status()
                delay = _retry_after_seconds(resp) or self._backoff_delay(attempt)
                self._sleep_fn(delay)
                continue

            resp.raise_for_status()
            last_err = None
            break

        if resp is None:
            if last_err is not None:
                raise last_err
            raise RuntimeError("HTTP request failed unexpectedly.")

        fetched_at = utc_now_iso()
        meta = {
            "url": str(resp.url),
            "status_code": resp.status_code,
            "headers": dict(resp.headers),
            "fetched_at_utc": fetched_at,
        }
        write_bytes(content_path, resp.content)
        write_json(meta_path, meta)

        return CachedResponse(
            url=str(resp.url),
            status_code=resp.status_code,
            headers=dict(resp.headers),
            content=resp.content,
            fetched_at_utc=fetched_at,
            cache_path=str(content_path),
        )

    def _throttle(self, host: str) -> None:
        min_interval = self._per_host_min_interval_s.get(host)
        if not min_interval:
            return
        now = time.monotonic()
        last = self._last_request_at_by_host.get(host)
        if last is not None:
            sleep_s = min_interval - (now - last)
            if sleep_s > 0:
                self._sleep_fn(sleep_s)
        self._last_request_at_by_host[host] = time.monotonic()

    def _backoff_delay(self, attempt: int) -> float:
        # 0.6, 1.2, 2.4, 4.8... (capped)
        delay = self._backoff_s * (1 << attempt)
        return min(20.0, delay)


def _retry_after_seconds(resp: httpx.Response) -> float | None:
    raw = resp.headers.get("Retry-After")
    if not raw:
        return None
    raw = raw.strip()
    if raw.isdigit():
        return float(raw)
    return None


_PMC_EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_PMC_OA_BASE = "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi"
_ws_re = re.compile(r"[ \t]+")
_many_newlines_re = re.compile(r"\n{3,}")


def fetch_pmc_full_text(
    http: CachedHttpClient,
    *,
    pmid: str | None = None,
    pmc_id: str | None = None,
    doi: str | None = None,
) -> PmcFullText | None:
    resolved_pmc_id = _normalize_pmc_id(pmc_id) if pmc_id else None
    if not resolved_pmc_id and pmid:
        resolved_pmc_id = _resolve_pmc_id_from_pmid(http, pmid)
    if not resolved_pmc_id and doi:
        resolved_pmc_id = _resolve_pmc_id_from_oa(http, doi)
    if not resolved_pmc_id:
        return None

    url = f"{_PMC_EUTILS_BASE}/efetch.fcgi"
    params = {"db": "pmc", "id": resolved_pmc_id, "retmode": "xml"}
    resp = http.get(url, params=params)
    text = _extract_pmc_text(resp.content)
    if not text:
        return None
    return PmcFullText(
        pmc_id=resolved_pmc_id,
        raw_xml=resp.content,
        text=text,
        url=f"https://www.ncbi.nlm.nih.gov/pmc/articles/{resolved_pmc_id}/",
        source="pmc",
    )


def _normalize_pmc_id(pmc_id: str | None) -> str | None:
    if not pmc_id:
        return None
    pmc_id = pmc_id.strip()
    if not pmc_id:
        return None
    return pmc_id if pmc_id.upper().startswith("PMC") else f"PMC{pmc_id}"


def _resolve_pmc_id_from_pmid(http: CachedHttpClient, pmid: str) -> str | None:
    url = f"{_PMC_EUTILS_BASE}/elink.fcgi"
    params = {
        "dbfrom": "pubmed",
        "db": "pmc",
        "id": pmid,
        "linkname": "pubmed_pmc",
    }
    resp = http.get(url, params=params)
    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError:
        return None
    link = root.find(".//LinkSetDb/Link/Id")
    if link is None or not link.text:
        return None
    return _normalize_pmc_id(link.text.strip())


def _resolve_pmc_id_from_oa(http: CachedHttpClient, doi: str) -> str | None:
    url = _PMC_OA_BASE
    params = {"doi": doi}
    resp = http.get(url, params=params)
    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError:
        return None

    record = root.find(".//record")
    if record is not None:
        pmc_id = record.get("id") or record.get("pmcid")
        resolved = _normalize_pmc_id(pmc_id)
        if resolved:
            return resolved

    for link in root.findall(".//link"):
        href = link.get("href") or ""
        if "PMC" in href.upper():
            match = re.search(r"(PMC\\d+)", href.upper())
            if match:
                return match.group(1)

    return None


def _extract_pmc_text(raw_xml: bytes) -> str:
    try:
        root = ET.fromstring(raw_xml)
    except ET.ParseError:
        return ""

    parts: list[str] = []
    title = root.findtext(".//article-title")
    if title:
        parts.append(title.strip())

    abstract_parts: list[str] = []
    for node in root.findall(".//abstract//p"):
        if node.text and node.text.strip():
            abstract_parts.append(node.text.strip())
    if abstract_parts:
        parts.append(" ".join(abstract_parts))

    body = root.find(".//body")
    if body is not None:
        body_text = " ".join(t.strip() for t in body.itertext() if t and t.strip())
        if body_text:
            parts.append(body_text)

    return _clean_pmc_text("\n\n".join(parts))


def _clean_pmc_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _ws_re.sub(" ", text)
    text = _many_newlines_re.sub("\n\n", text)
    return text.strip()
