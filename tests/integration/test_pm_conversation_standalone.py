"""
Standalone Project Manager Conversation Flow Tests

These tests run WITHOUT requiring PostgreSQL or any external services.
They use in-memory SQLite to simulate the database and test the complete
conversation loop with mock services.

This addresses the issue where integration tests were skipping due to
missing PostgreSQL. These tests ALWAYS RUN and validate the core
conversation functionality.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Optional

import pytest

from mnemosyne.aletheia.agents.project_manager import ProjectManagerAgent
from mnemosyne.argus.scout.monitor_agent import MessageOutbox


class MessageOutboxWrapper:
    """
    Wrapper for MessageOutbox to provide both enqueue() and enqueue_message() APIs.

    The ProjectManagerAgent uses enqueue_message() but the base MessageOutbox
    only provides enqueue(). This wrapper makes them compatible.
    """

    def __init__(self, outbox: MessageOutbox):
        self._outbox = outbox

    def enqueue_message(self, content: str, sender: str = "project_manager",
                       expects_response: bool = False, metadata: dict = None):
        """Enqueue message using PM's expected API."""
        import json
        import uuid
        message_id = str(uuid.uuid4())

        if metadata is None:
            metadata = {}

        # Determine message type from metadata if available
        message_type = metadata.get("question_type", "project_update")

        payload = {
            "content": content,
            "message_type": message_type,
            "sender": sender,
            "expects_response": expects_response,
            **metadata
        }

        self._outbox.enqueue(message_type, payload, message_id)

    def dequeue(self, limit: int = 100):
        """Dequeue messages, mark as delivered, and convert to tuple format."""
        import json
        from datetime import UTC, datetime

        messages = self._outbox.dequeue(limit)

        if not messages:
            return []

        result = []
        message_ids = []

        # First, mark ALL messages as delivered immediately
        for msg in messages:
            message_ids.append(msg["message_id"])

        # Update all at once
        placeholders = ",".join(["?" for _ in message_ids])
        self._outbox._conn.execute(
            f"UPDATE message_outbox SET status = 'delivered', updated_at = ? WHERE message_id IN ({placeholders})",
            (datetime.now(UTC).isoformat(), *message_ids)
        )
        self._outbox._conn.commit()

        # Now convert to result format
        for msg in messages:
            payload = json.loads(msg["payload_json"]) if isinstance(msg["payload_json"], str) else msg["payload_json"]
            result.append((msg["message_id"], payload))

        return result

    def __getattr__(self, name):
        """Delegate all other attributes to the wrapped outbox."""
        return getattr(self._outbox, name)


# =============================================================================
# In-Memory Database Setup
# =============================================================================


class SQLiteCursorWrapper:
    """
    Wrapper to make SQLite cursors compatible with PostgreSQL cursor API.

    PostgreSQL uses:
    - %s for placeholders
    - context manager protocol on cursors

    SQLite uses:
    - ? for placeholders
    - no context manager on cursors

    This wrapper translates between the two.
    """

    def __init__(self, conn):
        self.conn = conn
        self._cursor = self.conn.cursor()

    def execute(self, sql, params=None):
        """Execute SQL with automatic placeholder translation."""
        # Convert PostgreSQL %s to SQLite ?
        sqlite_sql = sql.replace("%s", "?")

        if params:
            return self._cursor.execute(sqlite_sql, params)
        else:
            return self._cursor.execute(sqlite_sql)

    def fetchone(self):
        """Fetch one row."""
        return self._cursor.fetchone()

    def fetchall(self):
        """Fetch all rows."""
        return self._cursor.fetchall()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._cursor:
            self._cursor.close()
        return False

    def __getattr__(self, name):
        """Delegate all other attribute access to the underlying cursor."""
        return getattr(self._cursor, name)


class InMemoryProjectDatabase:
    """
    In-memory SQLite database that mimics PostgreSQL schema.

    This allows tests to run without requiring PostgreSQL.
    """

    def __init__(self):
        """Create in-memory database with projects schema."""
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row  # Return rows as dicts
        self._create_schema()

    def _create_schema(self):
        """Create tables matching PostgreSQL schema."""
        cursor = self.conn.cursor()

        # Projects table
        cursor.execute(
            """
            CREATE TABLE projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                discovered_by TEXT,
                discovery_id TEXT UNIQUE,
                cluster_ids TEXT,
                cluster_count INTEGER DEFAULT 1,
                confidence_score REAL,
                verified_by_user INTEGER DEFAULT 0,
                verified_at TEXT,
                status TEXT DEFAULT 'candidate',
                importance INTEGER,
                urgency INTEGER,
                deadline TEXT,
                work_estimate REAL,
                estimated_work_hours REAL,
                pressure_score REAL,
                enriched INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Gatekeeper audit table
        cursor.execute(
            """
            CREATE TABLE gatekeeper_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                approval_id TEXT NOT NULL,
                approved INTEGER NOT NULL,
                project_id INTEGER REFERENCES projects(id),
                decided_at TEXT DEFAULT CURRENT_TIMESTAMP,
                decided_by TEXT DEFAULT 'telegram_user',
                reason TEXT
            )
            """
        )

        # Message outbox table (for throttling check)
        cursor.execute(
            """
            CREATE TABLE message_outbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender TEXT NOT NULL,
                recipient TEXT,
                content TEXT,
                message_type TEXT,
                metadata TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                delivered_at TEXT
            )
            """
        )

        self.conn.commit()

    def cursor(self):
        """Return cursor wrapper that supports context manager protocol."""
        return SQLiteCursorWrapper(self.conn)

    def commit(self):
        """Commit transaction."""
        self.conn.commit()

    def rollback(self):
        """Rollback transaction."""
        self.conn.rollback()

    def close(self):
        """Close connection."""
        self.conn.close()


class MockGatekeeper:
    """Mock gatekeeper for updating projects."""

    def __init__(self, db_conn):
        self.db_conn = db_conn

    def update_project_direct(self, project_id: int, updates: dict, user_initiated: bool = False):
        """Update project fields directly."""
        # Build SET clause
        set_parts = []
        values = []

        for key, value in updates.items():
            set_parts.append(f"{key} = ?")
            # Convert datetime to ISO string for SQLite
            if isinstance(value, datetime):
                value = value.isoformat()
            values.append(value)

        set_clause = ", ".join(set_parts)
        values.append(project_id)

        cursor = self.db_conn.cursor()
        cursor.execute(
            f"""
            UPDATE projects
            SET {set_clause}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            values,
        )
        self.db_conn.commit()

        # Check if fully enriched
        cursor.execute(
            """
            SELECT importance, urgency, deadline
            FROM projects
            WHERE id = ?
            """,
            (project_id,),
        )
        row = cursor.fetchone()

        if row and all(x is not None for x in row):
            # Mark as enriched
            cursor.execute(
                """
                UPDATE projects
                SET enriched = 1
                WHERE id = ?
                """,
                (project_id,),
            )
            self.db_conn.commit()


# =============================================================================
# Mock Services (Same as before)
# =============================================================================


class MockUser:
    """Simulates a user responding to PM questions."""

    def __init__(self, behavior: str = "cooperative"):
        self.behavior = behavior
        self.responses = {
            "importance": "4",
            "urgency": "3",
            "deadline": "2026-02-15",
        }

    def set_response(self, question_type: str, value: str):
        """Set custom response for a question type."""
        self.responses[question_type] = value

    def respond_to_question(self, message: dict) -> Optional[str]:
        """Generate response to a PM question."""
        content = message.get("content", "")

        # Avoidant user skips urgency questions
        if self.behavior == "avoidant" and "urgent" in content.lower():
            return None

        # Map message type to response type
        if "importance" in content.lower():
            return self.responses["importance"]
        elif "urgent" in content.lower():
            return self.responses["urgency"]
        elif "deadline" in content.lower():
            return self.responses["deadline"]

        return None


class MockNexus:
    """Simulates Nexus/Telegram bot polling outbox and delivering messages."""

    def __init__(
        self,
        message_outbox: MessageOutbox,
        project_manager: ProjectManagerAgent,
        mock_user: MockUser,
    ):
        self.outbox = message_outbox
        self.pm = project_manager
        self.user = mock_user
        self.delivered_messages = []

    def poll_and_deliver(self) -> int:
        """Poll outbox, deliver to user, and route responses back to PM."""
        messages = self.outbox.dequeue()
        processed = 0

        for msg_id, message in messages:
            # Deliver to user
            self.delivered_messages.append(message)
            user_response = self.user.respond_to_question(message)

            if user_response is None:
                processed += 1
                continue

            # Route response back to PM based on question_type metadata
            # IMPORTANT: Use metadata, not content parsing! The deadline question
            # contains the word "importance" in its text, which would cause
            # incorrect routing if we parsed content.
            project_id = message.get("project_id")
            question_type = message.get("question_type", "")

            if question_type == "importance":
                self.pm.handle_importance_response(project_id, int(user_response))
            elif question_type == "urgency":
                self.pm.handle_urgency_response(project_id, int(user_response))
            elif question_type == "deadline":
                self.pm.handle_deadline_response(project_id, user_response)

            processed += 1

        return processed

    def get_last_message(self) -> Optional[dict]:
        """Get the last delivered message."""
        return self.delivered_messages[-1] if self.delivered_messages else None

    def clear_history(self):
        """Clear delivered message history."""
        self.delivered_messages.clear()


class ConversationSimulator:
    """Orchestrates complete conversation flows for testing."""

    def __init__(
        self,
        project_manager: ProjectManagerAgent,
        mock_nexus: MockNexus,
        max_iterations: int = 10,
    ):
        self.pm = project_manager
        self.nexus = mock_nexus
        self.max_iterations = max_iterations

    def run_until_complete(self, project_id: int) -> dict:
        """
        Run conversation until project enrichment completes.

        Uses event-driven flow: PM check cycle kicks off the first question,
        then response handlers drive the conversation via continue_enrichment().
        """
        stats = {
            "turns": 0,
            "messages_sent": 0,
            "completed": False,
        }

        # Kick off the conversation with initial PM check cycle
        self.pm.run_pm_check_cycle()

        for i in range(self.max_iterations):
            stats["turns"] = i + 1

            # Nexus polls and delivers messages (which triggers response handlers)
            messages_processed = self.nexus.poll_and_deliver()
            stats["messages_sent"] += messages_processed

            # Check if project is fully enriched
            cur = self.pm.db_conn.cursor()
            cur.execute(
                """
                SELECT importance, urgency, deadline
                FROM projects
                WHERE id = ?
                """,
                (project_id,),
            )
            row = cur.fetchone()

            if row and all(x is not None for x in row):
                stats["completed"] = True
                break

            # No messages sent means no more questions
            if messages_processed == 0:
                break

        return stats


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def in_memory_db():
    """Create in-memory database."""
    db = InMemoryProjectDatabase()
    yield db
    db.close()


@pytest.fixture
def message_outbox(tmp_path):
    """Create message outbox with wrapper for PM compatibility."""
    outbox = MessageOutbox(tmp_path / "outbox.db")
    wrapped = MessageOutboxWrapper(outbox)
    yield wrapped


@pytest.fixture
def mock_gatekeeper(in_memory_db):
    """Create mock gatekeeper."""
    return MockGatekeeper(in_memory_db)


@pytest.fixture
def project_manager(in_memory_db, message_outbox, mock_gatekeeper):
    """Create ProjectManagerAgent with in-memory database."""
    return ProjectManagerAgent(
        db_conn=in_memory_db,
        message_outbox=message_outbox,
        gatekeeper=mock_gatekeeper,
        max_messages_per_hour=5,
    )


@pytest.fixture
def mock_user():
    """Create cooperative mock user."""
    return MockUser(behavior="cooperative")


@pytest.fixture
def mock_nexus(message_outbox, project_manager, mock_user):
    """Create mock Nexus."""
    return MockNexus(message_outbox, project_manager, mock_user)


@pytest.fixture
def conversation_sim(project_manager, mock_nexus):
    """Create conversation simulator."""
    return ConversationSimulator(project_manager, mock_nexus)


# =============================================================================
# Conversation Flow Tests (ALWAYS RUN - No PostgreSQL Required!)
# =============================================================================


def test_complete_enrichment_conversation(
    in_memory_db,
    project_manager,
    mock_user,
    mock_nexus,
    conversation_sim,
):
    """
    Test complete enrichment conversation from start to finish.

    This test ALWAYS RUNS (no external dependencies).
    """
    # Insert unenriched project
    cur = in_memory_db.cursor()
    cur.execute(
        """
        INSERT INTO projects (title, discovery_id, status)
        VALUES (?, ?, ?)
        """,
        ("Test Project", "disc-conv-1", "active"),
    )
    project_id = cur.lastrowid
    in_memory_db.commit()

    # Configure user responses
    mock_user.set_response("importance", "5")
    mock_user.set_response("urgency", "4")
    mock_user.set_response("deadline", "2026-03-01")

    # Run conversation until complete
    stats = conversation_sim.run_until_complete(project_id)

    # Verify conversation completed
    assert stats["completed"], "Enrichment should complete"
    assert stats["turns"] <= 4, "Should complete in 3-4 turns"
    assert stats["messages_sent"] == 3, "Should send 3 questions"

    # Verify final project state
    cur.execute(
        """
        SELECT importance, urgency, deadline, enriched
        FROM projects
        WHERE id = ?
        """,
        (project_id,),
    )
    row = cur.fetchone()

    assert row["importance"] == 5, "Importance should be set"
    assert row["urgency"] == 4, "Urgency should be set"
    assert row["deadline"] is not None, "Deadline should be set"
    assert row["enriched"] == 1, "Project should be marked enriched"


def test_high_priority_project_enriched_first(
    in_memory_db,
    project_manager,
    mock_user,
    mock_nexus,
):
    """
    Test that high priority projects get enriched before low priority ones.

    This test ALWAYS RUNS (no external dependencies).
    """
    # Insert low priority project
    cur = in_memory_db.cursor()
    cur.execute(
        """
        INSERT INTO projects (title, discovery_id, status, cluster_count)
        VALUES (?, ?, ?, ?)
        """,
        ("Low Priority", "disc-low", "active", 1),
    )
    low_id = cur.lastrowid

    # Insert high priority project
    cur.execute(
        """
        INSERT INTO projects (title, discovery_id, status, cluster_count)
        VALUES (?, ?, ?, ?)
        """,
        ("High Priority", "disc-high", "active", 5),
    )
    high_id = cur.lastrowid
    in_memory_db.commit()

    # Run PM check cycle
    project_manager.run_pm_check_cycle()

    # Poll outbox
    mock_nexus.poll_and_deliver()

    # Verify high priority project got the question
    last_msg = mock_nexus.get_last_message()
    assert last_msg is not None, "Should send question"
    assert last_msg["project_id"] == high_id, "Should ask about high priority project first"


def test_avoidant_user_only_answers_importance(
    in_memory_db,
    project_manager,
    message_outbox,
):
    """
    Test user who only answers importance questions (avoids urgency).

    This test ALWAYS RUNS (no external dependencies).
    """
    # Create avoidant user
    avoidant_user = MockUser(behavior="avoidant")
    avoidant_user.set_response("importance", "3")

    nexus = MockNexus(message_outbox, project_manager, avoidant_user)

    # Insert project
    cur = in_memory_db.cursor()
    cur.execute(
        """
        INSERT INTO projects (title, discovery_id, status)
        VALUES (?, ?, ?)
        """,
        ("Avoided Project", "disc-avoid", "active"),
    )
    project_id = cur.lastrowid
    in_memory_db.commit()

    # Turn 1: Ask importance
    project_manager.run_pm_check_cycle()
    nexus.poll_and_deliver()

    # Turn 2: Ask urgency (user will ignore)
    project_manager.run_pm_check_cycle()
    nexus.poll_and_deliver()

    # Turn 3: Should re-ask urgency (not move to deadline)
    project_manager.run_pm_check_cycle()
    messages = message_outbox.dequeue()

    # Verify still asking about urgency
    assert len(messages) > 0, "Should keep asking urgency"
    assert "urgent" in messages[0][1]["content"].lower()

    # Verify project only has importance
    cur.execute(
        """
        SELECT importance, urgency, deadline, enriched
        FROM projects
        WHERE id = ?
        """,
        (project_id,),
    )
    row = cur.fetchone()

    assert row["importance"] == 3, "Importance should be set"
    assert row["urgency"] is None, "Urgency should not be set"
    assert row["deadline"] is None, "Deadline should not be set"
    assert row["enriched"] == 0, "Project should not be marked enriched"


def test_natural_language_deadline_parsing(
    in_memory_db,
    project_manager,
    mock_user,
    mock_nexus,
    conversation_sim,
):
    """
    Test various deadline formats are parsed correctly.

    This test ALWAYS RUNS (no external dependencies).
    """
    # Insert project
    cur = in_memory_db.cursor()
    cur.execute(
        """
        INSERT INTO projects (title, discovery_id, status)
        VALUES (?, ?, ?)
        """,
        ("Deadline Test", "disc-deadline", "active"),
    )
    project_id = cur.lastrowid
    in_memory_db.commit()

    # Set responses with natural language deadline
    mock_user.set_response("importance", "4")
    mock_user.set_response("urgency", "3")
    mock_user.set_response("deadline", "in 2 weeks")

    # Run conversation
    stats = conversation_sim.run_until_complete(project_id)

    assert stats["completed"], "Should complete enrichment"

    # Verify deadline was parsed (should be ~14 days from now)
    cur.execute(
        """
        SELECT deadline
        FROM projects
        WHERE id = ?
        """,
        (project_id,),
    )
    deadline_str = cur.fetchone()["deadline"]

    assert deadline_str is not None, "Deadline should be parsed"

    # Parse stored deadline
    from datetime import timezone
    from dateutil import parser as date_parser

    deadline = date_parser.parse(deadline_str)

    # Should be approximately 2 weeks from now
    expected = datetime.now(timezone.utc) + timedelta(days=14)
    diff = abs((deadline - expected).total_seconds())

    assert diff < 86400, "Deadline should be ~2 weeks from now (within 1 day)"


def test_throttling_prevents_spam(
    in_memory_db,
    project_manager,
    mock_user,
    mock_nexus,
):
    """
    Test throttling prevents sending too many messages.

    This test ALWAYS RUNS (no external dependencies).
    """
    # Insert 10 projects (more than throttle limit)
    cur = in_memory_db.cursor()
    for i in range(10):
        cur.execute(
            """
            INSERT INTO projects (title, discovery_id, status)
            VALUES (?, ?, ?)
            """,
            (f"Spam Test {i+1}", f"disc-spam-{i+1}", "active"),
        )
    in_memory_db.commit()

    # Run PM check cycle (should only send 5 messages due to throttle)
    project_manager.run_pm_check_cycle()

    # Count messages in outbox
    messages = project_manager.message_outbox.dequeue()
    assert len(messages) == 5, "Should throttle at 5 messages per hour"

    # Try again immediately (should send 0 more)
    project_manager.run_pm_check_cycle()
    messages = project_manager.message_outbox.dequeue()
    assert len(messages) == 0, "Should not send more while throttled"


def test_pressure_score_updates_after_enrichment(
    in_memory_db,
    project_manager,
    mock_user,
    mock_nexus,
    conversation_sim,
):
    """
    Test pressure score is calculated after enrichment.

    This test ALWAYS RUNS (no external dependencies).
    """
    # Insert project with work estimate
    cur = in_memory_db.cursor()
    cur.execute(
        """
        INSERT INTO projects (title, discovery_id, status, work_estimate)
        VALUES (?, ?, ?, ?)
        """,
        ("Pressure Test", "disc-pressure", "active", 40.0),
    )
    project_id = cur.lastrowid
    in_memory_db.commit()

    # Verify pressure score is NULL
    cur.execute("SELECT pressure_score FROM projects WHERE id = ?", (project_id,))
    assert cur.fetchone()["pressure_score"] is None, "Pressure score should be NULL before enrichment"

    # Set responses (importance=5, urgency=4, deadline in 10 days)
    mock_user.set_response("importance", "5")
    mock_user.set_response("urgency", "4")
    deadline = (datetime.now(UTC) + timedelta(days=10)).date().isoformat()
    mock_user.set_response("deadline", deadline)

    # Run conversation
    stats = conversation_sim.run_until_complete(project_id)
    assert stats["completed"], "Should complete enrichment"

    # Update pressure scores
    project_manager._update_pressure_scores()

    # Verify pressure score calculated
    cur.execute("SELECT pressure_score FROM projects WHERE id = ?", (project_id,))
    pressure = cur.fetchone()["pressure_score"]

    assert pressure is not None, "Pressure score should be calculated"

    # Expected: (40 / (10*24)) × (5 × 4) = (40/240) × 20 = 0.167 × 20 = 3.33
    expected = (40.0 / (10 * 24)) * (5 * 4)
    assert abs(pressure - expected) < 0.1, f"Pressure score should be ~{expected}"


def test_event_driven_enrichment_flow(
    in_memory_db,
    project_manager,
    mock_user,
):
    """
    Test event-driven flow: each response triggers next question.

    This test ALWAYS RUNS (no external dependencies).
    Tests the response handlers directly without the PM check cycle.
    """
    # Insert project
    cur = in_memory_db.cursor()
    cur.execute(
        """
        INSERT INTO projects (title, discovery_id, status)
        VALUES (?, ?, ?)
        """,
        ("Event Test", "disc-event", "active"),
    )
    project_id = cur.lastrowid
    in_memory_db.commit()

    # Manually trigger responses (simulates event-driven flow)
    # 1. User responds with importance
    project_manager.handle_importance_response(project_id, 5)

    # Check that urgency question was queued
    messages = project_manager.message_outbox.dequeue()
    assert len(messages) >= 1, "Should queue urgency question"

    # Find the urgency question
    urgency_msg = None
    for msg_id, msg in messages:
        if "urgent" in msg.get("content", "").lower():
            urgency_msg = msg
            break

    assert urgency_msg is not None, "Should have urgency question"

    # 2. User responds with urgency
    project_manager.handle_urgency_response(project_id, 4)

    # Check that deadline question was queued (high priority: 5+4=9)
    messages = project_manager.message_outbox.dequeue()
    assert len(messages) >= 1, "Should queue deadline question"

    # Find the deadline question
    deadline_msg = None
    for msg_id, msg in messages:
        if "deadline" in msg.get("content", "").lower():
            deadline_msg = msg
            break

    assert deadline_msg is not None, "Should have deadline question"

    # 3. User responds with deadline
    project_manager.handle_deadline_response(project_id, "2026-04-01")

    # Verify project fully enriched
    cur.execute(
        """
        SELECT importance, urgency, deadline, enriched
        FROM projects
        WHERE id = ?
        """,
        (project_id,),
    )
    row = cur.fetchone()

    assert row["importance"] == 5
    assert row["urgency"] == 4
    assert row["deadline"] is not None
    assert row["enriched"] == 1
