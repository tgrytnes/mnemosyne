"""Minimal monitor agent components used by SQL Gatekeeper."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class DiscoveryRecord:
    discovery_id: str
    discovery_job_key: str
    candidate_key: str
    pattern_type: str
    cluster_ids: list[str]
    confidence_score: float
    detected_at: datetime
    title: str | None = None
    description: str | None = None


class ProposalQueue:
    """SQLite-backed proposal queue for gatekeeper review."""

    def __init__(self, db_path):
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._ensure_table()

    def _ensure_table(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS proposal_queue (
                id INTEGER PRIMARY KEY,
                proposal_id TEXT NOT NULL UNIQUE,
                discovery_id TEXT NOT NULL UNIQUE,
                discovery_job_key TEXT NOT NULL,
                candidate_key TEXT NOT NULL,
                cluster_ids TEXT NOT NULL,
                confidence_score FLOAT NOT NULL,
                detected_at TEXT NOT NULL,
                proposal_hash TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                updated_at TEXT
            )
        """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_proposal_status ON proposal_queue(status)"
        )
        self._conn.commit()

    def upsert(self, discovery: DiscoveryRecord) -> None:
        now = datetime.now(UTC).isoformat()
        proposal_id = discovery.discovery_id
        payload = json.dumps(discovery.cluster_ids, sort_keys=True)
        proposal_hash = proposal_id

        self._conn.execute(
            """
            INSERT INTO proposal_queue (
                proposal_id,
                discovery_id,
                discovery_job_key,
                candidate_key,
                cluster_ids,
                confidence_score,
                detected_at,
                proposal_hash,
                status,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
            ON CONFLICT(discovery_id) DO UPDATE SET
                discovery_job_key = EXCLUDED.discovery_job_key,
                candidate_key = EXCLUDED.candidate_key,
                cluster_ids = EXCLUDED.cluster_ids,
                confidence_score = EXCLUDED.confidence_score,
                detected_at = EXCLUDED.detected_at,
                proposal_hash = EXCLUDED.proposal_hash,
                status = EXCLUDED.status,
                updated_at = EXCLUDED.updated_at
        """,
            (
                proposal_id,
                discovery.discovery_id,
                discovery.discovery_job_key,
                discovery.candidate_key,
                payload,
                discovery.confidence_score,
                discovery.detected_at.isoformat(),
                proposal_hash,
                now,
                now,
            ),
        )
        self._conn.commit()

    def get_by_discovery_id(self, discovery_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM proposal_queue WHERE discovery_id = ?",
            (discovery_id,),
        ).fetchone()
        return dict(row) if row else None

    def update_status(self, discovery_id: str, status: str) -> None:
        now = datetime.now(UTC).isoformat()
        self._conn.execute(
            """
            UPDATE proposal_queue
            SET status = ?, updated_at = ?
            WHERE discovery_id = ?
        """,
            (status, now, discovery_id),
        )
        self._conn.commit()

    def list_by_status(self, status: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM proposal_queue WHERE status = ?",
            (status,),
        ).fetchall()
        return [dict(row) for row in rows]

    def close(self) -> None:
        self._conn.close()


class MessageOutbox:
    """SQLite-backed message outbox."""

    def __init__(self, db_path):
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._ensure_table()

    def _ensure_table(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS message_outbox (
                id INTEGER PRIMARY KEY,
                message_id TEXT NOT NULL UNIQUE,
                message_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT
            )
        """
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_outbox_status ON message_outbox(status)")
        self._conn.commit()

    def enqueue(self, message_type: str, payload: dict, message_id: str) -> None:
        now = datetime.now(UTC).isoformat()
        self._conn.execute(
            """
            INSERT OR IGNORE INTO message_outbox (
                message_id, message_type, payload_json, status, attempts, created_at, updated_at
            )
            VALUES (?, ?, ?, 'pending', 0, ?, ?)
        """,
            (message_id, message_type, json.dumps(payload, sort_keys=True), now, now),
        )
        self._conn.commit()

    def dequeue(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM message_outbox WHERE status = 'pending' ORDER BY id ASC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def close(self) -> None:
        self._conn.close()
