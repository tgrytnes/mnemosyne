"""
SQLite-based ingestion state tracking.

Tracks which files have been ingested and their modification times
to enable incremental updates (only re-ingest changed files).
"""

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any


class IngestionStateTracker:
    """
    Tracks which files have been ingested into Weaviate.

    Uses SQLite to persist state across restarts. Enables incremental
    ingestion by comparing file modification times.
    """

    def __init__(self, db_path: str = "ingestion_state.db"):
        """
        Initialize state tracker.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row  # Enable dict-like access
        self._create_table()

    def _create_table(self) -> None:
        """Create ingested_files table if it doesn't exist"""
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ingested_files (
                file_path TEXT PRIMARY KEY,
                last_modified TIMESTAMP,
                ingested_at TIMESTAMP,
                chunk_count INTEGER
            )
        """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS semantic_chunk_cache (
                cache_key TEXT PRIMARY KEY,
                boundaries_json TEXT NOT NULL,
                model TEXT,
                min_chunk_size INTEGER,
                max_chunk_size INTEGER,
                created_at TIMESTAMP
            )
        """
        )
        self.conn.commit()

    @staticmethod
    def _coerce_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def mark_ingested(self, file_path: str, modified_time: datetime, chunk_count: int) -> None:
        """
        Mark file as ingested.

        Updates existing record if file was previously ingested.

        Args:
            file_path: Absolute path to file
            modified_time: Last modification time of file
            chunk_count: Number of chunks created from file
        """
        normalized_modified = self._coerce_utc(modified_time)
        self.conn.execute(
            """
            INSERT OR REPLACE INTO ingested_files
            (file_path, last_modified, ingested_at, chunk_count)
            VALUES (?, ?, ?, ?)
        """,
            (
                file_path,
                normalized_modified.isoformat(),
                datetime.now(UTC).isoformat(),
                chunk_count,
            ),
        )
        self.conn.commit()

    def is_ingested(self, file_path: str, modified_time: datetime) -> bool:
        """
        Check if file has been ingested with this modification time.

        Returns False if:
        - File not in database
        - File has been modified since ingestion (modification time newer)

        Args:
            file_path: Absolute path to file
            modified_time: Current modification time of file

        Returns:
            True if file is up-to-date in database, False otherwise
        """
        result = self.conn.execute(
            "SELECT last_modified FROM ingested_files WHERE file_path = ?", (file_path,)
        ).fetchone()

        if not result:
            return False

        # Parse stored modification time
        stored_time = self._coerce_utc(datetime.fromisoformat(result["last_modified"]))
        normalized_modified = self._coerce_utc(modified_time)

        # File needs re-ingestion if it's been modified
        return stored_time >= normalized_modified

    def get_file_info(self, file_path: str) -> dict[str, Any] | None:
        """
        Get ingestion metadata for file.

        Args:
            file_path: Absolute path to file

        Returns:
            Dict with file metadata, or None if not found
        """
        result = self.conn.execute(
            "SELECT * FROM ingested_files WHERE file_path = ?", (file_path,)
        ).fetchone()

        if not result:
            return None

        return dict(result)

    def get_all_files(self) -> list[dict[str, Any]]:
        """
        Get all ingested files.

        Returns:
            List of dicts containing file metadata
        """
        results = self.conn.execute(
            "SELECT * FROM ingested_files ORDER BY ingested_at DESC"
        ).fetchall()

        return [dict(row) for row in results]

    def get_total_chunk_count(self) -> int:
        """
        Count total chunks across all files.

        Returns:
            Total number of chunks ingested
        """
        result = self.conn.execute(
            "SELECT SUM(chunk_count) as total FROM ingested_files"
        ).fetchone()

        return result["total"] or 0

    def cache_semantic_boundaries(
        self,
        cache_key: str,
        boundaries: list[int],
        model: str,
        min_chunk_size: int,
        max_chunk_size: int,
    ) -> None:
        """
        Cache semantic chunking boundaries for reuse.

        Args:
            cache_key: Deterministic key for text + model settings
            boundaries: List of boundary indices
            model: LLM model used
            min_chunk_size: Minimum chunk size used
            max_chunk_size: Maximum chunk size used
        """
        self.conn.execute(
            """
            INSERT OR REPLACE INTO semantic_chunk_cache
            (cache_key, boundaries_json, model, min_chunk_size, max_chunk_size, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                cache_key,
                json.dumps(boundaries),
                model,
                min_chunk_size,
                max_chunk_size,
                datetime.now(UTC).isoformat(),
            ),
        )
        self.conn.commit()

    def get_cached_semantic_boundaries(self, cache_key: str) -> list[int] | None:
        """
        Retrieve cached semantic boundaries by cache key.

        Args:
            cache_key: Deterministic key for text + model settings

        Returns:
            List of boundaries if cached, otherwise None
        """
        result = self.conn.execute(
            "SELECT boundaries_json FROM semantic_chunk_cache WHERE cache_key = ?",
            (cache_key,),
        ).fetchone()

        if not result:
            return None

        return json.loads(result["boundaries_json"])

    def delete_file(self, file_path: str) -> None:
        """
        Remove file from tracking.

        Args:
            file_path: Absolute path to file
        """
        self.conn.execute("DELETE FROM ingested_files WHERE file_path = ?", (file_path,))
        self.conn.commit()

    def clear_all(self) -> None:
        """Remove all ingestion records"""
        self.conn.execute("DELETE FROM ingested_files")
        self.conn.commit()

    def close(self) -> None:
        """Close database connection"""
        self.conn.close()

    def __enter__(self):
        """Context manager support"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close connection on exit"""
        self.close()
