"""Document-level cache for PICO extractions.

Uses SHA-256 hash of abstract text as cache key for reuse across runs.
Implements confidence-based gating to prevent caching uncertain extractions.
"""
from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from pathlib import Path

from procedurewriter.agents.meta_analysis.models import PICOData

logger = logging.getLogger(__name__)


class MetaAnalysisCache:
    """Cache for PICO extraction results.

    Features:
    - Document-level caching using SHA-256 hash of abstract
    - Confidence gating (low-confidence extractions not cached by default)
    - SQLite persistence
    - Hit/miss statistics
    """

    DEFAULT_CONFIDENCE_THRESHOLD = 0.85

    def __init__(
        self,
        cache_dir: Path,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    ) -> None:
        """Initialize cache.

        Args:
            cache_dir: Directory for cache database.
            confidence_threshold: Minimum confidence to cache (0-1).
        """
        self.cache_dir = cache_dir
        self._confidence_threshold = confidence_threshold
        self._hits = 0
        self._misses = 0

        # Ensure directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._db_path = self.cache_dir / "meta_analysis_cache.sqlite3"
        self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite database schema."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pico_cache (
                    key TEXT PRIMARY KEY,
                    data JSON NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def compute_cache_key(
        self, abstract: str, study_id: str | None = None
    ) -> str:
        """Compute cache key from abstract text.

        Args:
            abstract: Study abstract text.
            study_id: Optional study identifier for disambiguation.

        Returns:
            32-character hex string (truncated SHA-256).
        """
        content = abstract
        if study_id:
            content = f"{study_id}:{abstract}"

        hash_obj = hashlib.sha256(content.encode("utf-8"))
        return hash_obj.hexdigest()[:32]

    def should_cache(self, pico: PICOData) -> bool:
        """Check if PICO extraction should be cached based on confidence.

        Args:
            pico: PICO extraction result.

        Returns:
            True if confidence >= threshold.
        """
        return pico.confidence >= self._confidence_threshold

    def get(self, key: str) -> PICOData | None:
        """Retrieve cached PICO extraction.

        Args:
            key: Cache key (from compute_cache_key).

        Returns:
            Cached PICOData or None if not found.
        """
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                "SELECT data FROM pico_cache WHERE key = ?",
                (key,),
            )
            row = cursor.fetchone()

        if row is None:
            self._misses += 1
            return None

        self._hits += 1

        try:
            data = json.loads(row[0])
            return PICOData(**data)
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to deserialize cached PICO data: {e}")
            self._hits -= 1
            self._misses += 1
            return None

    def set(self, key: str, pico: PICOData, force: bool = False) -> bool:
        """Store PICO extraction in cache.

        Args:
            key: Cache key.
            pico: PICO extraction to cache.
            force: If True, cache even if confidence is below threshold.

        Returns:
            True if cached, False if rejected due to low confidence.
        """
        if not force and not self.should_cache(pico):
            logger.debug(
                f"Not caching PICO extraction with confidence {pico.confidence:.2f} "
                f"(threshold: {self._confidence_threshold})"
            )
            return False

        data = json.dumps(pico.model_dump())

        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO pico_cache (key, data)
                VALUES (?, ?)
                """,
                (key, data),
            )
            conn.commit()

        return True

    def get_stats(self) -> dict[str, int]:
        """Get cache hit/miss statistics.

        Returns:
            Dictionary with 'hits' and 'misses' counts.
        """
        return {
            "hits": self._hits,
            "misses": self._misses,
        }

    def clear(self) -> None:
        """Clear all cached entries."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("DELETE FROM pico_cache")
            conn.commit()

        logger.info("Cleared meta-analysis cache")
