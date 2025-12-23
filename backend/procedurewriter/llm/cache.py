"""
LLM Response Caching Module.

Provides content-addressable caching for LLM responses to:
1. Reduce API costs during development
2. Speed up repeated operations
3. Enable offline development with cached responses

NO MOCKS - This uses real file-based caching with SQLite.
"""
from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def compute_cache_key(
    messages: list[dict[str, str]],
    model: str,
    temperature: float,
) -> str:
    """
    Compute a deterministic cache key from LLM request parameters.

    Uses SHA-256 hash of serialized request for content-addressable storage.

    Args:
        messages: List of message dicts with 'role' and 'content'
        model: Model identifier (e.g., "gpt-5.2", "claude-opus-4-5")
        temperature: Sampling temperature

    Returns:
        32-character hex string cache key
    """
    # Normalize the request to ensure consistent hashing
    normalized = {
        "messages": messages,
        "model": model,
        "temperature": round(temperature, 2),  # Round to avoid float precision issues
    }
    serialized = json.dumps(normalized, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:32]


@dataclass
class CacheStats:
    """Statistics for cache usage."""

    hits: int = 0
    misses: int = 0


class LLMCache:
    """
    File-based LLM response cache using SQLite with LRU eviction.

    Features:
    - Content-addressable storage (hash-based keys)
    - Persistent across sessions
    - Thread-safe (SQLite handles locking)
    - Stats tracking for monitoring
    - R7-002: LRU eviction when max_entries exceeded

    Usage:
        cache = LLMCache(cache_dir=Path("./cache"))
        key = compute_cache_key(messages, model, temperature)

        cached = cache.get(key)
        if cached:
            return LLMResponse(**cached)

        response = provider.chat_completion(messages, model, temperature)
        cache.set(key, response.to_dict())
        return response
    """

    # R7-002: Default max entries before LRU eviction
    DEFAULT_MAX_ENTRIES = 10000

    def __init__(self, cache_dir: Path | None = None, max_entries: int | None = None) -> None:
        """
        Initialize cache with optional custom directory.

        Args:
            cache_dir: Directory for cache storage. Defaults to ~/.cache/procedurewriter/llm
            max_entries: Maximum entries before LRU eviction (R7-002). Defaults to 10000.
        """
        if cache_dir is None:
            cache_dir = Path.home() / ".cache" / "procedurewriter" / "llm"

        self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = self._cache_dir / "cache.db"
        self._stats = CacheStats()
        self._max_entries = max_entries or self.DEFAULT_MAX_ENTRIES
        self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite database with cache table."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    response TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    model TEXT,
                    input_tokens INTEGER DEFAULT 0,
                    output_tokens INTEGER DEFAULT 0,
                    last_accessed REAL  -- R7-002: For LRU eviction
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_model ON cache(model)")
            # R7-002: Index for efficient LRU eviction
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_last_accessed ON cache(last_accessed)")
            # Migrate existing rows that don't have last_accessed
            conn.execute("""
                UPDATE cache SET last_accessed = created_at
                WHERE last_accessed IS NULL
            """)
            conn.commit()

    def get(self, key: str) -> dict[str, Any] | None:
        """
        Retrieve cached response by key.

        Args:
            key: Cache key (from compute_cache_key)

        Returns:
            Cached response dict, or None if not found
        """
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                "SELECT response FROM cache WHERE key = ?",
                (key,),
            )
            row = cursor.fetchone()

            if row is None:
                self._stats.misses += 1
                return None

            # R7-002: Update last_accessed for LRU tracking
            conn.execute(
                "UPDATE cache SET last_accessed = ? WHERE key = ?",
                (time.time(), key),
            )
            conn.commit()

        self._stats.hits += 1
        return json.loads(row[0])

    def set(self, key: str, response: dict[str, Any]) -> None:
        """
        Store response in cache.

        Args:
            key: Cache key (from compute_cache_key)
            response: Response dict to cache

        Overwrites existing entries with same key.
        R7-002: Evicts least recently used entries when max_entries exceeded.
        """
        now = time.time()
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO cache (key, response, created_at, model, input_tokens, output_tokens, last_accessed)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key,
                    json.dumps(response, ensure_ascii=False),
                    now,
                    response.get("model"),
                    response.get("input_tokens", 0),
                    response.get("output_tokens", 0),
                    now,  # R7-002: Set initial last_accessed
                ),
            )

            # R7-002: Evict oldest entries if over limit
            cursor = conn.execute("SELECT COUNT(*) FROM cache")
            count = cursor.fetchone()[0]

            if count > self._max_entries:
                # Delete 10% of oldest entries to avoid frequent evictions
                evict_count = max(1, count - int(self._max_entries * 0.9))
                conn.execute(
                    """
                    DELETE FROM cache WHERE key IN (
                        SELECT key FROM cache
                        ORDER BY last_accessed ASC
                        LIMIT ?
                    )
                    """,
                    (evict_count,),
                )
                logger.info(f"R7-002: Evicted {evict_count} LRU cache entries")

            conn.commit()

    def get_stats(self) -> dict[str, int | float]:
        """
        Get cache statistics.

        Returns:
            Dict with hits, misses, entries, and hit_rate
        """
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM cache")
            count = cursor.fetchone()[0]

        total_requests = self._stats.hits + self._stats.misses
        hit_rate = (
            round(self._stats.hits / total_requests * 100, 1) if total_requests > 0 else 0.0
        )

        return {
            "hits": self._stats.hits,
            "misses": self._stats.misses,
            "entries": count,
            "hit_rate": hit_rate,
        }

    def clear(self) -> None:
        """Clear all cached entries."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("DELETE FROM cache")
            conn.commit()
        self._stats = CacheStats()
        logger.info("LLM cache cleared")

    def get_size_bytes(self) -> int:
        """
        Get total cache size in bytes.

        Returns:
            Size of cache database file in bytes
        """
        if self._db_path.exists():
            return self._db_path.stat().st_size
        return 0
