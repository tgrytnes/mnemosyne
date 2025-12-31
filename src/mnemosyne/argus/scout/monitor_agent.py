"""Monitor Agent for reconciling discoveries with SQL projects."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any

from weaviate.classes.query import Filter

from mnemosyne.alexandria.weaviate_schema import Discoveries


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


@dataclass(frozen=True)
class MonitorConfig:
    confidence_threshold: float = 0.7
    scan_limit: int = 200
    cooldown_days: int = 14
    max_asks: int = 3
    confidence_delta: float = 0.15


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
        proposal_hash = sha256(discovery.discovery_id.encode("utf-8")).hexdigest()

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
                status = 'pending',
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


class MonitorStateStore:
    """SQLite-backed state for monitor decisions and cooldowns."""

    def __init__(self, db_path):
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._ensure_table()

    def _ensure_table(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS monitor_state (
                discovery_id TEXT PRIMARY KEY,
                asked_at TEXT,
                ask_count INTEGER DEFAULT 0,
                rejected_at TEXT,
                rejected_confidence FLOAT,
                snoozed_until TEXT,
                archived_at TEXT
            )
        """
        )
        self._conn.commit()

    def get_state(self, discovery_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM monitor_state WHERE discovery_id = ?",
            (discovery_id,),
        ).fetchone()
        return dict(row) if row else None

    def record_ask(self, discovery_id: str) -> None:
        now = datetime.now(UTC).isoformat()
        self._conn.execute(
            """
            INSERT INTO monitor_state (discovery_id, asked_at, ask_count)
            VALUES (?, ?, 1)
            ON CONFLICT(discovery_id) DO UPDATE SET
                asked_at = EXCLUDED.asked_at,
                ask_count = monitor_state.ask_count + 1
        """,
            (discovery_id, now),
        )
        self._conn.commit()

    def record_rejection(
        self,
        discovery_id: str,
        rejected_at: datetime,
        rejected_confidence: float,
        ask_count: int | None = None,
    ) -> None:
        values = {
            "discovery_id": discovery_id,
            "rejected_at": rejected_at.isoformat(),
            "rejected_confidence": rejected_confidence,
            "ask_count": ask_count,
        }

        self._conn.execute(
            """
            INSERT INTO monitor_state (
                discovery_id, rejected_at, rejected_confidence, ask_count
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(discovery_id) DO UPDATE SET
                rejected_at = EXCLUDED.rejected_at,
                rejected_confidence = EXCLUDED.rejected_confidence,
                ask_count = COALESCE(EXCLUDED.ask_count, monitor_state.ask_count)
        """,
            (
                values["discovery_id"],
                values["rejected_at"],
                values["rejected_confidence"],
                values["ask_count"],
            ),
        )
        self._conn.commit()

    def archive(self, discovery_id: str) -> None:
        now = datetime.now(UTC).isoformat()
        self._conn.execute(
            """
            UPDATE monitor_state
            SET archived_at = ?
            WHERE discovery_id = ?
        """,
            (now, discovery_id),
        )
        self._conn.commit()

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
                last_error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_attempted_at TIMESTAMP
            )
        """
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_outbox_status ON message_outbox(status)")
        self._conn.commit()

    def enqueue(self, message_type: str, payload: dict[str, Any], message_id: str) -> None:
        payload_json = json.dumps(payload, default=str)
        self._conn.execute(
            """
            INSERT OR IGNORE INTO message_outbox (
                message_id, message_type, payload_json
            ) VALUES (?, ?, ?)
        """,
            (message_id, message_type, payload_json),
        )
        self._conn.commit()

    def fetch_pending(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT * FROM message_outbox
            WHERE status = 'pending'
            ORDER BY id ASC
            LIMIT ?
        """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def close(self) -> None:
        self._conn.close()


class WeaviateDiscoveryReader:
    """Loads discovery records from Weaviate."""

    def __init__(self, client):
        self._client = client
        self._collection = client.collections.get(Discoveries.collection_name)

    def fetch_project_candidates(self, threshold: float, limit: int) -> list[DiscoveryRecord]:
        filters = Filter.by_property("patternType").equal("project_candidate") & Filter.by_property(
            "confidenceScore"
        ).greater_or_equal(threshold)
        response = self._collection.query.fetch_objects(filters=filters, limit=limit)
        records: list[DiscoveryRecord] = []
        for obj in response.objects:
            record = _record_from_properties(obj.properties)
            if record is None:
                continue
            records.append(record)
        return records


class PostgresProjectRepository:
    """Reads existing projects from The Ananke."""

    def __init__(self, connection):
        self._conn = connection

    def exists_by_discovery_id(self, discovery_id: str) -> bool:
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT id FROM projects WHERE discovery_id = %s",
            (discovery_id,),
        )
        return cursor.fetchone() is not None


class MonitorAgent:
    """Coordinates discovery reconciliation and escalations."""

    def __init__(
        self,
        discovery_reader,
        project_repository,
        proposal_queue: ProposalQueue,
        state_store: MonitorStateStore,
        outbox: MessageOutbox,
        config: MonitorConfig | None = None,
    ):
        self._reader = discovery_reader
        self._projects = project_repository
        self._queue = proposal_queue
        self._state = state_store
        self._outbox = outbox
        self._config = config or MonitorConfig()

    def run(self) -> None:
        self._reconcile_discoveries()
        self._escalate_rejections()

    def _reconcile_discoveries(self) -> None:
        discoveries = self._reader.fetch_project_candidates(
            threshold=self._config.confidence_threshold,
            limit=self._config.scan_limit,
        )

        for discovery in discoveries:
            if self._projects.exists_by_discovery_id(discovery.discovery_id):
                continue
            if not self._should_propose(discovery):
                continue
            self._queue.upsert(discovery)
            self._state.record_ask(discovery.discovery_id)

    def _should_propose(self, discovery: DiscoveryRecord) -> bool:
        state = self._state.get_state(discovery.discovery_id)
        if state is None:
            return True

        if state.get("archived_at"):
            return False

        ask_count = state.get("ask_count") or 0
        if ask_count >= self._config.max_asks:
            self._state.archive(discovery.discovery_id)
            return False

        snoozed_until = _parse_datetime(state.get("snoozed_until"))
        if snoozed_until and snoozed_until > datetime.now(UTC):
            return False

        rejected_at = _parse_datetime(state.get("rejected_at"))
        rejected_confidence = state.get("rejected_confidence")
        if rejected_at and rejected_confidence is not None:
            cooldown = timedelta(days=self._config.cooldown_days)
            if datetime.now(UTC) - rejected_at < cooldown:
                return False
            if discovery.confidence_score < rejected_confidence + self._config.confidence_delta:
                return False

        return True

    def _escalate_rejections(self) -> None:
        rejected = self._queue.list_by_status("rejected")
        for proposal in rejected:
            discovery_id = proposal["discovery_id"]
            message_id = f"proposal_escalation:{discovery_id}"
            payload = {
                "type": "proposal_escalation",
                "proposal_id": proposal["proposal_id"],
                "discovery_id": discovery_id,
                "discovery_job_key": proposal["discovery_job_key"],
                "candidate_key": proposal["candidate_key"],
                "confidence": proposal["confidence_score"],
                "detected_at": proposal["detected_at"],
            }
            self._outbox.enqueue("proposal_escalation", payload, message_id)
            self._queue.update_status(discovery_id, "escalated")
            self._state.record_rejection(
                discovery_id=discovery_id,
                rejected_at=datetime.now(UTC),
                rejected_confidence=float(proposal["confidence_score"]),
                ask_count=int(proposal.get("ask_count") or 1),
            )


def _record_from_properties(properties: dict[str, Any]) -> DiscoveryRecord | None:
    try:
        discovery_id = properties["discoveryId"]
        discovery_job_key = properties["discoveryJobKey"]
        candidate_key = properties["candidateKey"]
        pattern_type = properties["patternType"]
        cluster_ids = properties.get("clusterIds") or []
        confidence_score = float(properties.get("confidenceScore") or 0.0)
        detected_at = _parse_datetime(properties.get("detectedAt")) or datetime.now(UTC)
    except KeyError:
        return None

    return DiscoveryRecord(
        discovery_id=discovery_id,
        discovery_job_key=discovery_job_key,
        candidate_key=candidate_key,
        pattern_type=pattern_type,
        cluster_ids=[str(item) for item in cluster_ids],
        confidence_score=confidence_score,
        detected_at=detected_at,
        title=properties.get("title"),
        description=properties.get("description"),
    )


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None
