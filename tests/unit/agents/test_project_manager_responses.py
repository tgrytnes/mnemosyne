"""
Unit tests for Project Manager Agent Response Handlers (Story 016 - Phase 6)

Tests the event-driven response processing when users answer questions
via Telegram commands (routed through Nexus/Hermes and Message Outbox).
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_db():
    """Mock database connection."""
    db = MagicMock()
    cursor = MagicMock()
    db.cursor.return_value.__enter__.return_value = cursor
    return db


@pytest.fixture
def mock_outbox():
    """Mock Message Outbox."""
    return MagicMock()


@pytest.fixture
def mock_gatekeeper():
    """Mock SQL Gatekeeper."""
    return MagicMock()


@pytest.fixture
def project_manager(mock_db, mock_outbox, mock_gatekeeper):
    """Create ProjectManagerAgent instance with mocks."""
    from mnemosyne.aletheia.agents.project_manager import ProjectManagerAgent

    return ProjectManagerAgent(
        db_conn=mock_db,
        message_outbox=mock_outbox,
        gatekeeper=mock_gatekeeper,
    )


class TestResponseHandlers:
    """Test response processing when user answers questions."""

    def test_handle_importance_response_updates_db_and_asks_next(
        self, project_manager, mock_db, mock_outbox, mock_gatekeeper
    ):
        """
        When user provides importance rating:
        - Update project via gatekeeper
        - Sync to Obsidian
        - Ask next question (urgency)
        """
        # Mock project state: missing urgency
        cursor = mock_db.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (
            1,  # id
            "Test Project",  # title
            "latent_scout",  # discovered_by
            "disco_001",  # discovery_id
            "candidate",  # status
            5,  # importance (just set)
            None,  # urgency (missing)
            None,  # deadline
            None,  # work_estimate
            None,  # pressure_score
            datetime.now(UTC),  # created_at
            datetime.now(UTC),  # updated_at
        )

        # User responds with importance=5
        project_manager.handle_importance_response(project_id=1, value=5)

        # Should update via gatekeeper
        mock_gatekeeper.update_project_direct.assert_called_once_with(
            1, {"importance": 5}, user_initiated=True
        )

        # Should ask next question (urgency)
        mock_outbox.enqueue_message.assert_called_once()
        call_args = mock_outbox.enqueue_message.call_args[1]
        assert "urgency" in call_args["content"].lower()
        assert call_args["metadata"]["project_id"] == 1
        assert call_args["metadata"]["question_type"] == "urgency"

    def test_handle_urgency_response_updates_and_continues(
        self, project_manager, mock_db, mock_outbox, mock_gatekeeper
    ):
        """
        When user provides urgency rating:
        - Update project via gatekeeper
        - If high priority (importance+urgency >= 7), ask deadline
        - If low priority, stop asking
        """
        # Mock project state: high priority (5+4=9)
        cursor = mock_db.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (
            1,
            "Test Project",
            "latent_scout",
            "disco_001",
            "active",
            5,  # importance
            4,  # urgency (just set)
            None,  # deadline (missing)
            None,
            None,
            datetime.now(UTC),
            datetime.now(UTC),
        )

        # User responds with urgency=4
        project_manager.handle_urgency_response(project_id=1, value=4)

        # Should update via gatekeeper
        mock_gatekeeper.update_project_direct.assert_called_once_with(
            1, {"urgency": 4}, user_initiated=True
        )

        # Should ask deadline (high priority: 5+4=9)
        mock_outbox.enqueue_message.assert_called_once()
        call_args = mock_outbox.enqueue_message.call_args[1]
        assert "deadline" in call_args["content"].lower()

    def test_handle_deadline_response_parses_and_updates(
        self, project_manager, mock_db, mock_outbox, mock_gatekeeper
    ):
        """
        When user provides deadline:
        - Parse date string (ISO format or relative duration)
        - Update project via gatekeeper
        - No next question (enrichment complete)
        """
        # Mock project state: fully enriched after deadline
        cursor = mock_db.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (
            1,
            "Test Project",
            "latent_scout",
            "disco_001",
            "active",
            5,  # importance
            4,  # urgency
            datetime.now(UTC) + timedelta(days=30),  # deadline (just set)
            None,
            None,
            datetime.now(UTC),
            datetime.now(UTC),
        )

        # User responds with deadline "2026-03-15"
        project_manager.handle_deadline_response(project_id=1, deadline_text="2026-03-15")

        # Should parse and update via gatekeeper
        mock_gatekeeper.update_project_direct.assert_called_once()
        call_args = mock_gatekeeper.update_project_direct.call_args[0]
        assert call_args[0] == 1  # project_id
        assert "deadline" in call_args[1]  # updates dict

        # Should NOT ask another question (fully enriched)
        mock_outbox.enqueue_message.assert_not_called()

    def test_handle_description_response_updates_text(
        self, project_manager, mock_db, mock_outbox, mock_gatekeeper
    ):
        """
        When user provides richer description:
        - Update description via gatekeeper
        - Sync to Obsidian
        """
        # Mock project state
        cursor = mock_db.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (
            1,
            "Test Project",
            "latent_scout",
            "disco_001",
            "candidate",
            None,
            None,
            None,
            None,
            None,
            datetime.now(UTC),
            datetime.now(UTC),
        )

        # User provides description
        project_manager.handle_description_response(
            project_id=1, description="Build a comprehensive testing framework"
        )

        # Should update via gatekeeper
        mock_gatekeeper.update_project_direct.assert_called_once_with(
            1,
            {"description": "Build a comprehensive testing framework"},
            user_initiated=True,
        )


class TestDeadlineParsing:
    """Test deadline text parsing logic."""

    def test_parse_iso_date(self, project_manager):
        """Parse ISO format date: 2026-03-15"""
        result = project_manager._parse_deadline("2026-03-15")
        assert result.year == 2026
        assert result.month == 3
        assert result.day == 15

    def test_parse_natural_date(self, project_manager):
        """Parse natural date: March 15"""
        result = project_manager._parse_deadline("March 15")
        assert result.month == 3
        assert result.day == 15

    def test_parse_relative_duration_weeks(self, project_manager):
        """Parse relative duration: 2 weeks"""
        now = datetime.now(UTC)
        result = project_manager._parse_deadline("2 weeks")

        # Should be ~14 days from now
        delta = (result - now).days
        assert 13 <= delta <= 15  # Allow some tolerance

    def test_parse_relative_duration_months(self, project_manager):
        """Parse relative duration: 1 month"""
        now = datetime.now(UTC)
        result = project_manager._parse_deadline("1 month")

        # Should be ~30 days from now
        delta = (result - now).days
        assert 28 <= delta <= 32  # Allow tolerance for month length

    def test_parse_no_deadline_returns_none(self, project_manager):
        """Parse 'no deadline' returns None"""
        result = project_manager._parse_deadline("no deadline")
        assert result is None

        result = project_manager._parse_deadline("flexible")
        assert result is None


class TestResponseValidation:
    """Test input validation for user responses."""

    def test_importance_validates_range(self, project_manager, mock_db, mock_gatekeeper):
        """Importance must be 1-5."""
        with pytest.raises(ValueError, match="1 and 5"):
            project_manager.handle_importance_response(project_id=1, value=0)

        with pytest.raises(ValueError, match="1 and 5"):
            project_manager.handle_importance_response(project_id=1, value=6)

        # Valid values should not raise
        cursor = mock_db.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (
            1,
            "Test",
            "scout",
            "disco",
            "candidate",
            3,
            None,
            None,
            None,
            None,
            datetime.now(UTC),
            datetime.now(UTC),
        )
        project_manager.handle_importance_response(project_id=1, value=3)  # OK

    def test_urgency_validates_range(self, project_manager, mock_db, mock_gatekeeper):
        """Urgency must be 1-5."""
        with pytest.raises(ValueError, match="1 and 5"):
            project_manager.handle_urgency_response(project_id=1, value=0)

        with pytest.raises(ValueError, match="1 and 5"):
            project_manager.handle_urgency_response(project_id=1, value=7)

    def test_invalid_deadline_format_raises_error(self, project_manager):
        """Invalid deadline format should raise ParseError."""
        with pytest.raises(ValueError, match="[Cc]ould not parse"):
            project_manager._parse_deadline("invalid date format xyz")


class TestGatekeeperIntegration:
    """Test integration with SQL Gatekeeper for direct updates."""

    def test_all_responses_use_gatekeeper_direct_update(
        self, project_manager, mock_db, mock_outbox, mock_gatekeeper
    ):
        """
        All response handlers should use gatekeeper.update_project_direct()
        with user_initiated=True (not agent updates).
        """
        cursor = mock_db.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (
            1,
            "Test",
            "scout",
            "disco",
            "candidate",
            5,
            4,
            None,
            None,
            None,
            datetime.now(UTC),
            datetime.now(UTC),
        )

        # Test importance response
        project_manager.handle_importance_response(project_id=1, value=5)
        assert mock_gatekeeper.update_project_direct.call_args[1]["user_initiated"] is True

        mock_gatekeeper.reset_mock()

        # Test urgency response
        project_manager.handle_urgency_response(project_id=1, value=4)
        assert mock_gatekeeper.update_project_direct.call_args[1]["user_initiated"] is True

    def test_gatekeeper_triggers_obsidian_sync(
        self, project_manager, mock_db, mock_outbox, mock_gatekeeper
    ):
        """
        Gatekeeper should trigger Obsidian sync after direct update.
        (This is tested via gatekeeper's own tests, but we verify the call)
        """
        cursor = mock_db.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (
            1,
            "Test",
            "scout",
            "disco",
            "candidate",
            5,
            None,
            None,
            None,
            None,
            datetime.now(UTC),
            datetime.now(UTC),
        )

        project_manager.handle_importance_response(project_id=1, value=5)

        # Verify gatekeeper was called (sync happens inside gatekeeper)
        mock_gatekeeper.update_project_direct.assert_called_once()


class TestEventDrivenFlow:
    """Test event-driven question flow."""

    def test_importance_triggers_urgency_question(
        self, project_manager, mock_db, mock_outbox, mock_gatekeeper
    ):
        """After importance is set, urgency question is automatically asked."""
        cursor = mock_db.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (
            1,
            "Test",
            "scout",
            "disco",
            "candidate",
            5,
            None,
            None,
            None,
            None,  # urgency missing
            datetime.now(UTC),
            datetime.now(UTC),
        )

        project_manager.handle_importance_response(project_id=1, value=5)

        # Should ask urgency
        assert mock_outbox.enqueue_message.called
        call_args = mock_outbox.enqueue_message.call_args[1]
        assert call_args["metadata"]["question_type"] == "urgency"

    def test_low_priority_stops_asking(
        self, project_manager, mock_db, mock_outbox, mock_gatekeeper
    ):
        """Low priority projects (importance+urgency < 7) don't get deadline question."""
        cursor = mock_db.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (
            1,
            "Test",
            "scout",
            "disco",
            "candidate",
            2,
            2,
            None,
            None,
            None,  # importance=2, urgency=2 (total=4)
            datetime.now(UTC),
            datetime.now(UTC),
        )

        project_manager.handle_urgency_response(project_id=1, value=2)

        # Should NOT ask deadline (low priority)
        mock_outbox.enqueue_message.assert_not_called()

    def test_high_priority_asks_deadline(
        self, project_manager, mock_db, mock_outbox, mock_gatekeeper
    ):
        """High priority projects (importance+urgency >= 7) get deadline question."""
        cursor = mock_db.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (
            1,
            "Test",
            "scout",
            "disco",
            "active",
            5,
            4,
            None,
            None,
            None,  # importance=5, urgency=4 (total=9)
            datetime.now(UTC),
            datetime.now(UTC),
        )

        project_manager.handle_urgency_response(project_id=1, value=4)

        # Should ask deadline (high priority)
        assert mock_outbox.enqueue_message.called
        call_args = mock_outbox.enqueue_message.call_args[1]
        assert call_args["metadata"]["question_type"] == "deadline"
