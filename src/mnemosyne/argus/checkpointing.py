"""Checkpointed state storage for LangGraph workflows."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field


DEFAULT_MAX_AGE_DAYS = 30


class ResearchState(BaseModel):
    """Serializable state for a research workflow."""

    query_id: str = Field(min_length=1)
    original_query: str
    current_node: str
    conversation_history: list[dict[str, Any]] = Field(default_factory=list)
    intermediate_results: list[dict[str, Any]] = Field(default_factory=list)
    search_results: list[dict[str, Any]] = Field(default_factory=list)
    synthesis_draft: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


@dataclass
class CheckpointInfo:
    """Summary metadata for stored checkpoints."""

    query_id: str
    current_node: str
    updated_at: datetime


class CheckpointStore:
    """SQLite-backed checkpoint store for ResearchState."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.table_name = "mnemosyne_checkpoints"
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._ensure_table()

    def _ensure_table(self) -> None:
        self._conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                checkpoint_id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_id TEXT NOT NULL,
                current_node TEXT NOT NULL,
                state_json TEXT NOT NULL,
                updated_at TIMESTAMP NOT NULL
            )
        """
        )
        self._conn.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_query_id "
            f"ON {self.table_name} (query_id)"
        )
        self._conn.commit()

    def save(self, state: ResearchState) -> None:
        payload = json.dumps(state.model_dump(mode="json"))
        updated_at = datetime.utcnow().isoformat()
        self._conn.execute(
            f"""
            INSERT INTO {self.table_name} (query_id, current_node, state_json, updated_at)
            VALUES (?, ?, ?, ?)
        """,
            (state.query_id, state.current_node, payload, updated_at),
        )
        self._conn.commit()

    def load(self, query_id: str) -> ResearchState | None:
        row = self._conn.execute(
            f"""
            SELECT state_json
            FROM {self.table_name}
            WHERE query_id = ?
            ORDER BY updated_at DESC
            LIMIT 1
        """,
            (query_id,),
        ).fetchone()
        if not row:
            return None
        data = json.loads(row["state_json"])
        return ResearchState.model_validate(data)

    def list_checkpoints(self) -> list[CheckpointInfo]:
        rows = self._conn.execute(
            f"""
            SELECT query_id, current_node, updated_at
            FROM (
                SELECT query_id, current_node, updated_at,
                       ROW_NUMBER() OVER (
                           PARTITION BY query_id
                           ORDER BY updated_at DESC
                       ) AS rn
                FROM {self.table_name}
            )
            WHERE rn = 1
            ORDER BY updated_at DESC
        """
        ).fetchall()
        return [
            CheckpointInfo(
                query_id=row["query_id"],
                current_node=row["current_node"],
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
            for row in rows
        ]

    def list_query_history(self, query_id: str) -> list[CheckpointInfo]:
        rows = self._conn.execute(
            f"""
            SELECT query_id, current_node, updated_at
            FROM {self.table_name}
            WHERE query_id = ?
            ORDER BY updated_at ASC
        """,
            (query_id,),
        ).fetchall()
        return [
            CheckpointInfo(
                query_id=row["query_id"],
                current_node=row["current_node"],
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
            for row in rows
        ]

    def delete(self, query_id: str) -> None:
        self._conn.execute(
            f"DELETE FROM {self.table_name} WHERE query_id = ?",
            (query_id,),
        )
        self._conn.commit()

    def cleanup(self, max_age_days: int) -> int:
        cutoff = datetime.utcnow() - timedelta(days=max_age_days)
        cursor = self._conn.execute(
            f"DELETE FROM {self.table_name} WHERE updated_at < ?",
            (cutoff.isoformat(),),
        )
        self._conn.commit()
        return cursor.rowcount

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> CheckpointStore:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


class CheckpointCleanupJob:
    """Scheduled cleanup for checkpoint persistence."""

    def __init__(self, store: CheckpointStore, max_age_days: int = DEFAULT_MAX_AGE_DAYS):
        self.store = store
        self.max_age_days = max_age_days

    def run(self) -> int:
        return self.store.cleanup(self.max_age_days)
