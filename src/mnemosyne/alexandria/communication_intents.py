"""PM intent queue for centralized user communication (Story 029)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class PMIntent:
    id: int
    message_id: str
    intent_type: str
    originating_agent: str | None
    context_id: str | None
    payload: dict[str, Any]
    expects_response: bool
    status: str
    created_at: datetime | None
    handled_at: datetime | None


class PMIntentQueue:
    """Postgres-backed queue of PM communication intents."""

    def __init__(self, db_conn) -> None:
        self._db = db_conn
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with self._db.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS pm_intent_queue (
                    id SERIAL PRIMARY KEY,
                    message_id TEXT NOT NULL UNIQUE,
                    intent_type TEXT NOT NULL,
                    originating_agent TEXT,
                    context_id TEXT,
                    payload_json TEXT NOT NULL,
                    expects_response BOOLEAN DEFAULT FALSE,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT NOW(),
                    handled_at TIMESTAMP
                )
                """)
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_pm_intent_status ON pm_intent_queue(status)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_pm_intent_created ON pm_intent_queue(created_at)"
            )
        self._db.commit()

    def enqueue_intent(
        self,
        intent_type: str,
        payload: dict[str, Any],
        message_id: str,
        originating_agent: str | None = None,
        context_id: str | None = None,
        expects_response: bool = False,
    ) -> str:
        with self._db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO pm_intent_queue (
                    message_id,
                    intent_type,
                    originating_agent,
                    context_id,
                    payload_json,
                    expects_response
                ) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (message_id) DO NOTHING
                """,
                (
                    message_id,
                    intent_type,
                    originating_agent,
                    context_id,
                    json.dumps(payload),
                    expects_response,
                ),
            )
        self._db.commit()
        return message_id

    def list_pending(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._db.cursor() as cur:
            cur.execute(
                """
                SELECT id, message_id, intent_type, originating_agent, context_id,
                       payload_json, expects_response, status, created_at, handled_at
                FROM pm_intent_queue
                WHERE status = 'pending'
                ORDER BY created_at ASC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall() or []
            columns = [desc[0] for desc in cur.description]

        intents = []
        for row in rows:
            data = dict(zip(columns, row))
            intents.append(
                {
                    "id": data["id"],
                    "message_id": data["message_id"],
                    "intent_type": data["intent_type"],
                    "originating_agent": data["originating_agent"],
                    "context_id": data["context_id"],
                    "payload": json.loads(data["payload_json"]),
                    "expects_response": data["expects_response"],
                    "status": data["status"],
                    "created_at": data["created_at"],
                    "handled_at": data["handled_at"],
                }
            )
        return intents

    def mark_handled(self, message_id: str) -> None:
        with self._db.cursor() as cur:
            cur.execute(
                """
                UPDATE pm_intent_queue
                SET status = 'handled', handled_at = %s
                WHERE message_id = %s
                """,
                (datetime.utcnow(), message_id),
            )
        self._db.commit()
