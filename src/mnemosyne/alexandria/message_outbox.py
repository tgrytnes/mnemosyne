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
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Any
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
    """
    id: int
    message_id: str
    message_type: str
    originating_agent: Optional[str]
    context_id: Optional[str]
    payload: Dict[str, Any]
    status: str
    expects_response: bool
    response_received_at: Optional[datetime]
    response: Optional[Dict[str, Any]]
    attempts: int
    last_error: Optional[str]
    created_at: datetime
    last_attempted_at: Optional[datetime]
    delivered_at: Optional[datetime]

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> 'OutboxMessage':
        """
        Create OutboxMessage from database row

        Args:
            row: Database row as dict (from sqlite3.Row)

        Returns:
            OutboxMessage instance
        """
        return cls(
            id=row['id'],
            message_id=row['message_id'],
            message_type=row['message_type'],
            originating_agent=row['originating_agent'],
            context_id=row['context_id'],
            payload=json.loads(row['payload_json']),
            status=row['status'],
            expects_response=bool(row['expects_response']),
            response_received_at=_parse_timestamp(row['response_received_at']),
            response=json.loads(row['response_json']) if row['response_json'] else None,
            attempts=row['attempts'],
            last_error=row['last_error'],
            created_at=_parse_timestamp(row['created_at']),
            last_attempted_at=_parse_timestamp(row['last_attempted_at']),
            delivered_at=_parse_timestamp(row['delivered_at'])
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
    VALID_MESSAGE_TYPES = {
        'notification',
        'approval_request',
        'escalation',
        'question'
    }

    # Max delivery attempts before marking as failed
    MAX_ATTEMPTS = 3

    def __init__(self, db: sqlite3.Connection):
        """
        Initialize MessageOutbox

        Args:
            db: SQLite database connection with message_outbox table
        """
        self.db = db
        self.db.row_factory = sqlite3.Row

    def enqueue(
        self,
        message_type: str,
        payload: dict,
        message_id: Optional[str] = None,
        originating_agent: Optional[str] = None,
        context_id: Optional[str] = None,
        expects_response: bool = False
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

        # Validate payload
        if not payload:
            raise ValueError("payload cannot be empty")

        # Generate message_id if not provided
        if not message_id:
            message_id = f"{message_type}:{context_id or 'none'}:{uuid4()}"

        cursor = self.db.cursor()

        # INSERT OR IGNORE for idempotency
        cursor.execute("""
            INSERT OR IGNORE INTO message_outbox (
                message_id,
                message_type,
                originating_agent,
                context_id,
                payload_json,
                expects_response
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            message_id,
            message_type,
            originating_agent,
            context_id,
            json.dumps(payload),
            expects_response
        ))

        self.db.commit()
        return message_id

    def send_message(
        self,
        text: str,
        agent: Optional[str] = None,
        context_id: Optional[str] = None
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
            message_type='notification',
            payload={'text': text},
            originating_agent=agent,
            context_id=context_id
        )

    def fetch_pending(self, limit: int = 50) -> List[OutboxMessage]:
        """
        Pull pending messages for delivery

        Args:
            limit: Maximum number of messages to fetch

        Returns:
            List of OutboxMessage instances in FIFO order (oldest first)
        """
        cursor = self.db.cursor()

        cursor.execute("""
            SELECT * FROM message_outbox
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()
        return [OutboxMessage.from_row(dict(row)) for row in rows]

    def mark_delivered(self, message_id: str) -> None:
        """
        Mark message as successfully delivered

        Transitions:
        - If expects_response=False: pending → delivered
        - If expects_response=True: pending → awaiting_response

        Args:
            message_id: Message ID to mark as delivered
        """
        cursor = self.db.cursor()

        cursor.execute("""
            UPDATE message_outbox
            SET status = CASE
                    WHEN expects_response = 1 THEN 'awaiting_response'
                    ELSE 'delivered'
                END,
                delivered_at = ?
            WHERE message_id = ?
        """, (datetime.now().isoformat(), message_id))

        self.db.commit()

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

        cursor.execute("""
            UPDATE message_outbox
            SET attempts = attempts + 1,
                last_error = ?,
                last_attempted_at = ?,
                status = CASE
                    WHEN attempts + 1 >= ? THEN 'failed'
                    ELSE 'pending'
                END
            WHERE message_id = ?
        """, (error, datetime.now().isoformat(), self.MAX_ATTEMPTS, message_id))

        self.db.commit()

    def record_response(
        self,
        context_id: str,
        response_data: dict
    ) -> Optional[str]:
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
        cursor.execute("""
            SELECT id, originating_agent FROM message_outbox
            WHERE context_id = ?
            AND expects_response = 1
            AND status = 'awaiting_response'
            LIMIT 1
        """, (context_id,))

        row = cursor.fetchone()

        if not row:
            return None

        originating_agent = row['originating_agent']

        # Update the message
        cursor.execute("""
            UPDATE message_outbox
            SET status = 'delivered',
                response_received_at = ?,
                response_json = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), json.dumps(response_data), row['id']))

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

        if row['status'] != 'failed':
            raise ValueError(
                f"Can only requeue failed messages. "
                f"Message {message_id} has status: {row['status']}"
            )

        # Reset to pending
        cursor.execute("""
            UPDATE message_outbox
            SET status = 'pending',
                attempts = 0,
                last_error = NULL
            WHERE message_id = ?
        """, (message_id,))

        self.db.commit()


# ==============================================================================
# Helper Functions
# ==============================================================================

def _parse_timestamp(timestamp_str: Optional[str]) -> Optional[datetime]:
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
        return datetime.fromisoformat(timestamp_str)
    except (ValueError, TypeError):
        return None
