"""Monitor Agent for reconciling discoveries with SQL projects."""

from __future__ import annotations

import json
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
    """Postgres-backed proposal queue for gatekeeper review."""

    def __init__(self, db_conn):
        self._conn = db_conn
        self._ensure_table()

    def _ensure_table(self) -> None:
        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS proposal_queue (
                    id SERIAL PRIMARY KEY,
                    proposal_id TEXT NOT NULL UNIQUE,
                    discovery_id TEXT NOT NULL UNIQUE,
                    discovery_job_key TEXT NOT NULL,
                    candidate_key TEXT NOT NULL,
                    cluster_ids TEXT[] NOT NULL,
                    confidence_score DOUBLE PRECISION NOT NULL,
                    detected_at TIMESTAMPTZ NOT NULL,
                    proposal_hash TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ
                )
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_proposal_status ON proposal_queue(status)"
            )
        self._conn.commit()

    def upsert(self, discovery: DiscoveryRecord) -> None:
        now = datetime.now(UTC)
        proposal_id = discovery.discovery_id
        proposal_hash = sha256(discovery.discovery_id.encode("utf-8")).hexdigest()

        with self._conn.cursor() as cursor:
            cursor.execute(
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
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s, %s)
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
                    discovery.cluster_ids,
                    discovery.confidence_score,
                    discovery.detected_at,
                    proposal_hash,
                    now,
                    now,
                ),
            )
        self._conn.commit()

    def get_by_discovery_id(self, discovery_id: str) -> dict[str, Any] | None:
        with self._conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM proposal_queue WHERE discovery_id = %s",
                (discovery_id,),
            )
            row = cursor.fetchone()
            return _row_to_dict(cursor, row)

    def update_status(self, discovery_id: str, status: str) -> None:
        now = datetime.now(UTC)
        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE proposal_queue
                SET status = %s, updated_at = %s
                WHERE discovery_id = %s
                """,
                (status, now, discovery_id),
            )
        self._conn.commit()

    def list_by_status(self, status: str) -> list[dict[str, Any]]:
        with self._conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM proposal_queue WHERE status = %s ORDER BY id ASC",
                (status,),
            )
            rows = cursor.fetchall()
            return [_row_to_dict(cursor, row) for row in rows if row]

    def close(self) -> None:
        pass


class MonitorStateStore:
    """Postgres-backed state for monitor decisions and cooldowns."""

    def __init__(self, db_conn):
        self._conn = db_conn
        self._ensure_table()

    def _ensure_table(self) -> None:
        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS monitor_state (
                    discovery_id TEXT PRIMARY KEY,
                    asked_at TIMESTAMPTZ,
                    ask_count INTEGER DEFAULT 0,
                    rejected_at TIMESTAMPTZ,
                    rejected_confidence DOUBLE PRECISION,
                    snoozed_until TIMESTAMPTZ,
                    archived_at TIMESTAMPTZ
                )
                """
            )
        self._conn.commit()

    def get_state(self, discovery_id: str) -> dict[str, Any] | None:
        with self._conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM monitor_state WHERE discovery_id = %s",
                (discovery_id,),
            )
            row = cursor.fetchone()
            return _row_to_dict(cursor, row)

    def record_ask(self, discovery_id: str) -> None:
        now = datetime.now(UTC)
        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO monitor_state (discovery_id, asked_at, ask_count)
                VALUES (%s, %s, 1)
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
        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO monitor_state (
                    discovery_id, rejected_at, rejected_confidence, ask_count
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT(discovery_id) DO UPDATE SET
                    rejected_at = EXCLUDED.rejected_at,
                    rejected_confidence = EXCLUDED.rejected_confidence,
                    ask_count = COALESCE(EXCLUDED.ask_count, monitor_state.ask_count)
                """,
                (
                    discovery_id,
                    rejected_at,
                    rejected_confidence,
                    ask_count,
                ),
            )
        self._conn.commit()

    def archive(self, discovery_id: str) -> None:
        now = datetime.now(UTC)
        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE monitor_state
                SET archived_at = %s
                WHERE discovery_id = %s
                """,
                (now, discovery_id),
            )
        self._conn.commit()

    def close(self) -> None:
        pass


class MessageOutbox:
    """Postgres-backed message outbox."""

    def __init__(self, db_conn):
        self._conn = db_conn
        self._ensure_table()

    def _ensure_table(self) -> None:
        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS message_outbox (
                    id SERIAL PRIMARY KEY,
                    message_id TEXT NOT NULL UNIQUE,
                    message_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    last_attempted_at TIMESTAMPTZ
                )
                """
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_outbox_status ON message_outbox(status)")
        self._conn.commit()

    def enqueue(self, message_type: str, payload: dict[str, Any], message_id: str) -> None:
        payload_json = json.dumps(payload, default=str)
        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO message_outbox (
                    message_id, message_type, payload_json
                ) VALUES (%s, %s, %s)
                ON CONFLICT (message_id) DO NOTHING
                """,
                (message_id, message_type, payload_json),
            )
        self._conn.commit()

    def fetch_pending(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM message_outbox
                WHERE status = 'pending'
                ORDER BY id ASC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            return [_row_to_dict(cursor, row) for row in rows if row]

    def dequeue(self, limit: int = 100) -> list[dict[str, Any]]:
        """Alias for fetch_pending() to maintain API compatibility."""
        return self.fetch_pending(limit=limit)

    def close(self) -> None:
        pass


def _row_to_dict(cursor, row: tuple | None) -> dict[str, Any] | None:
    if row is None:
        return None
    columns = [desc[0] for desc in cursor.description]
    return {column: value for column, value in zip(columns, row)}


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
        self._ensure_table()

    def _ensure_table(self) -> None:
        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    discovered_by TEXT,
                    discovery_id TEXT,
                    cluster_ids TEXT[],
                    confidence_score FLOAT,
                    verified_by_user BOOLEAN DEFAULT FALSE,
                    verified_at TIMESTAMP,
                    status TEXT DEFAULT 'candidate',
                    deadline TIMESTAMP,
                    pressure_score FLOAT,
                    importance INTEGER CHECK (importance >= 1 AND importance <= 5),
                    urgency INTEGER CHECK (urgency >= 1 AND urgency <= 5),
                    work_estimate INTEGER,
                    obsidian_file_path TEXT,
                    last_synced_to_obsidian TIMESTAMP,
                    last_synced_from_obsidian TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
                """
            )
            cursor.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_discovery_id
                ON projects(discovery_id)
                """
            )
        self._conn.commit()

    def exists_by_discovery_id(self, discovery_id: str) -> bool:
        with self._conn.cursor() as cursor:
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
        self._escalate_rejections()
        self._reconcile_discoveries()

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

    if not discovery_id or not discovery_job_key or not candidate_key:
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
