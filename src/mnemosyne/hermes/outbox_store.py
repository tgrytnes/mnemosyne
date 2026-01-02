from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path


class OutboxStore:
    def __init__(self, db_path: str):
        self._db_path = Path(db_path)
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        cursor = self._conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS message_outbox (
                message_id TEXT PRIMARY KEY,
                message_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                expects_response INTEGER NOT NULL DEFAULT 0,
                originating_agent TEXT,
                context_id TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                chat_id TEXT,
                telegram_message_id INTEGER,
                response_json TEXT,
                response_received_at TEXT,
                last_error TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                delivered_at TEXT
            )
            """
        )
        self._conn.commit()

    def enqueue(
        self,
        *,
        message_id: str,
        message_type: str,
        payload_json: dict,
        expects_response: bool,
        originating_agent: str,
        context_id: str,
    ) -> None:
        cursor = self._conn.cursor()
        cursor.execute(
            """
            INSERT INTO message_outbox (
                message_id,
                message_type,
                payload_json,
                expects_response,
                originating_agent,
                context_id,
                status
            ) VALUES (?, ?, ?, ?, ?, ?, 'pending')
            """,
            (
                message_id,
                message_type,
                json.dumps(payload_json),
                1 if expects_response else 0,
                originating_agent,
                context_id,
            ),
        )
        self._conn.commit()

    def fetch_pending(self, *, limit: int = 10) -> list[sqlite3.Row]:
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT * FROM message_outbox
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (limit,),
        )
        return cursor.fetchall()

    def mark_delivered(self, *, message_id: str, chat_id: str, telegram_message_id: int) -> None:
        cursor = self._conn.cursor()
        cursor.execute(
            """
            UPDATE message_outbox
            SET status = 'delivered',
                chat_id = ?,
                telegram_message_id = ?,
                delivered_at = ?
            WHERE message_id = ?
            """,
            (chat_id, telegram_message_id, datetime.utcnow().isoformat(), message_id),
        )
        self._conn.commit()

    def mark_failed(self, *, message_id: str, error: str) -> None:
        cursor = self._conn.cursor()
        cursor.execute(
            """
            UPDATE message_outbox
            SET status = 'failed',
                last_error = ?
            WHERE message_id = ?
            """,
            (error, message_id),
        )
        self._conn.commit()

    def record_response_by_message_id(self, *, message_id: str, response_json: dict) -> None:
        cursor = self._conn.cursor()
        cursor.execute(
            """
            UPDATE message_outbox
            SET response_json = ?,
                response_received_at = ?
            WHERE message_id = ?
            """,
            (json.dumps(response_json), datetime.utcnow().isoformat(), message_id),
        )
        self._conn.commit()

    def record_response_from_reply(
        self, *, chat_id: str, reply_to_message_id: int, response_json: dict
    ) -> bool:
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT message_id FROM message_outbox
            WHERE chat_id = ? AND telegram_message_id = ?
            """,
            (chat_id, reply_to_message_id),
        )
        row = cursor.fetchone()
        if not row:
            return False
        self.record_response_by_message_id(
            message_id=row["message_id"],
            response_json=response_json,
        )
        return True

    def get_by_message_id(self, message_id: str) -> sqlite3.Row:
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT * FROM message_outbox WHERE message_id = ?",
            (message_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise ValueError(f"Unknown message_id {message_id}")
        return row

    def has_reply_mapping(self, chat_id: str, reply_to_message_id: int) -> bool:
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT 1 FROM message_outbox
            WHERE chat_id = ? AND telegram_message_id = ?
            """,
            (chat_id, reply_to_message_id),
        )
        return cursor.fetchone() is not None
