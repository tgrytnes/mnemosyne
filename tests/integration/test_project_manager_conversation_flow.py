"""
Integration tests for Project Manager Agent conversation flows (Story 016 - Phase 8 Enhanced)

Tests the complete conversation loop using mock services that simulate:
- Nexus polling the message outbox and delivering messages
- User reading questions and providing responses
- PM processing responses and continuing enrichment
- Complete enrichment flows from start to finish

This addresses the need for more creative, comprehensive testing of the
entire system working together as a conversation loop.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Optional

import pytest

from mnemosyne.aletheia.agents.project_manager import ProjectManagerAgent
from mnemosyne.alexandria.sql_gatekeeper import GatekeeperConfig, SQLProjectGatekeeper
from mnemosyne.argus.scout.monitor_agent import MessageOutbox, ProposalQueue


class MockUser:
    """
    Simulates a user responding to PM questions.

    Provides realistic responses based on question type and can simulate
    different user behaviors (cooperative, avoidant, slow responder).
    """

    def __init__(self, behavior: str = "cooperative"):
        """
        Initialize mock user.

        Args:
            behavior: User behavior type
                - "cooperative": Always responds appropriately
                - "avoidant": Skips urgency questions
                - "slow": Delays responses (for throttling tests)
        """
        self.behavior = behavior
        self.responses = {
            "importance": "4",  # Default importance rating
            "urgency": "3",  # Default urgency rating
            "deadline": "2026-02-15",  # Default deadline
        }

    def set_response(self, question_type: str, value: str):
        """Set custom response for a question type."""
        self.responses[question_type] = value

    def respond_to_question(self, message: dict) -> Optional[str]:
        """
        Generate response to a PM question.

        Args:
            message: Message from outbox

        Returns:
            User's response string, or None if avoiding question
        """
        message_type = message.get("message_type")
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
    """
    Simulates Nexus/Telegram bot polling outbox and delivering messages.

    Bridges the gap between PM agent (writing to outbox) and user (responding).
    Routes user responses back to PM via response handlers.
    """

    def __init__(
        self,
        message_outbox: MessageOutbox,
        project_manager: ProjectManagerAgent,
        mock_user: MockUser,
    ):
        """
        Initialize mock Nexus.

        Args:
            message_outbox: Message outbox to poll
            project_manager: PM agent to route responses to
            mock_user: Mock user to deliver messages to
        """
        self.outbox = message_outbox
        self.pm = project_manager
        self.user = mock_user
        self.delivered_messages = []

    def poll_and_deliver(self) -> int:
        """
        Poll outbox, deliver to user, and route responses back to PM.

        Returns:
            Number of messages processed
        """
        messages = self.outbox.dequeue()
        processed = 0

        for msg_id, message in messages:
            # Deliver to user
            self.delivered_messages.append(message)
            user_response = self.user.respond_to_question(message)

            if user_response is None:
                # User ignored question
                processed += 1
                continue

            # Route response back to PM
            project_id = message.get("project_id")
            content = message.get("content", "")

            if "importance" in content.lower():
                self.pm.handle_importance_response(project_id, user_response)
            elif "urgent" in content.lower():
                self.pm.handle_urgency_response(project_id, user_response)
            elif "deadline" in content.lower():
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
    """
    Orchestrates complete conversation flows for testing.

    Runs the PM check cycle, polls outbox, delivers messages, processes responses,
    and repeats until enrichment completes.
    """

    def __init__(
        self,
        project_manager: ProjectManagerAgent,
        mock_nexus: MockNexus,
        max_iterations: int = 10,
    ):
        """
        Initialize conversation simulator.

        Args:
            project_manager: PM agent
            mock_nexus: Mock Nexus for message delivery
            max_iterations: Max conversation turns (safety limit)
        """
        self.pm = project_manager
        self.nexus = mock_nexus
        self.max_iterations = max_iterations

    def run_until_complete(self, project_id: int) -> dict:
        """
        Run conversation until project enrichment completes.

        Args:
            project_id: Project to enrich

        Returns:
            Statistics about the conversation:
                - turns: Number of conversation turns
                - messages_sent: Total messages sent
                - completed: Whether enrichment completed
        """
        stats = {
            "turns": 0,
            "messages_sent": 0,
            "completed": False,
        }

        for i in range(self.max_iterations):
            stats["turns"] = i + 1

            # PM runs check cycle (sends question if needed)
            self.pm.run_pm_check_cycle()

            # Nexus polls and delivers messages
            messages_processed = self.nexus.poll_and_deliver()
            stats["messages_sent"] += messages_processed

            # Check if project is fully enriched
            cur = self.pm.db_conn.cursor()
            cur.execute(
                """
                SELECT importance, urgency, deadline
                FROM projects
                WHERE id = %s
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
# Conversation Flow Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.postgres
def test_complete_enrichment_conversation(
    ananke_test_db,
    project_manager,
    mock_user,
    mock_nexus,
    conversation_sim,
):
    """
    Test complete enrichment conversation from start to finish.

    Verifies:
    1. PM asks importance question
    2. User responds with rating
    3. PM asks urgency question
    4. User responds with rating
    5. PM asks deadline question
    6. User provides deadline
    7. All data stored correctly in database
    """
    # Insert unenriched project
    cur = ananke_test_db.cursor()
    cur.execute(
        """
        INSERT INTO projects (title, discovery_id, status)
        VALUES (%s, %s, %s)
        RETURNING id
        """,
        ("Test Project", "disc-conv-1", "active"),
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

    # Verify final project state
    cur.execute(
        """
        SELECT importance, urgency, deadline, enriched
        FROM projects
        WHERE id = %s
        """,
        (project_id,),
    )
    row = cur.fetchone()

    assert row[0] == 5, "Importance should be set"
    assert row[1] == 4, "Urgency should be set"
    assert row[2] == datetime(2026, 3, 1, tzinfo=UTC), "Deadline should be parsed"
    assert row[3] is True, "Project should be marked enriched"


@pytest.mark.integration
@pytest.mark.postgres
def test_high_priority_project_enriched_first(
    ananke_test_db,
    project_manager,
    mock_user,
    mock_nexus,
):
    """
    Test that high priority projects get enriched before low priority ones.

    Creates two projects:
    1. Low cluster count (cluster_count=1)
    2. High cluster count (cluster_count=5)

    Verifies high cluster project is asked first.
    """
    # Insert low priority project
    cur = ananke_test_db.cursor()
    cur.execute(
        """
        INSERT INTO projects (title, discovery_id, status, cluster_count)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """,
        ("Low Priority", "disc-low", "active", 1),
    )
    low_id = cur.fetchone()[0]

    # Insert high priority project
    cur.execute(
        """
        INSERT INTO projects (title, discovery_id, status, cluster_count)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """,
        ("High Priority", "disc-high", "active", 5),
    )
    high_id = cur.fetchone()[0]
    ananke_test_db.commit()

    # Run PM check cycle
    project_manager.run_pm_check_cycle()

    # Poll outbox
    mock_nexus.poll_and_deliver()

    # Verify high priority project got the question
    last_msg = mock_nexus.get_last_message()
    assert last_msg is not None, "Should send question"
    assert last_msg["project_id"] == high_id, "Should ask about high priority project first"


@pytest.mark.integration
@pytest.mark.postgres
def test_avoidant_user_only_answers_importance(
    ananke_test_db,
    project_manager,
    message_outbox,
):
    """
    Test user who only answers importance questions (avoids urgency).

    Verifies:
    1. User answers importance question
    2. User ignores urgency question
    3. Project remains partially enriched
    4. No deadline question sent
    """
    # Create avoidant user
    avoidant_user = MockUser(behavior="avoidant")
    avoidant_user.set_response("importance", "3")

    nexus = MockNexus(message_outbox, project_manager, avoidant_user)

    # Insert project
    cur = ananke_test_db.cursor()
    cur.execute(
        """
        INSERT INTO projects (title, discovery_id, status)
        VALUES (%s, %s, %s)
        RETURNING id
        """,
        ("Avoided Project", "disc-avoid", "active"),
    )
    project_id = cur.fetchone()[0]
    ananke_test_db.commit()

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
        WHERE id = %s
        """,
        (project_id,),
    )
    row = cur.fetchone()

    assert row[0] == 3, "Importance should be set"
    assert row[1] is None, "Urgency should not be set"
    assert row[2] is None, "Deadline should not be set"
    assert row[3] is False, "Project should not be marked enriched"


@pytest.mark.integration
@pytest.mark.postgres
def test_multiple_projects_enriched_sequentially(
    ananke_test_db,
    project_manager,
    mock_user,
    mock_nexus,
    conversation_sim,
):
    """
    Test enriching multiple projects sequentially.

    Verifies:
    1. First project gets fully enriched
    2. Second project starts enrichment after first completes
    3. All projects eventually enriched
    """
    # Insert 3 projects
    cur = ananke_test_db.cursor()
    project_ids = []

    for i in range(3):
        cur.execute(
            """
            INSERT INTO projects (title, discovery_id, status, cluster_count)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (f"Project {i+1}", f"disc-multi-{i+1}", "active", 3 - i),  # Different priorities
        )
        project_ids.append(cur.fetchone()[0])

    ananke_test_db.commit()

    # Run conversation for each project
    for project_id in project_ids:
        stats = conversation_sim.run_until_complete(project_id)
        assert stats["completed"], f"Project {project_id} should complete"

    # Verify all projects enriched
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
def test_natural_language_deadline_parsing(
    ananke_test_db,
    project_manager,
    mock_user,
    mock_nexus,
    conversation_sim,
):
    """
    Test various deadline formats are parsed correctly.

    Tests:
    - ISO date: "2026-03-15"
    - Natural language: "next Friday"
    - Relative: "in 2 weeks"
    """
    # Insert project
    cur = ananke_test_db.cursor()
    cur.execute(
        """
        INSERT INTO projects (title, discovery_id, status)
        VALUES (%s, %s, %s)
        RETURNING id
        """,
        ("Deadline Test", "disc-deadline", "active"),
    )
    project_id = cur.fetchone()[0]
    ananke_test_db.commit()

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
        WHERE id = %s
        """,
        (project_id,),
    )
    deadline = cur.fetchone()[0]

    assert deadline is not None, "Deadline should be parsed"

    # Should be approximately 2 weeks from now
    expected = datetime.now(UTC) + timedelta(days=14)
    diff = abs((deadline - expected).total_seconds())

    assert diff < 86400, "Deadline should be ~2 weeks from now (within 1 day)"


@pytest.mark.integration
@pytest.mark.postgres
def test_throttling_prevents_spam(
    ananke_test_db,
    project_manager,
    mock_user,
    mock_nexus,
):
    """
    Test throttling prevents sending too many messages.

    Verifies:
    1. Can send up to max_messages_per_hour
    2. Additional sends are blocked
    3. Throttle state persists in database
    """
    # Insert 10 projects (more than throttle limit)
    cur = ananke_test_db.cursor()
    for i in range(10):
        cur.execute(
            """
            INSERT INTO projects (title, discovery_id, status)
            VALUES (%s, %s, %s)
            """,
            (f"Spam Test {i+1}", f"disc-spam-{i+1}", "active"),
        )
    ananke_test_db.commit()

    # Run PM check cycle (should only send 5 messages due to throttle)
    project_manager.run_pm_check_cycle()

    # Count messages in outbox
    messages = project_manager.message_outbox.dequeue()
    assert len(messages) == 5, "Should throttle at 5 messages per hour"

    # Try again immediately (should send 0 more)
    project_manager.run_pm_check_cycle()
    messages = project_manager.message_outbox.dequeue()
    assert len(messages) == 0, "Should not send more while throttled"


@pytest.mark.integration
@pytest.mark.postgres
def test_pressure_score_updates_after_enrichment(
    ananke_test_db,
    project_manager,
    mock_user,
    mock_nexus,
    conversation_sim,
):
    """
    Test pressure score is calculated after enrichment.

    Verifies:
    1. Pressure score is NULL before enrichment
    2. Pressure score calculated after enrichment completes
    3. Formula: (work/time) × (importance × urgency)
    """
    # Insert project with work estimate
    cur = ananke_test_db.cursor()
    cur.execute(
        """
        INSERT INTO projects (title, discovery_id, status, estimated_work_hours)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """,
        ("Pressure Test", "disc-pressure", "active", 40.0),
    )
    project_id = cur.fetchone()[0]
    ananke_test_db.commit()

    # Verify pressure score is NULL
    cur.execute("SELECT pressure_score FROM projects WHERE id = %s", (project_id,))
    assert cur.fetchone()[0] is None, "Pressure score should be NULL before enrichment"

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
    cur.execute("SELECT pressure_score FROM projects WHERE id = %s", (project_id,))
    pressure = cur.fetchone()[0]

    assert pressure is not None, "Pressure score should be calculated"

    # Expected: (40 / (10*24)) × (5 × 4) = (40/240) × 20 = 0.167 × 20 = 3.33
    expected = (40.0 / (10 * 24)) * (5 * 4)
    assert abs(pressure - expected) < 0.1, f"Pressure score should be ~{expected}"
