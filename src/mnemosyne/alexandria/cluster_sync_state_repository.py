"""PostgreSQL repository for cluster delta sync state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class ClusterSyncState:
    """Persisted sync state for a cluster."""

    cluster_id: str
    last_sync_timestamp: datetime
    vector_count_at_sync: int
    profile_hash: str | None
    sync_status: str
    last_error: str | None
    next_sync_scheduled: datetime | None = None


@dataclass
class ClusterSyncStateRepository:
    """Repository for storing cluster sync state in The Ananke."""

    connection: Any

    def ensure_table(self) -> None:
        cursor = self.connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS cluster_sync_state (
                cluster_id TEXT PRIMARY KEY,
                last_sync_timestamp TIMESTAMP NOT NULL,
                vector_count_at_sync INTEGER NOT NULL,
                profile_hash TEXT,
                sync_status TEXT NOT NULL,
                last_error TEXT,
                next_sync_scheduled TIMESTAMP
            )
        """
        )
        self.connection.commit()

    def upsert(self, state: ClusterSyncState) -> None:
        cursor = self.connection.cursor()
        cursor.execute(
            """
            INSERT INTO cluster_sync_state (
                cluster_id,
                last_sync_timestamp,
                vector_count_at_sync,
                profile_hash,
                sync_status,
                last_error,
                next_sync_scheduled
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (cluster_id) DO UPDATE SET
                last_sync_timestamp = EXCLUDED.last_sync_timestamp,
                vector_count_at_sync = EXCLUDED.vector_count_at_sync,
                profile_hash = EXCLUDED.profile_hash,
                sync_status = EXCLUDED.sync_status,
                last_error = EXCLUDED.last_error,
                next_sync_scheduled = EXCLUDED.next_sync_scheduled
        """,
            (
                state.cluster_id,
                state.last_sync_timestamp,
                state.vector_count_at_sync,
                state.profile_hash,
                state.sync_status,
                state.last_error,
                state.next_sync_scheduled,
            ),
        )
        self.connection.commit()

    def get(self, cluster_id: str) -> ClusterSyncState | None:
        cursor = self.connection.cursor()
        cursor.execute(
            """
            SELECT
                cluster_id,
                last_sync_timestamp,
                vector_count_at_sync,
                profile_hash,
                sync_status,
                last_error,
                next_sync_scheduled
            FROM cluster_sync_state
            WHERE cluster_id = %s
        """,
            (cluster_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return ClusterSyncState(
            cluster_id=row[0],
            last_sync_timestamp=row[1],
            vector_count_at_sync=row[2],
            profile_hash=row[3],
            sync_status=row[4],
            last_error=row[5],
            next_sync_scheduled=row[6],
        )

    def list_all(self) -> list[ClusterSyncState]:
        cursor = self.connection.cursor()
        cursor.execute(
            """
            SELECT
                cluster_id,
                last_sync_timestamp,
                vector_count_at_sync,
                profile_hash,
                sync_status,
                last_error,
                next_sync_scheduled
            FROM cluster_sync_state
            ORDER BY cluster_id
        """
        )
        rows = cursor.fetchall()
        return [
            ClusterSyncState(
                cluster_id=row[0],
                last_sync_timestamp=row[1],
                vector_count_at_sync=row[2],
                profile_hash=row[3],
                sync_status=row[4],
                last_error=row[5],
                next_sync_scheduled=row[6],
            )
            for row in rows
        ]
