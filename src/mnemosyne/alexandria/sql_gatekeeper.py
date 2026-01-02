"""SQL Project Gatekeeper for The Ananke."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any

from mnemosyne.argus.scout.monitor_agent import MessageOutbox, ProposalQueue


@dataclass(frozen=True)
class GatekeeperConfig:
    auto_reject_threshold: float = 0.60
    auto_approve_threshold: float = 0.90
    rollback_window_days: int = 7


class SQLProjectGatekeeper:
    """Applies policy before writing projects to The Ananke (PostgreSQL)."""

    def __init__(
        self,
        db_conn,
        proposal_queue: ProposalQueue,
        outbox: MessageOutbox,
        config: GatekeeperConfig | None = None,
    ):
        self._db = db_conn
        self._queue = proposal_queue
        self._outbox = outbox
        self._config = config or GatekeeperConfig()
        self._ensure_schema()

    def process_pending(self) -> dict[str, int]:
        """Process all pending proposals and apply thresholds."""
        counts = {"auto_approved": 0, "awaiting_approval": 0, "rejected": 0}
        pending = self._queue.list_by_status("pending")
        for proposal in pending:
            confidence = float(proposal["confidence_score"])
            discovery_id = proposal["discovery_id"]
            if confidence < self._config.auto_reject_threshold:
                self._queue.update_status(discovery_id, "rejected")
                self._log_audit(discovery_id, approved=False, reason="auto_reject")
                counts["rejected"] += 1
                continue

            if confidence >= self._config.auto_approve_threshold:
                self._approve_proposal(proposal)
                counts["auto_approved"] += 1
                continue

            message_id = f"project_approval:{discovery_id}"
            payload = {
                "type": "project_approval_request",
                "discovery_id": discovery_id,
                "discovery_job_key": proposal["discovery_job_key"],
                "candidate_key": proposal["candidate_key"],
                "confidence": confidence,
                "detected_at": proposal["detected_at"],
                "cluster_ids": proposal["cluster_ids"],
            }
            self._outbox.enqueue("project_approval_request", payload, message_id)
            self._queue.update_status(discovery_id, "awaiting_approval")
            counts["awaiting_approval"] += 1

        return counts

    def approve(self, discovery_id: str) -> int:
        """Approve a proposal and write it to SQL. Returns project_id."""
        proposal = self._queue.get_by_discovery_id(discovery_id)
        if proposal is None:
            raise ValueError(f"Proposal {discovery_id} not found")
        project_id = self._approve_proposal(proposal)
        return project_id

    def reject(self, discovery_id: str, reason: str | None = None) -> None:
        """Reject a proposal without escalation (Monitor handles escalation)."""
        if self._queue.get_by_discovery_id(discovery_id) is None:
            raise ValueError(f"Proposal {discovery_id} not found")
        self._queue.update_status(discovery_id, "rejected")
        self._log_audit(discovery_id, approved=False, reason=reason or "manual_reject")

    def request_rollback(self, project_id: int) -> str:
        """Request rollback; returns confirmation token."""
        if not self._is_within_rollback_window(project_id):
            raise ValueError("Project too old for automated rollback")
        token = sha256(f"{project_id}:{datetime.now(UTC).isoformat()}".encode()).hexdigest()
        with self._db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO gatekeeper_rollback_tokens (project_id, token, requested_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (project_id) DO UPDATE SET
                    token = EXCLUDED.token,
                    requested_at = EXCLUDED.requested_at
                """,
                (project_id, token, datetime.now(UTC)),
            )
        self._db.commit()
        return token

    def confirm_rollback(self, project_id: int, token: str) -> None:
        """Confirm rollback with token; deletes project."""
        with self._db.cursor() as cur:
            cur.execute(
                "SELECT token FROM gatekeeper_rollback_tokens WHERE project_id = %s",
                (project_id,),
            )
            row = cur.fetchone()
            if row is None or row[0] != token:
                raise ValueError("Invalid rollback token")

            cur.execute("DELETE FROM gatekeeper_audit WHERE project_id = %s", (project_id,))
            cur.execute("DELETE FROM projects WHERE id = %s", (project_id,))
            cur.execute(
                "DELETE FROM gatekeeper_rollback_tokens WHERE project_id = %s",
                (project_id,),
            )
        self._db.commit()

    # ---------------- internal helpers ----------------

    def _approve_proposal(self, proposal: dict[str, Any]) -> int:
        discovery_id = proposal["discovery_id"]
        cluster_ids = proposal["cluster_ids"]
        if isinstance(cluster_ids, str):
            try:
                cluster_ids = json.loads(cluster_ids)
            except Exception:
                cluster_ids = [cluster_ids]

        title = proposal.get("title") or f"Project {proposal['candidate_key']}"
        description = proposal.get("description")
        confidence = float(proposal["confidence_score"])

        with self._db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO projects (
                    title,
                    description,
                    discovered_by,
                    discovery_id,
                    cluster_ids,
                    confidence_score,
                    verified_by_user,
                    verified_at,
                    status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (discovery_id) DO NOTHING
                RETURNING id
                """,
                (
                    title,
                    description,
                    "latent_scout",
                    discovery_id,
                    cluster_ids,
                    confidence,
                    True,
                    datetime.now(UTC),
                    "candidate",
                ),
            )
            row = cur.fetchone()
        self._db.commit()

        project_id = row[0] if row else None
        self._queue.update_status(discovery_id, "approved")
        self._log_audit(discovery_id, approved=True, project_id=project_id)
        return project_id or -1

    def _log_audit(
        self,
        discovery_id: str,
        approved: bool,
        reason: str | None = None,
        project_id=None,
    ):
        with self._db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO gatekeeper_audit (
                    approval_id,
                    approved,
                    project_id,
                    decided_at,
                    decided_by,
                    reason
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    discovery_id,
                    approved,
                    project_id,
                    datetime.now(UTC),
                    "gatekeeper",
                    reason,
                ),
            )
        self._db.commit()

    def _is_within_rollback_window(self, project_id: int) -> bool:
        with self._db.cursor() as cur:
            cur.execute("SELECT created_at FROM projects WHERE id = %s", (project_id,))
            row = cur.fetchone()
            if row is None:
                raise ValueError("Project not found")
            created_at = row[0]
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=UTC)
            age = datetime.now(UTC) - created_at
            return age <= timedelta(days=self._config.rollback_window_days)

    def update_project_direct(
        self,
        project_id: int,
        updates: dict[str, Any],
        user_initiated: bool = True,
    ) -> bool:
        """
        Direct project update (bypasses approval for user-initiated changes)

        Used by Project Manager when user provides metadata via Telegram/Obsidian.
        This is safe because the user is DIRECTLY making the change.

        Args:
            project_id: Existing project ID in The Ananke
            updates: Dict of fields to update (importance, urgency, deadline, description, status, work_estimate)
            user_initiated: Must be True (safety check to prevent agent misuse)

        Returns:
            True if update succeeded, False otherwise

        Raises:
            ValueError: If user_initiated=False or trying to update protected fields

        Example:
            success = gatekeeper.update_project_direct(
                project_id=42,
                updates={'importance': 5, 'urgency': 4},
                user_initiated=True
            )
        """
        # Validate user_initiated flag
        if not user_initiated:
            raise ValueError("Direct updates require user_initiated=True flag")

        # Whitelist of allowed fields for direct updates
        allowed_fields = {
            "importance",
            "urgency",
            "deadline",
            "description",
            "status",
            "work_estimate",
        }

        update_fields = set(updates.keys())

        # Check for disallowed fields
        if not update_fields.issubset(allowed_fields):
            disallowed = update_fields - allowed_fields
            raise ValueError(
                f"Cannot update fields via direct update: {disallowed}. "
                f"Allowed fields: {allowed_fields}"
            )

        # Handle empty updates
        if not updates:
            return True

        # Build dynamic UPDATE query
        set_clauses = []
        values = []

        for field, value in updates.items():
            set_clauses.append(f"{field} = %s")
            values.append(value)

        # Always update timestamp
        set_clauses.append("updated_at = %s")
        values.append(datetime.now(UTC))

        values.append(project_id)

        query = f"""
            UPDATE projects
            SET {', '.join(set_clauses)}
            WHERE id = %s
            RETURNING id
        """

        try:
            with self._db.cursor() as cur:
                cur.execute(query, values)
                result = cur.fetchone()

                if not result:
                    # Project not found
                    return False

            self._db.commit()

            # Log to audit trail
            self._log_direct_update(project_id, updates, user_initiated=True)

            return True

        except Exception as e:
            # Rollback on any error
            self._db.rollback()
            return False

    def _log_direct_update(
        self,
        project_id: int,
        updates: dict[str, Any],
        user_initiated: bool,
    ) -> None:
        """
        Audit trail for direct user updates

        Args:
            project_id: Project that was updated
            updates: Dict of fields that were updated
            user_initiated: Whether this was a user-initiated update
        """
        # Convert datetime objects to ISO format strings for JSON serialization
        serializable_updates = {}
        for key, value in updates.items():
            if isinstance(value, datetime):
                serializable_updates[key] = value.isoformat()
            else:
                serializable_updates[key] = value

        with self._db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO gatekeeper_audit (
                    approval_id,
                    action_type,
                    project_id,
                    updates_json,
                    user_initiated,
                    decided_at,
                    decided_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    None,  # No approval_id for direct updates
                    "direct_update",
                    project_id,
                    json.dumps(serializable_updates),
                    user_initiated,
                    datetime.now(UTC),
                    "telegram_user",
                ),
            )
        self._db.commit()

    def _ensure_schema(self) -> None:
        with self._db.cursor() as cur:
            cur.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_discovery_id
                ON projects(discovery_id)
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS gatekeeper_audit (
                    id SERIAL PRIMARY KEY,
                    approval_id TEXT,
                    action_type TEXT DEFAULT 'approval',
                    approved BOOLEAN,
                    project_id INTEGER REFERENCES projects(id),
                    updates_json TEXT,
                    user_initiated BOOLEAN DEFAULT FALSE,
                    decided_at TIMESTAMP DEFAULT NOW(),
                    decided_by TEXT DEFAULT 'gatekeeper',
                    reason TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_gatekeeper_audit_action
                ON gatekeeper_audit(action_type)
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS gatekeeper_rollback_tokens (
                    project_id INTEGER PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
                    token TEXT NOT NULL,
                    requested_at TIMESTAMP NOT NULL
                )
                """
            )
        self._db.commit()
