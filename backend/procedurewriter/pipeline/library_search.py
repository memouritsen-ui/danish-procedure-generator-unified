"""Danish Guideline Library search provider.

Integrates with guideline_harvester's SQLite + FTS5 database to search
40,665+ Danish clinical guidelines with priority 1000 (highest in evidence hierarchy).
"""
from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class LibrarySearchResult:
    """A search result from the Danish guideline library."""
    doc_id: str
    source_id: str
    source_name: str
    title: str
    url: str
    local_path: Path
    publish_year: str | None
    category: str | None
    content_type: str | None
    relevance_score: float
    priority: int = 1000  # Danish guidelines = highest priority

    def get_text_content(self) -> str | None:
        """Load the extracted text content from the document."""
        text_file = self.local_path / "extracted_text.txt"
        if text_file.exists():
            return text_file.read_text(encoding="utf-8")
        return None

    def get_metadata(self) -> dict[str, Any]:
        """Load the metadata JSON for this document."""
        meta_file = self.local_path / "metadata.json"
        if meta_file.exists():
            return json.loads(meta_file.read_text(encoding="utf-8"))
        return {}


class LibrarySearchProvider:
    """Search provider for the Danish guideline library.

    Uses FTS5 full-text search against the guideline_harvester SQLite database.
    Returns results with priority 1000 (highest in evidence hierarchy).
    """

    def __init__(self, library_root: Path | None = None):
        """Initialize the library search provider.

        Args:
            library_root: Root path of the guideline_harvester library.
                         Defaults to ~/guideline_harvester/library
        """
        if library_root is None:
            library_root = Path.home() / "guideline_harvester" / "library"

        self.library_root = library_root
        self.db_path = library_root / "index.sqlite"
        self._available: bool | None = None

    def available(self) -> bool:
        """Check if the library database is accessible."""
        if self._available is not None:
            return self._available

        self._available = self.db_path.exists()
        if self._available:
            # Verify we can connect and the tables exist
            try:
                with self._connect() as conn:
                    cursor = conn.execute(
                        "SELECT COUNT(*) FROM documents LIMIT 1"
                    )
                    cursor.fetchone()
            except Exception:
                self._available = False

        return self._available

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Context manager for database connections."""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def search(
        self,
        query: str,
        *,
        limit: int = 20,
        source_filter: list[str] | None = None,
    ) -> list[LibrarySearchResult]:
        """Search the Danish guideline library using FTS5.

        Args:
            query: Search query (natural language or FTS5 syntax)
            limit: Maximum number of results to return
            source_filter: Optional list of source_ids to filter by
                          (e.g., ["vip_regionh", "sst_nkr_nka"])

        Returns:
            List of search results sorted by relevance
        """
        if not self.available():
            return []

        query = query.strip()
        if not query:
            return []

        # Prepare FTS5 query - escape special characters
        fts_query = self._prepare_fts_query(query)

        with self._connect() as conn:
            # Use FTS5 MATCH with weighted BM25 ranking
            # bm25(table, weight_col0, weight_col1, ...) - higher weight = more important
            # Assuming FTS5 columns: doc_id (0), title (1), content (2)
            # Title matches weighted 10x higher than content matches
            sql = """
                SELECT
                    d.doc_id,
                    d.source_id,
                    d.source_name,
                    d.title,
                    d.url,
                    d.local_path,
                    d.publish_year,
                    d.category,
                    d.content_type,
                    bm25(documents_fts, 0.0, 10.0, 1.0) as relevance
                FROM documents_fts
                JOIN documents d ON documents_fts.doc_id = d.doc_id
                WHERE documents_fts MATCH ?
            """
            params: list[Any] = [fts_query]

            if source_filter:
                placeholders = ",".join("?" * len(source_filter))
                sql += f" AND d.source_id IN ({placeholders})"
                params.extend(source_filter)

            sql += " ORDER BY relevance LIMIT ?"
            params.append(limit)

            try:
                cursor = conn.execute(sql, params)
                rows = cursor.fetchall()
            except sqlite3.OperationalError:
                # FTS5 query syntax error - fall back to simple LIKE search
                return self._fallback_search(query, limit=limit, source_filter=source_filter)

            results: list[LibrarySearchResult] = []
            for row in rows:
                local_path = self.library_root.parent / row["local_path"]
                results.append(
                    LibrarySearchResult(
                        doc_id=row["doc_id"],
                        source_id=row["source_id"],
                        source_name=row["source_name"],
                        title=row["title"] or "",
                        url=row["url"] or "",
                        local_path=local_path,
                        publish_year=row["publish_year"],
                        category=row["category"],
                        content_type=row["content_type"],
                        relevance_score=abs(row["relevance"]),  # BM25 returns negative
                    )
                )

            return results

    def _prepare_fts_query(self, query: str, *, phrase_boost: bool = True) -> str:
        """Prepare a natural language query for FTS5 with phrase support.

        Strategy:
        1. Try exact phrase match first (highest relevance)
        2. Fall back to OR-based term matching
        3. Support multi-word phrases in quotes

        Examples:
            "akut hypoglykæmi" -> "akut hypoglykæmi" OR akut OR hypoglykæmi
            akut hypoglykæmi behandling -> "akut hypoglykæmi behandling" OR akut OR hypoglykæmi OR behandling
        """
        import re

        # Remove FTS5 special characters except quotes (for phrase detection)
        # Include / and \ as they can break FTS5 queries
        clean = re.sub(r'[\(\)\[\]\{\}\*\-\+\:\;\,\.\!\?\/\\]', ' ', query)
        clean = clean.strip()

        if not clean:
            return '""'  # Empty query

        # Extract quoted phrases and remaining terms
        quoted_phrases = re.findall(r'"([^"]+)"', clean)
        remaining = re.sub(r'"[^"]*"', '', clean).strip()
        tokens = remaining.split() if remaining else []

        query_parts: list[str] = []

        # If phrase_boost is enabled, add the entire query as a phrase
        if phrase_boost and len(tokens) >= 2:
            # Exact phrase match gets highest priority in BM25
            full_phrase = " ".join(tokens)
            query_parts.append(f'"{full_phrase}"')

        # Add any explicitly quoted phrases
        for phrase in quoted_phrases:
            phrase = phrase.strip()
            if phrase:
                query_parts.append(f'"{phrase}"')

        # Add individual terms with OR (fallback matching)
        for token in tokens:
            token = token.strip()
            if token and len(token) >= 2:  # Skip single-char tokens
                query_parts.append(token)

        if not query_parts:
            return '""'

        # Combine with OR - FTS5 will rank phrase matches higher naturally
        return " OR ".join(query_parts)

    def _fallback_search(
        self,
        query: str,
        *,
        limit: int = 20,
        source_filter: list[str] | None = None,
    ) -> list[LibrarySearchResult]:
        """Fallback LIKE-based search when FTS5 query fails."""
        with self._connect() as conn:
            sql = """
                SELECT
                    doc_id, source_id, source_name, title, url,
                    local_path, publish_year, category, content_type
                FROM documents
                WHERE title LIKE ?
            """
            params: list[Any] = [f"%{query}%"]

            if source_filter:
                placeholders = ",".join("?" * len(source_filter))
                sql += f" AND source_id IN ({placeholders})"
                params.extend(source_filter)

            sql += " LIMIT ?"
            params.append(limit)

            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()

            results: list[LibrarySearchResult] = []
            for i, row in enumerate(rows):
                local_path = self.library_root.parent / row["local_path"]
                results.append(
                    LibrarySearchResult(
                        doc_id=row["doc_id"],
                        source_id=row["source_id"],
                        source_name=row["source_name"],
                        title=row["title"] or "",
                        url=row["url"] or "",
                        local_path=local_path,
                        publish_year=row["publish_year"],
                        category=row["category"],
                        content_type=row["content_type"],
                        relevance_score=1.0 / (i + 1),  # Position-based score
                    )
                )

            return results

    def get_document_count(self) -> int:
        """Get total number of documents in the library."""
        if not self.available():
            return 0

        with self._connect() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM documents")
            return cursor.fetchone()[0]

    def get_source_stats(self) -> dict[str, int]:
        """Get document counts per source."""
        if not self.available():
            return {}

        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT source_id, COUNT(*) as count FROM documents GROUP BY source_id ORDER BY count DESC"
            )
            return {row["source_id"]: row["count"] for row in cursor.fetchall()}
