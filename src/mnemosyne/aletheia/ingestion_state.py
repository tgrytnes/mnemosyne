"""
SQLite-based ingestion state tracking.

Tracks which files have been ingested and their modification times
to enable incremental updates (only re-ingest changed files).
"""

import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path


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
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS ingested_files (
                file_path TEXT PRIMARY KEY,
                last_modified TIMESTAMP,
                ingested_at TIMESTAMP,
                chunk_count INTEGER
            )
        """)
        self.conn.commit()

    def mark_ingested(
        self,
        file_path: str,
        modified_time: datetime,
        chunk_count: int
    ) -> None:
        """
        Mark file as ingested.

        Updates existing record if file was previously ingested.

        Args:
            file_path: Absolute path to file
            modified_time: Last modification time of file
            chunk_count: Number of chunks created from file
        """
        self.conn.execute("""
            INSERT OR REPLACE INTO ingested_files
            (file_path, last_modified, ingested_at, chunk_count)
            VALUES (?, ?, ?, ?)
        """, (
            file_path,
            modified_time.isoformat(),
            datetime.now().isoformat(),
            chunk_count,
        ))
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
            "SELECT last_modified FROM ingested_files WHERE file_path = ?",
            (file_path,)
        ).fetchone()

        if not result:
            return False

        # Parse stored modification time
        stored_time = datetime.fromisoformat(result["last_modified"])

        # File needs re-ingestion if it's been modified
        return stored_time >= modified_time

    def get_file_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Get ingestion metadata for file.

        Args:
            file_path: Absolute path to file

        Returns:
            Dict with file metadata, or None if not found
        """
        result = self.conn.execute(
            "SELECT * FROM ingested_files WHERE file_path = ?",
            (file_path,)
        ).fetchone()

        if not result:
            return None

        return dict(result)

    def get_all_files(self) -> List[Dict[str, Any]]:
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

    def delete_file(self, file_path: str) -> None:
        """
        Remove file from tracking.

        Args:
            file_path: Absolute path to file
        """
        self.conn.execute(
            "DELETE FROM ingested_files WHERE file_path = ?",
            (file_path,)
        )
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
