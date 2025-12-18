from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse

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
    ) -> None:
        self._cache_dir = cache_dir
        self._timeout_s = timeout_s
        self._client = httpx.Client(timeout=timeout_s, follow_redirects=True)
        self._max_retries = max_retries
        self._backoff_s = backoff_s
        self._per_host_min_interval_s = per_host_min_interval_s or {
            # NCBI recommends <= 3 req/sec without API key.
            "eutils.ncbi.nlm.nih.gov": 0.40,
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
