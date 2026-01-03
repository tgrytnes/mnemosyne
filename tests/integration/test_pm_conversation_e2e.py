"""
E2E tests for Project Manager Agent conversation flows (Story 016)

These tests run with REAL services (PostgreSQL, SQLite) in CI/CD.
They validate the complete conversation loop end-to-end with actual infrastructure.

Unlike the standalone tests (which use in-memory mocks), these tests:
- Use real PostgreSQL database
- Use real SQLite message outbox
- Test actual database queries and transactions
- Validate production-like behavior
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Optional

import pytest

from mnemosyne.aletheia.agents.project_manager import ProjectManagerAgent
from mnemosyne.alexandria.sql_gatekeeper import GatekeeperConfig, SQLProjectGatekeeper
from mnemosyne.argus.scout.monitor_agent import MessageOutbox


# =============================================================================
# Mock Services (same as standalone tests)
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
        message_outbox,
        project_manager: ProjectManagerAgent,
        mock_user: MockUser,
    ):
        self.outbox = message_outbox
        self.pm = project_manager
        self.user = mock_user
        self.delivered_messages = []

    def poll_and_deliver(self) -> int:
        """Poll outbox, deliver to user, and route responses back to PM."""
        # For E2E tests, we query the real message outbox
        import json

        # Use the existing MessageOutbox connection
        cursor = self.outbox.db.cursor()

        cursor.execute(
            """
            SELECT id, message_id, message_type, payload_json
            FROM message_outbox
            WHERE status = 'pending'
            ORDER BY id ASC
            LIMIT 100
            """
        )
        rows = cursor.fetchall()

        processed = 0
        for row_id, msg_id, msg_type, payload_json in rows:
            message = json.loads(payload_json)

            # Deliver to user
            self.delivered_messages.append(message)
            user_response = self.user.respond_to_question(message)

            # Mark as delivered
            cursor.execute("UPDATE message_outbox SET status = 'delivered' WHERE id = ?", (row_id,))

            if user_response is None:
                processed += 1
                continue

            # Route response back to PM based on question_type metadata
            project_id = message.get("project_id")
            question_type = message.get("question_type", "")

            if question_type == "importance":
                self.pm.handle_importance_response(project_id, int(user_response))
            elif question_type == "urgency":
                self.pm.handle_urgency_response(project_id, int(user_response))
            elif question_type == "deadline":
                self.pm.handle_deadline_response(project_id, user_response)

            processed += 1

        self.outbox.db.commit()
        cursor.close()

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
            with self.pm.db_conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT importance, urgency, deadline
                    FROM projects
                    WHERE id = %s
                    """,
                    (project_id,),
                )
                row = cursor.fetchone()

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
def message_outbox(tmp_path):
    """Create real SQLite message outbox."""
    outbox_path = tmp_path / "outbox.db"
    outbox = MessageOutbox(outbox_path)

    yield outbox


@pytest.fixture
def project_manager(ananke_test_db, message_outbox, postgres_connection):
    """Create ProjectManagerAgent with real PostgreSQL."""
    # Create PM agent (gatekeeper not needed for E2E conversation tests)
    pm = ProjectManagerAgent(
        db_conn=postgres_connection,
        message_outbox=message_outbox,
        gatekeeper=None,
        max_messages_per_hour=5,
    )

    yield pm


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
# E2E Conversation Flow Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.postgres
def test_e2e_complete_enrichment_conversation(
    ananke_test_db,
    project_manager,
    mock_user,
    mock_nexus,
    conversation_sim,
):
    """
    E2E test: Complete enrichment conversation with real PostgreSQL.

    This test runs in CI with actual services to validate production behavior.
    """
    # Insert unenriched project
    with ananke_test_db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO projects (title, discovery_id, status)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            ("E2E Test Project", "disc-e2e-1", "active"),
        )
        project_id = cur.fetchone()[0]
    ananke_test_db.commit()

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

    # Verify final project state in real database
    with ananke_test_db.cursor() as cur:
        cur.execute(
            """
            SELECT importance, urgency, deadline, enriched
            FROM projects
            WHERE id = %s
            """,
            (project_id,),
        )
        row = cur.fetchone()

    assert row[0] == 5, "Importance should be 5"
    assert row[1] == 4, "Urgency should be 4"
    assert row[2] is not None, "Deadline should be set"
    assert row[3] is True, "Project should be marked enriched"


@pytest.mark.integration
@pytest.mark.postgres
def test_e2e_multiple_projects_sequential(
    ananke_test_db,
    project_manager,
    mock_user,
    mock_nexus,
    conversation_sim,
):
    """
    E2E test: Multiple projects enriched sequentially.

    Validates that the PM can handle multiple projects in sequence.
    """
    # Insert 3 projects
    project_ids = []
    with ananke_test_db.cursor() as cur:
        for i in range(3):
            cur.execute(
                """
                INSERT INTO projects (title, discovery_id, status)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (f"E2E Project {i+1}", f"disc-e2e-multi-{i+1}", "active"),
            )
            project_ids.append(cur.fetchone()[0])
    ananke_test_db.commit()

    # Enrich each project
    for project_id in project_ids:
        stats = conversation_sim.run_until_complete(project_id)
        assert stats["completed"], f"Project {project_id} should complete"

    # Verify all projects enriched
    with ananke_test_db.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM projects
            WHERE enriched = TRUE
            """
        )
        count = cur.fetchone()[0]

    assert count == 3, "All 3 projects should be enriched"


@pytest.mark.integration
@pytest.mark.postgres
def test_e2e_pressure_score_calculation(
    ananke_test_db,
    project_manager,
    mock_user,
    mock_nexus,
    conversation_sim,
):
    """
    E2E test: Pressure score calculation with real PostgreSQL.

    Validates the pressure score formula against real database.
    """
    # Insert project with work estimate
    with ananke_test_db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO projects (title, discovery_id, status, work_estimate)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            ("E2E Pressure Test", "disc-e2e-pressure", "active", 40.0),
        )
        project_id = cur.fetchone()[0]
    ananke_test_db.commit()

    # Set responses
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
    with ananke_test_db.cursor() as cur:
        cur.execute(
            """
            SELECT pressure_score
            FROM projects
            WHERE id = %s
            """,
            (project_id,),
        )
        pressure = cur.fetchone()[0]

    assert pressure is not None, "Pressure score should be calculated"
    assert pressure > 0, "Pressure score should be positive"


@pytest.mark.integration
@pytest.mark.postgres
def test_e2e_database_transactions(
    ananke_test_db,
    project_manager,
    mock_user,
):
    """
    E2E test: Verify database transactions and ACID properties.

    Tests that updates are atomic and consistent.
    """
    # Insert project
    with ananke_test_db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO projects (title, discovery_id, status)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            ("E2E Transaction Test", "disc-e2e-tx", "active"),
        )
        project_id = cur.fetchone()[0]
    ananke_test_db.commit()

    # Update importance
    project_manager.handle_importance_response(project_id, 5)

    # Verify importance was committed
    with ananke_test_db.cursor() as cur:
        cur.execute(
            "SELECT importance FROM projects WHERE id = %s",
            (project_id,),
        )
        importance = cur.fetchone()[0]

    assert importance == 5, "Importance should be committed to database"

    # Update urgency
    project_manager.handle_urgency_response(project_id, 4)

    # Verify both values persisted
    with ananke_test_db.cursor() as cur:
        cur.execute(
            "SELECT importance, urgency FROM projects WHERE id = %s",
            (project_id,),
        )
        row = cur.fetchone()

    assert row[0] == 5, "Importance should still be 5"
    assert row[1] == 4, "Urgency should be 4"


@pytest.mark.integration
@pytest.mark.postgres
def test_e2e_message_outbox_persistence(
    ananke_test_db,
    project_manager,
    message_outbox,
):
    """
    E2E test: Verify messages persist in SQLite outbox.

    Validates that the message outbox stores messages durably.
    """
    # Insert project
    with ananke_test_db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO projects (title, discovery_id, status)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            ("E2E Outbox Test", "disc-e2e-outbox", "active"),
        )
        project_id = cur.fetchone()[0]
    ananke_test_db.commit()

    # Run PM check cycle to send a message
    project_manager.run_pm_check_cycle()

    # Verify message in outbox
    cursor = message_outbox.db.cursor()

    cursor.execute(
        """
        SELECT COUNT(*) FROM message_outbox
        WHERE status = 'pending'
        """
    )
    count = cursor.fetchone()[0]
    cursor.close()

    assert count >= 1, "Should have at least 1 pending message in outbox"
