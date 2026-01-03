"""
Unit tests for Project Manager Agent (Story 016)

Tests the core agent logic for incremental project enrichment,
natural PM rhythm, and pressure score calculations.

TDD Approach: These tests are written BEFORE implementation (RED phase).
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest

# ==============================================================================
# Test Fixtures
# ==============================================================================


@pytest.fixture
def mock_db_conn():
    """Mock PostgreSQL connection"""
    conn = Mock()
    cursor = Mock()
    cursor.__enter__ = Mock(return_value=cursor)
    cursor.__exit__ = Mock(return_value=None)
    conn.cursor.return_value = cursor
    return conn


@pytest.fixture
def mock_outbox():
    """Mock Message Outbox"""
    outbox = Mock()
    outbox.enqueue_message = Mock(return_value={"id": "msg_123", "status": "pending"})
    return outbox


@pytest.fixture
def mock_gatekeeper():
    """Mock SQL Gatekeeper"""
    gatekeeper = Mock()
    gatekeeper.update_project_direct = Mock(return_value=True)
    return gatekeeper


@pytest.fixture
def sample_projects():
    """Sample project data for testing"""
    now = datetime.now(UTC)
    return [
        {
            "id": 1,
            "title": "New Project Needing Metadata",
            "discovered_by": "latent_scout",
            "discovery_id": "disco_001",
            "status": "candidate",
            "importance": None,  # Missing
            "urgency": None,  # Missing
            "deadline": None,
            "work_estimate": None,
            "pressure_score": None,
            "created_at": now - timedelta(hours=2),
            "updated_at": now - timedelta(hours=2),
        },
        {
            "id": 2,
            "title": "Has Importance, Needs Urgency",
            "discovered_by": "latent_scout",
            "discovery_id": "disco_002",
            "status": "active",
            "importance": 5,  # High importance
            "urgency": None,  # Missing
            "deadline": None,
            "work_estimate": None,
            "pressure_score": None,
            "created_at": now - timedelta(days=1),
            "updated_at": now - timedelta(hours=6),
        },
        {
            "id": 3,
            "title": "High Priority Needs Deadline",
            "discovered_by": "latent_scout",
            "discovery_id": "disco_003",
            "status": "active",
            "importance": 5,
            "urgency": 4,  # High priority (9 total)
            "deadline": None,  # Missing for high-priority project
            "work_estimate": 20,
            "pressure_score": None,
            "created_at": now - timedelta(days=3),
            "updated_at": now - timedelta(days=1),
        },
        {
            "id": 4,
            "title": "Fully Enriched Project",
            "discovered_by": "latent_scout",
            "discovery_id": "disco_004",
            "status": "active",
            "importance": 3,
            "urgency": 3,
            "deadline": now + timedelta(days=30),
            "work_estimate": 10,
            "pressure_score": 0.42,
            "created_at": now - timedelta(days=10),
            "updated_at": now - timedelta(days=2),
        },
    ]


# ==============================================================================
# Enrichment Queue Tests
# ==============================================================================


class TestEnrichmentQueue:
    """Test building prioritized enrichment queue"""

    def test_build_queue_prioritizes_new_projects_first(
        self, mock_db_conn, mock_outbox, sample_projects
    ):
        """Test that new projects without any metadata come first"""
        from mnemosyne.aletheia.agents.project_manager import ProjectManagerAgent

        agent = ProjectManagerAgent(mock_db_conn, mock_outbox)

        # Mock database to return sample projects
        cursor = mock_db_conn.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = sample_projects

        queue = agent._build_enrichment_queue()

        # First item should be project #1 (no metadata at all)
        assert queue[0]["id"] == 1
        assert queue[0]["stage"] == "importance"

    def test_build_queue_stage_1_requests_importance(
        self, mock_db_conn, mock_outbox, sample_projects
    ):
        """Test Stage 1: Request importance for projects missing it"""
        from mnemosyne.aletheia.agents.project_manager import ProjectManagerAgent

        agent = ProjectManagerAgent(mock_db_conn, mock_outbox)
        cursor = mock_db_conn.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = sample_projects

        queue = agent._build_enrichment_queue()

        # Project #1 should need importance
        importance_items = [q for q in queue if q["stage"] == "importance"]
        assert any(item["id"] == 1 for item in importance_items)

    def test_build_queue_stage_2_requests_urgency(self, mock_db_conn, mock_outbox, sample_projects):
        """Test Stage 2: Request urgency for projects with importance but no urgency"""
        from mnemosyne.aletheia.agents.project_manager import ProjectManagerAgent

        agent = ProjectManagerAgent(mock_db_conn, mock_outbox)
        cursor = mock_db_conn.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = sample_projects

        queue = agent._build_enrichment_queue()

        # Project #2 has importance=5, needs urgency
        urgency_items = [q for q in queue if q["stage"] == "urgency"]
        assert any(item["id"] == 2 for item in urgency_items)

    def test_build_queue_stage_3_focuses_on_high_priority(
        self, mock_db_conn, mock_outbox, sample_projects
    ):
        """Test Stage 3: Focus on high-priority projects (importance+urgency >= 7)"""
        from mnemosyne.aletheia.agents.project_manager import ProjectManagerAgent

        agent = ProjectManagerAgent(mock_db_conn, mock_outbox)
        cursor = mock_db_conn.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = sample_projects

        queue = agent._build_enrichment_queue()

        # Project #3 has importance=5, urgency=4 (total=9, high priority)
        # Should be prioritized for deadline
        high_priority = [q for q in queue if q["id"] == 3 and q["stage"] == "deadline"]
        assert len(high_priority) > 0

    def test_build_queue_skips_fully_enriched_projects(
        self, mock_db_conn, mock_outbox, sample_projects
    ):
        """Test that fully enriched projects don't appear in queue"""
        from mnemosyne.aletheia.agents.project_manager import ProjectManagerAgent

        agent = ProjectManagerAgent(mock_db_conn, mock_outbox)
        cursor = mock_db_conn.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = sample_projects

        queue = agent._build_enrichment_queue()

        # Project #4 has all metadata - should not be in queue
        assert not any(item["id"] == 4 for item in queue)

    def test_build_queue_returns_empty_for_no_projects(self, mock_db_conn, mock_outbox):
        """Test that empty project list returns empty queue"""
        from mnemosyne.aletheia.agents.project_manager import ProjectManagerAgent

        agent = ProjectManagerAgent(mock_db_conn, mock_outbox)
        cursor = mock_db_conn.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = []

        queue = agent._build_enrichment_queue()

        assert queue == []


# ==============================================================================
# Question Handler Tests
# ==============================================================================


class TestQuestionHandlers:
    """Test question formatting and enqueueing"""

    def test_request_importance_formats_message(self, mock_db_conn, mock_outbox):
        """Test importance question formatting"""
        from mnemosyne.aletheia.agents.project_manager import ProjectManagerAgent

        agent = ProjectManagerAgent(mock_db_conn, mock_outbox)

        project = {
            "id": 42,
            "title": "Implement Dark Mode",
            "description": "Add dark mode toggle to settings",
        }

        agent._request_importance(project)

        # Should enqueue message
        mock_outbox.enqueue_message.assert_called_once()
        call_args = mock_outbox.enqueue_message.call_args[1]

        # Check message content
        assert "importance" in call_args["content"].lower()
        assert "Implement Dark Mode" in call_args["content"]
        assert call_args["expects_response"] is True
        assert call_args["sender"] == "project_manager"
        assert call_args["metadata"]["project_id"] == 42
        assert call_args["metadata"]["question_type"] == "importance"

    def test_request_urgency_formats_message(self, mock_db_conn, mock_outbox):
        """Test urgency question formatting"""
        from mnemosyne.aletheia.agents.project_manager import ProjectManagerAgent

        agent = ProjectManagerAgent(mock_db_conn, mock_outbox)

        project = {
            "id": 42,
            "title": "Implement Dark Mode",
            "importance": 5,
        }

        agent._request_urgency(project)

        mock_outbox.enqueue_message.assert_called_once()
        call_args = mock_outbox.enqueue_message.call_args[1]

        assert "urgency" in call_args["content"].lower()
        assert call_args["expects_response"] is True
        assert call_args["metadata"]["question_type"] == "urgency"

    def test_request_deadline_formats_message(self, mock_db_conn, mock_outbox):
        """Test deadline question formatting"""
        from mnemosyne.aletheia.agents.project_manager import ProjectManagerAgent

        agent = ProjectManagerAgent(mock_db_conn, mock_outbox)

        project = {
            "id": 42,
            "title": "Implement Dark Mode",
            "importance": 5,
            "urgency": 4,
        }

        agent._request_deadline(project)

        mock_outbox.enqueue_message.assert_called_once()
        call_args = mock_outbox.enqueue_message.call_args[1]

        assert "deadline" in call_args["content"].lower()
        assert call_args["expects_response"] is True
        assert call_args["metadata"]["question_type"] == "deadline"

    def test_request_description_formats_message(self, mock_db_conn, mock_outbox):
        """Test description enrichment question formatting"""
        from mnemosyne.aletheia.agents.project_manager import ProjectManagerAgent

        agent = ProjectManagerAgent(mock_db_conn, mock_outbox)

        project = {
            "id": 42,
            "title": "Implement Dark Mode",
            "description": "Add feature",  # Vague description
        }

        agent._request_description(project)

        mock_outbox.enqueue_message.assert_called_once()
        call_args = mock_outbox.enqueue_message.call_args[1]

        assert (
            "describe" in call_args["content"].lower()
            or "description" in call_args["content"].lower()
        )
        assert call_args["expects_response"] is True
        assert call_args["metadata"]["question_type"] == "description"


# ==============================================================================
# Event-Driven Response Handler Tests
# ==============================================================================


class TestResponseHandler:
    """Test event-driven enrichment continuation"""

    def test_continue_enrichment_asks_next_question(self, mock_db_conn, mock_outbox):
        """Test that continue_enrichment asks the next missing field"""
        from mnemosyne.aletheia.agents.project_manager import ProjectManagerAgent

        agent = ProjectManagerAgent(mock_db_conn, mock_outbox)

        # Project just got importance, now needs urgency
        cursor = mock_db_conn.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (
            42,
            "Test Project",
            "latent_scout",
            "d1",
            "active",
            5,
            None,
            None,
            None,
            None,  # has importance, missing urgency
            datetime.now(UTC),
            datetime.now(UTC),
        )

        agent.continue_enrichment(project_id=42)

        # Should call _request_urgency
        mock_outbox.enqueue_message.assert_called_once()
        call_args = mock_outbox.enqueue_message.call_args[1]
        assert call_args["metadata"]["question_type"] == "urgency"

    def test_continue_enrichment_stops_when_complete(self, mock_db_conn, mock_outbox):
        """Test that continue_enrichment stops when all metadata present"""
        from mnemosyne.aletheia.agents.project_manager import ProjectManagerAgent

        agent = ProjectManagerAgent(mock_db_conn, mock_outbox)

        # Fully enriched project
        cursor = mock_db_conn.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (
            42,
            "Test Project",
            "latent_scout",
            "d1",
            "active",
            5,
            4,
            datetime.now(UTC) + timedelta(days=30),
            20,
            0.5,
            datetime.now(UTC),
            datetime.now(UTC),
        )

        agent.continue_enrichment(project_id=42)

        # Should NOT enqueue any messages
        mock_outbox.enqueue_message.assert_not_called()

    def test_continue_enrichment_handles_nonexistent_project(self, mock_db_conn, mock_outbox):
        """Test handling of nonexistent project ID"""
        from mnemosyne.aletheia.agents.project_manager import ProjectManagerAgent

        agent = ProjectManagerAgent(mock_db_conn, mock_outbox)

        cursor = mock_db_conn.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = None

        # Should handle gracefully, not crash
        agent.continue_enrichment(project_id=99999)

        mock_outbox.enqueue_message.assert_not_called()


# ==============================================================================
# PM Check Cycle Tests
# ==============================================================================


class TestPMCheckCycle:
    """Test natural PM rhythm check cycle"""

    def test_run_pm_check_cycle_processes_new_projects(
        self, mock_db_conn, mock_outbox, sample_projects
    ):
        """Test that check cycle processes new projects"""
        from mnemosyne.aletheia.agents.project_manager import ProjectManagerAgent

        agent = ProjectManagerAgent(mock_db_conn, mock_outbox)

        cursor = mock_db_conn.cursor.return_value.__enter__.return_value
        # Mock fetchone for multiple queries (message count, then project details)
        cursor.fetchone.side_effect = [
            (0,),  # Message count
            (1, "New Project", None, None, "Description"),  # Project details
        ]
        cursor.fetchall.return_value = sample_projects

        agent.run_pm_check_cycle()

        # Should ask at least one question for new projects
        assert mock_outbox.enqueue_message.call_count >= 1

    def test_messages_sent_last_hour_counts_correctly(self, mock_db_conn, mock_outbox):
        """Test counting messages sent in last hour"""
        from mnemosyne.aletheia.agents.project_manager import ProjectManagerAgent

        agent = ProjectManagerAgent(mock_db_conn, mock_outbox)

        datetime.now(UTC)
        cursor = mock_db_conn.cursor.return_value.__enter__.return_value

        # 3 messages in last hour, 2 older
        cursor.fetchone.return_value = (3,)

        count = agent._messages_sent_last_hour()

        assert count == 3

    def test_check_cycle_respects_throttling(self, mock_db_conn, mock_outbox, sample_projects):
        """Test that check cycle respects message throttling"""
        from mnemosyne.aletheia.agents.project_manager import ProjectManagerAgent

        agent = ProjectManagerAgent(mock_db_conn, mock_outbox)
        agent.max_messages_per_hour = 5

        cursor = mock_db_conn.cursor.return_value.__enter__.return_value

        # Simulate already sent 5 messages this hour
        cursor.fetchone.return_value = (5,)
        cursor.fetchall.return_value = sample_projects

        agent.run_pm_check_cycle()

        # Should not send more messages (throttled)
        mock_outbox.enqueue_message.assert_not_called()

    def test_get_critical_deadlines_identifies_urgent_items(self, mock_db_conn, mock_outbox):
        """Test identifying projects with deadlines <24 hours"""
        from mnemosyne.aletheia.agents.project_manager import ProjectManagerAgent

        agent = ProjectManagerAgent(mock_db_conn, mock_outbox)

        now = datetime.now(UTC)
        cursor = mock_db_conn.cursor.return_value.__enter__.return_value

        # Project with deadline in 12 hours
        cursor.fetchall.return_value = [(42, "Urgent Project", now + timedelta(hours=12), 5, 5)]

        critical = agent._get_critical_deadlines()

        assert len(critical) == 1
        assert critical[0][0] == 42

    def test_handle_critical_deadline_sends_urgent_reminder(self, mock_db_conn, mock_outbox):
        """Test sending urgent reminder for critical deadline"""
        from mnemosyne.aletheia.agents.project_manager import ProjectManagerAgent

        agent = ProjectManagerAgent(mock_db_conn, mock_outbox)

        now = datetime.now(UTC)
        project = {
            "id": 42,
            "title": "Urgent Task",
            "deadline": now + timedelta(hours=6),
            "importance": 5,
            "urgency": 5,
        }

        agent._handle_critical_deadline(project)

        mock_outbox.enqueue_message.assert_called_once()
        call_args = mock_outbox.enqueue_message.call_args[1]

        # Should be urgent tone
        assert (
            "urgent" in call_args["content"].lower() or "deadline" in call_args["content"].lower()
        )


# ==============================================================================
# Pressure Score Tests
# ==============================================================================


class TestPressureScore:
    """Test pressure score calculation"""

    def test_update_pressure_scores_calculates_time_pressure(self, mock_db_conn, mock_gatekeeper):
        """Test pressure score = work_estimate / time_remaining"""
        from mnemosyne.aletheia.agents.project_manager import ProjectManagerAgent

        agent = ProjectManagerAgent(mock_db_conn, Mock(), mock_gatekeeper)

        now = datetime.now(UTC)
        cursor = mock_db_conn.cursor.return_value.__enter__.return_value

        # Project: 20 hours work, 10 days remaining
        cursor.fetchall.return_value = [(42, 20, now + timedelta(days=10), 5, 4)]

        agent._update_pressure_scores()

        # Pressure = 20 / (10 * 24) = 20 / 240 = 0.083
        # With priority factor (5 * 4 = 20): 0.083 * 20 = 1.67
        mock_gatekeeper.update_project_direct.assert_called()
        call_args = mock_gatekeeper.update_project_direct.call_args[0]

        # Check pressure score was calculated (approximate)
        assert "pressure_score" in call_args[1]
        assert call_args[1]["pressure_score"] > 0

    def test_pressure_score_overdue_project(self, mock_db_conn, mock_gatekeeper):
        """Test that overdue projects get maximum pressure score"""
        from mnemosyne.aletheia.agents.project_manager import ProjectManagerAgent

        agent = ProjectManagerAgent(mock_db_conn, Mock(), mock_gatekeeper)

        now = datetime.now(UTC)
        cursor = mock_db_conn.cursor.return_value.__enter__.return_value

        # Project is overdue (deadline in the past)
        cursor.fetchall.return_value = [(42, 20, now - timedelta(days=1), 5, 5)]

        agent._update_pressure_scores()

        call_args = mock_gatekeeper.update_project_direct.call_args[0]
        assert call_args[1]["pressure_score"] == 999.0  # Max pressure

    def test_pressure_score_no_deadline_returns_none(self, mock_db_conn, mock_gatekeeper):
        """Test that projects without deadline don't get pressure score"""
        from mnemosyne.aletheia.agents.project_manager import ProjectManagerAgent

        agent = ProjectManagerAgent(mock_db_conn, Mock(), mock_gatekeeper)

        cursor = mock_db_conn.cursor.return_value.__enter__.return_value

        # Project without deadline
        cursor.fetchall.return_value = [(42, 20, None, 5, 4)]

        agent._update_pressure_scores()

        # Should not update projects without deadlines
        mock_gatekeeper.update_project_direct.assert_not_called()


# ==============================================================================
# Reminder Handler Tests
# ==============================================================================


class TestReminderHandlers:
    """Test reminder escalation logic"""

    def test_send_gentle_reminder_uses_friendly_tone(self, mock_db_conn, mock_outbox):
        """Test gentle reminder has friendly, non-pushy tone"""
        from mnemosyne.aletheia.agents.project_manager import ProjectManagerAgent

        agent = ProjectManagerAgent(mock_db_conn, mock_outbox)

        project = {
            "id": 42,
            "title": "Test Project",
            "unanswered_questions": 1,
        }

        agent._send_gentle_reminder(project, "importance")

        mock_outbox.enqueue_message.assert_called_once()
        call_args = mock_outbox.enqueue_message.call_args[1]

        # Should be gentle (no "urgent", "critical", etc.)
        content_lower = call_args["content"].lower()
        assert "urgent" not in content_lower
        assert "critical" not in content_lower

    def test_send_escalated_reminder_for_high_priority(self, mock_db_conn, mock_outbox):
        """Test escalated reminder for high-priority items"""
        from mnemosyne.aletheia.agents.project_manager import ProjectManagerAgent

        agent = ProjectManagerAgent(mock_db_conn, mock_outbox)

        project = {
            "id": 42,
            "title": "High Priority Task",
            "importance": 5,
            "urgency": 5,
            "unanswered_questions": 3,
        }

        agent._send_escalated_reminder(project, "deadline")

        mock_outbox.enqueue_message.assert_called_once()
        call_args = mock_outbox.enqueue_message.call_args[1]

        # Should mention high priority
        assert (
            "important" in call_args["content"].lower()
            or "priority" in call_args["content"].lower()
        )

    def test_mark_as_avoiding_after_many_questions(self, mock_db_conn, mock_gatekeeper):
        """Test marking project as user avoiding after 5+ unanswered questions"""
        from mnemosyne.aletheia.agents.project_manager import ProjectManagerAgent

        agent = ProjectManagerAgent(mock_db_conn, Mock(), mock_gatekeeper)

        project_id = 42

        agent._mark_as_avoiding(project_id)

        # Should update project status or add metadata
        mock_gatekeeper.update_project_direct.assert_called()
        call_args = mock_gatekeeper.update_project_direct.call_args

        # Check it marks as avoiding
        assert call_args[0][0] == 42

    def test_stop_asking_for_low_priority(self, mock_db_conn, mock_gatekeeper):
        """Test stopping questions for low-priority items after multiple attempts"""
        from mnemosyne.aletheia.agents.project_manager import ProjectManagerAgent

        agent = ProjectManagerAgent(mock_db_conn, Mock(), mock_gatekeeper)

        project = {
            "id": 42,
            "importance": 1,  # Low priority
            "urgency": 1,
            "unanswered_questions": 4,
        }

        result = agent._should_stop_asking(project)

        # Should stop asking for low-priority items
        assert result is True

    def test_continue_asking_for_high_priority(self, mock_db_conn):
        """Test continuing to ask for high-priority items"""
        from mnemosyne.aletheia.agents.project_manager import ProjectManagerAgent

        agent = ProjectManagerAgent(mock_db_conn, Mock())

        project = {
            "id": 42,
            "importance": 5,  # High priority
            "urgency": 5,
            "unanswered_questions": 4,
        }

        result = agent._should_stop_asking(project)

        # Should continue asking for high-priority items
        assert result is False
