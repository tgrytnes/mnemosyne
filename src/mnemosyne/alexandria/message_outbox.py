"""
Message Outbox - Transport-agnostic message queue for agent-to-user communication

Story 027: Message Outbox Relay (Nexus Middle-Man)

This module provides a SQLite-based message queue that decouples agents from
the Telegram delivery mechanism. Agents enqueue messages, Hermes consumes them,
and user responses route back to the originating agent.

Key Features:
- Idempotent message enqueuing (INSERT OR IGNORE by message_id)
- State machine: pending → delivered/awaiting_response → delivered
- Response routing back to originating agent
- Retry logic with exponential backoff (max 3 attempts)
- Long-term audit history
"""

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass
class OutboxMessage:
    """
    Represents a message in the outbox queue

    Attributes:
        id: Auto-increment primary key
        message_id: Unique message identifier (for idempotency)
        message_type: Type of message (notification, approval_request, escalation, question)
        originating_agent: Which agent sent this message (project_manager, monitor, gatekeeper)
        context_id: Context for routing responses (e.g., 'project:42', 'discovery:disco_001')
        payload: Message content and metadata
        status: Current state (pending, delivered, failed, awaiting_response)
        expects_response: True if this is an interactive question
        response_received_at: When user responded (if expects_response=True)
        response: User's response data (if expects_response=True)
        attempts: Number of delivery attempts
        last_error: Most recent delivery error
        created_at: When message was enqueued
        last_attempted_at: Most recent delivery attempt timestamp
        delivered_at: When successfully delivered to user
        chat_id: Telegram chat identifier (when delivered)
        telegram_message_id: Telegram message ID (when delivered)
        next_attempt_at: Next retry timestamp (for backoff)
    """

    id: int
    message_id: str
    message_type: str
    originating_agent: str | None
    context_id: str | None
    payload: dict[str, Any]
    status: str
    expects_response: bool
    response_received_at: datetime | None
    response: dict[str, Any] | None
    attempts: int
    last_error: str | None
    created_at: datetime
    last_attempted_at: datetime | None
    delivered_at: datetime | None
    chat_id: str | None
    telegram_message_id: int | None
    next_attempt_at: datetime | None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "OutboxMessage":
        """
        Create OutboxMessage from database row

        Args:
            row: Database row as dict (from sqlite3.Row)

        Returns:
            OutboxMessage instance
        """
        return cls(
            id=row["id"],
            message_id=row["message_id"],
            message_type=row["message_type"],
            originating_agent=row["originating_agent"],
            context_id=row["context_id"],
            payload=json.loads(row["payload_json"]),
            status=row["status"],
            expects_response=bool(row["expects_response"]),
            response_received_at=_parse_timestamp(row["response_received_at"]),
            response=json.loads(row["response_json"]) if row["response_json"] else None,
            attempts=row["attempts"],
            last_error=row["last_error"],
            created_at=_parse_timestamp(row["created_at"]),
            last_attempted_at=_parse_timestamp(row["last_attempted_at"]),
            delivered_at=_parse_timestamp(row["delivered_at"]),
            chat_id=row.get("chat_id"),
            telegram_message_id=row.get("telegram_message_id"),
            next_attempt_at=_parse_timestamp(row.get("next_attempt_at")),
        )


class MessageOutbox:
    """
    Queue for agent → user communication with response routing

    Usage (Producer - Agent side):
        outbox = MessageOutbox(db_conn)

        # Simple notification
        outbox.send_message("Project approved!", agent="gatekeeper")

        # Interactive question
        outbox.enqueue(
            message_type='question',
            payload={'text': 'How important is this? (1-5)'},
            originating_agent='project_manager',
            context_id='project:42',
            expects_response=True
        )

    Usage (Consumer - Hermes side):
        outbox = MessageOutbox(db_conn)

        # Fetch pending messages
        pending = outbox.fetch_pending(limit=50)

        for msg in pending:
            try:
                telegram_bot.send_message(msg.payload['text'])
                outbox.mark_delivered(msg.message_id)
            except Exception as e:
                outbox.mark_failed(msg.message_id, str(e))

        # When user responds
        agent = outbox.record_response(
            context_id='project:42',
            response_data={'field': 'importance', 'value': 5}
        )

        # Route to agent
        if agent == 'project_manager':
            project_manager.handle_response(...)
    """

    # Valid message types
    VALID_MESSAGE_TYPES = {"notification", "approval_request", "escalation", "question"}

    # Max delivery attempts before marking as failed
    MAX_ATTEMPTS = 3

    def __init__(self, db: sqlite3.Connection | str | Path):
        """
        Initialize MessageOutbox

        Args:
            db: SQLite database connection or path to database file
        """
        if isinstance(db, (str, Path)):
            self._db_path = str(db)
            self.db = sqlite3.connect(self._db_path)
            self._owns_connection = True
            self._ensure_schema()
        else:
            self.db = db
            self._db_path = None
            self._owns_connection = False

        self.db.row_factory = sqlite3.Row

    def _ensure_schema(self):
        """Create message_outbox table and indexes if they don't exist."""
        cursor = self.db.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS message_outbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT NOT NULL UNIQUE,
                message_type TEXT NOT NULL,
                originating_agent TEXT,
                context_id TEXT,
                payload_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                expects_response BOOLEAN DEFAULT FALSE,
                response_received_at TIMESTAMP,
                response_json TEXT,
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_attempted_at TIMESTAMP,
                delivered_at TIMESTAMP,
                chat_id TEXT,
                telegram_message_id INTEGER,
                next_attempt_at TIMESTAMP,
                CHECK (message_type IN (
                    'notification', 'approval_request', 'escalation', 'question'
                )),
                CHECK (status IN (
                    'pending', 'delivered', 'failed', 'awaiting_response'
                )),
                CHECK (attempts >= 0)
            )
        """
        )

        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_message_outbox_message_id ON message_outbox(message_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_message_outbox_status ON message_outbox(status)"
        )
        cursor.execute(
            """CREATE INDEX IF NOT EXISTS idx_message_outbox_agent
            ON message_outbox(originating_agent)"""
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_message_outbox_context ON message_outbox(context_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_message_outbox_created ON message_outbox(created_at)"
        )
        cursor.execute(
            """CREATE INDEX IF NOT EXISTS idx_message_outbox_response_routing
            ON message_outbox(context_id, expects_response, status)"""
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_message_outbox_chat ON message_outbox(chat_id)"
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_message_outbox_next_attempt
            ON message_outbox(next_attempt_at)
            """
        )

        self._ensure_column("chat_id", "TEXT")
        self._ensure_column("telegram_message_id", "INTEGER")
        self._ensure_column("next_attempt_at", "TIMESTAMP")

        self.db.commit()

    def _ensure_column(self, name: str, column_type: str) -> None:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise ValueError("invalid column name")
        if not re.fullmatch(r"[A-Za-z0-9_()\\s]+", column_type):
            raise ValueError("invalid column type")
        cursor = self.db.cursor()
        cursor.execute("PRAGMA table_info(message_outbox)")
        existing = {row[1] for row in cursor.fetchall()}
        if name in existing:
            return
        cursor.execute(f"ALTER TABLE message_outbox ADD COLUMN {name} {column_type}")
        self.db.commit()

    def enqueue(
        self,
        message_type: str,
        payload: dict,
        message_id: str | None = None,
        originating_agent: str | None = None,
        context_id: str | None = None,
        expects_response: bool = False,
    ) -> str:
        """
        Enqueue a message for delivery to user

        Args:
            message_type: Type of message (notification, approval_request, escalation, question)
            payload: Message content and metadata (must contain at least one key)
            message_id: Optional ID for idempotency (auto-generated if None)
            originating_agent: Which agent sent this (project_manager, monitor, gatekeeper, etc.)
            context_id: Context for routing responses (e.g., 'project:42', 'discovery:disco_001')
            expects_response: True if this is an interactive question expecting user response

        Returns:
            message_id (either provided or auto-generated)

        Raises:
            ValueError: If payload is empty or message_type is invalid
        """
        # Validate message type
        if message_type not in self.VALID_MESSAGE_TYPES:
            raise ValueError(
                f"Invalid message_type: {message_type}. "
                f"Must be one of: {', '.join(self.VALID_MESSAGE_TYPES)}"
            )

        # Enforce PM-centralized messaging
        if originating_agent and originating_agent != "project_manager":
            raise ValueError("originating_agent must be project_manager for user messages")

        # Validate payload
        if not payload:
            raise ValueError("payload cannot be empty")

        # Generate message_id if not provided
        if not message_id:
            message_id = f"{message_type}:{context_id or 'none'}:{uuid4()}"

        cursor = self.db.cursor()

        # INSERT OR IGNORE for idempotency
        cursor.execute(
            """
            INSERT OR IGNORE INTO message_outbox (
                message_id,
                message_type,
                originating_agent,
                context_id,
                payload_json,
                expects_response
            ) VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                message_id,
                message_type,
                originating_agent,
                context_id,
                json.dumps(payload),
                expects_response,
            ),
        )

        self.db.commit()
        return message_id

    def send_message(
        self, text: str, agent: str | None = None, context_id: str | None = None
    ) -> str:
        """
        Simple helper for text-only notifications

        Args:
            text: Message text to send
            agent: Originating agent name
            context_id: Context for routing

        Returns:
            message_id
        """
        return self.enqueue(
            message_type="notification",
            payload={"text": text},
            originating_agent=agent,
            context_id=context_id,
        )

    def fetch_pending(self, limit: int = 50) -> list[OutboxMessage]:
        """
        Pull pending messages for delivery

        Args:
            limit: Maximum number of messages to fetch

        Returns:
            List of OutboxMessage instances in FIFO order (oldest first)
        """
        cursor = self.db.cursor()

        now = datetime.now(UTC).isoformat()
        cursor.execute(
            """
            SELECT * FROM message_outbox
            WHERE status = 'pending'
            AND (next_attempt_at IS NULL OR next_attempt_at <= ?)
            ORDER BY created_at ASC
            LIMIT ?
        """,
            (now, limit),
        )

        rows = cursor.fetchall()
        return [OutboxMessage.from_row(dict(row)) for row in rows]

    def get_by_message_id(self, message_id: str) -> OutboxMessage | None:
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT * FROM message_outbox WHERE message_id = ?",
            (message_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return OutboxMessage.from_row(dict(row))

    def list_recent_by_chat(
        self, chat_id: str, limit: int = 5, message_type_prefix: str | None = None
    ) -> list[OutboxMessage]:
        cursor = self.db.cursor()
        params: list[object] = [chat_id]
        query = "SELECT * FROM message_outbox " "WHERE chat_id = ? AND delivered_at IS NOT NULL"
        if message_type_prefix:
            query += " AND message_type LIKE ?"
            params.append(f"{message_type_prefix}%")
        query += " ORDER BY delivered_at DESC LIMIT ?"
        params.append(limit)
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [OutboxMessage.from_row(dict(row)) for row in rows]

    def count_delivered_since(self, chat_id: str, since_iso: str) -> int:
        cursor = self.db.cursor()
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM message_outbox
            WHERE chat_id = ? AND delivered_at >= ?
        """,
            (chat_id, since_iso),
        )
        row = cursor.fetchone()
        return int(row[0]) if row else 0

    def mark_delivered(
        self, message_id: str, chat_id: str | None = None, telegram_message_id: int | None = None
    ) -> None:
        """
        Mark message as successfully delivered

        Transitions:
        - If expects_response=False: pending → delivered
        - If expects_response=True: pending → awaiting_response

        Args:
            message_id: Message ID to mark as delivered
        """
        cursor = self.db.cursor()

        cursor.execute(
            """
            UPDATE message_outbox
            SET status = CASE
                    WHEN expects_response = 1 THEN 'awaiting_response'
                    ELSE 'delivered'
                END,
                delivered_at = ?,
                last_attempted_at = ?,
                chat_id = COALESCE(?, chat_id),
                telegram_message_id = COALESCE(?, telegram_message_id)
            WHERE message_id = ?
        """,
            (
                datetime.now(UTC).isoformat(),
                datetime.now(UTC).isoformat(),
                chat_id,
                telegram_message_id,
                message_id,
            ),
        )

        self.db.commit()

    def record_response_from_reply(
        self,
        chat_id: str,
        reply_to_message_id: int,
        response_json: dict[str, Any],
    ) -> str | None:
        cursor = self.db.cursor()
        cursor.execute(
            """
            SELECT id, originating_agent FROM message_outbox
            WHERE chat_id = ?
            AND telegram_message_id = ?
            AND expects_response = 1
            AND status = 'awaiting_response'
            LIMIT 1
        """,
            (chat_id, reply_to_message_id),
        )
        row = cursor.fetchone()
        if not row:
            return None

        cursor.execute(
            """
            UPDATE message_outbox
            SET status = 'delivered',
                response_received_at = ?,
                response_json = ?
            WHERE id = ?
        """,
            (datetime.now(UTC).isoformat(), json.dumps(response_json), row["id"]),
        )
        self.db.commit()
        return row["originating_agent"]

    def mark_failed(self, message_id: str, error: str) -> None:
        """
        Mark message delivery as failed

        Increments attempts counter. After MAX_ATTEMPTS (3), marks as 'failed'.
        Otherwise stays 'pending' for retry.

        Args:
            message_id: Message ID that failed delivery
            error: Error message describing the failure
        """
        cursor = self.db.cursor()

        now = datetime.now(UTC)

        cursor.execute(
            "SELECT attempts FROM message_outbox WHERE message_id = ?",
            (message_id,),
        )
        row = cursor.fetchone()
        if not row:
            return

        attempts = int(row["attempts"] or 0) + 1
        if attempts >= self.MAX_ATTEMPTS:
            status = "failed"
            next_attempt_at = None
        else:
            status = "pending"
            delay_seconds = 60 * (2 ** (attempts - 1))
            next_attempt_at = (now + timedelta(seconds=delay_seconds)).isoformat()

        cursor.execute(
            """
            UPDATE message_outbox
            SET attempts = ?,
                last_error = ?,
                last_attempted_at = ?,
                status = ?,
                next_attempt_at = ?
            WHERE message_id = ?
        """,
            (
                attempts,
                error,
                now.isoformat(),
                status,
                next_attempt_at,
                message_id,
            ),
        )

        self.db.commit()

    def record_response(self, context_id: str, response_data: dict) -> str | None:
        """
        Record user response to an interactive message
        Routes response back to originating agent

        Transition: awaiting_response → delivered

        Args:
            context_id: Context ID (e.g., 'project:42', 'discovery:disco_001')
            response_data: User's response (parsed from Telegram command)

        Returns:
            originating_agent name for routing, or None if no matching message found
        """
        cursor = self.db.cursor()

        # SQLite doesn't support RETURNING in UPDATE, so we need to fetch first
        cursor.execute(
            """
            SELECT id, originating_agent FROM message_outbox
            WHERE context_id = ?
            AND expects_response = 1
            AND status = 'awaiting_response'
            LIMIT 1
        """,
            (context_id,),
        )

        row = cursor.fetchone()

        if not row:
            return None

        originating_agent = row["originating_agent"]

        # Update the message
        cursor.execute(
            """
            UPDATE message_outbox
            SET status = 'delivered',
                response_received_at = ?,
                response_json = ?
            WHERE id = ?
        """,
            (datetime.now(UTC).isoformat(), json.dumps(response_data), row["id"]),
        )

        self.db.commit()

        return originating_agent

    def requeue(self, message_id: str) -> None:
        """
        Requeue a failed message for retry

        Transition: failed → pending

        Resets attempts to 0 and clears last_error.

        Args:
            message_id: Message ID to requeue

        Raises:
            ValueError: If message not found or not in 'failed' state
        """
        cursor = self.db.cursor()

        # Check if message exists and is failed
        cursor.execute("SELECT status FROM message_outbox WHERE message_id = ?", (message_id,))
        row = cursor.fetchone()

        if not row:
            raise ValueError(f"Message {message_id} not found")

        if row["status"] != "failed":
            raise ValueError(
                f"Can only requeue failed messages. "
                f"Message {message_id} has status: {row['status']}"
            )

        # Reset to pending
        cursor.execute(
            """
            UPDATE message_outbox
            SET status = 'pending',
                attempts = 0,
                last_error = NULL,
                next_attempt_at = NULL
            WHERE message_id = ?
        """,
            (message_id,),
        )

        self.db.commit()

    def close(self) -> None:
        if self._owns_connection:
            self.db.close()


# ==============================================================================
# Helper Functions
# ==============================================================================


def _parse_timestamp(timestamp_str: str | None) -> datetime | None:
    """
    Parse ISO format timestamp string to datetime

    Args:
        timestamp_str: ISO format timestamp or None

    Returns:
        datetime object or None
    """
    if not timestamp_str:
        return None

    try:
        parsed = datetime.fromisoformat(timestamp_str)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed
    except (ValueError, TypeError):
        return None
