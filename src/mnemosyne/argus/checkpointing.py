"""Checkpointed state storage for LangGraph workflows."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field


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
    updated_at: datetime


class CheckpointStore:
    """SQLite-backed checkpoint store for ResearchState."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._ensure_table()

    def _ensure_table(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS checkpoints (
                query_id TEXT PRIMARY KEY,
                state_json TEXT NOT NULL,
                updated_at TIMESTAMP NOT NULL
            )
        """
        )
        self._conn.commit()

    def save(self, state: ResearchState) -> None:
        payload = json.dumps(state.model_dump(mode="json"))
        updated_at = datetime.utcnow().isoformat()
        self._conn.execute(
            """
            INSERT OR REPLACE INTO checkpoints (query_id, state_json, updated_at)
            VALUES (?, ?, ?)
        """,
            (state.query_id, payload, updated_at),
        )
        self._conn.commit()

    def load(self, query_id: str) -> ResearchState | None:
        row = self._conn.execute(
            "SELECT state_json FROM checkpoints WHERE query_id = ?",
            (query_id,),
        ).fetchone()
        if not row:
            return None
        data = json.loads(row["state_json"])
        return ResearchState.model_validate(data)

    def list_checkpoints(self) -> list[CheckpointInfo]:
        rows = self._conn.execute(
            "SELECT query_id, updated_at FROM checkpoints ORDER BY updated_at DESC"
        ).fetchall()
        return [
            CheckpointInfo(
                query_id=row["query_id"],
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
            for row in rows
        ]

    def delete(self, query_id: str) -> None:
        self._conn.execute("DELETE FROM checkpoints WHERE query_id = ?", (query_id,))
        self._conn.commit()

    def cleanup(self, max_age_days: int) -> int:
        cutoff = datetime.utcnow() - timedelta(days=max_age_days)
        cursor = self._conn.execute(
            "DELETE FROM checkpoints WHERE updated_at < ?",
            (cutoff.isoformat(),),
        )
        self._conn.commit()
        return cursor.rowcount

    def close(self) -> None:
        self._conn.close()
