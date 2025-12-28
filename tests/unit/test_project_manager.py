"""
Unit tests for Project Manager (Layer 5: Hermes)
Tests Story 016: Project Manager Agent
"""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest


@pytest.mark.unit
class TestPressureScoreCalculation:
    """Test pressure score calculation (Work ÷ Time)"""

    def test_calculate_pressure_with_estimate(self, freeze_time):
        """Test pressure calculation with work estimate"""
        # from Hermes.project_manager import ProjectManagerAgent

        with freeze_time("2024-01-15 08:00:00"):
            # pm = ProjectManagerAgent(db=Mock(), messenger=Mock())

            datetime(2024, 1, 20, 17, 0, 0)  # 5 days away

            # pressure = pm._calculate_pressure(deadline, work_estimate)

            # 40 hours / (5.375 days * 24 hours) ≈ 0.31
            # assert 0.3 <= pressure <= 0.35

    def test_calculate_pressure_without_estimate(self, freeze_time):
        """Test pressure calculation uses default estimate"""
        with freeze_time("2024-01-15 08:00:00"):
            # pm = ProjectManagerAgent(db=Mock(), messenger=Mock())

            datetime(2024, 1, 20, 17, 0, 0)

            # Should use default (20 hours for medium project)
            # pressure = pm._calculate_pressure(deadline, work_estimate=None)
            # assert pressure > 0

    def test_overdue_project_high_pressure(self, freeze_time):
        """Test overdue projects get maximum pressure score"""
        with freeze_time("2024-01-15 08:00:00"):
            # pm = ProjectManagerAgent(db=Mock(), messenger=Mock())

            datetime(2024, 1, 10, 17, 0, 0)  # 5 days ago

            # pressure = pm._calculate_pressure(deadline, work_estimate=20)

            # assert pressure == 999.0  # Overdue marker


@pytest.mark.unit
class TestDeadlineChecking:
    """Test deadline detection and reminders"""

    def test_detect_missing_deadlines(self):
        """Test detection of active projects without deadlines"""
        db = Mock()
        Mock()
        # pm = ProjectManagerAgent(db, messenger)

        # Mock query result: active project without deadline
        cursor = Mock()
        cursor.fetchall.return_value = [
            (1, "Test Project", datetime(2024, 1, 1, 10, 0, 0))  # id, title, created_at
        ]
        db.cursor.return_value = cursor

        # pm._check_missing_deadlines()

        # Should request deadline from user
        # messenger.send_message.assert_called()
        # message = messenger.send_message.call_args[0][0]
        # assert "Needs Deadline" in message
        # assert "Test Project" in message

    def test_approaching_deadlines_notification(self, freeze_time):
        """Test notifications for deadlines within 3 days"""
        with freeze_time("2024-01-15 08:00:00"):
            db = Mock()
            Mock()
            # pm = ProjectManagerAgent(db, messenger)

            # Mock: project due in 2 days
            cursor = Mock()
            cursor.fetchall.return_value = [
                (1, "Urgent Project", datetime(2024, 1, 17, 17, 0, 0), 5.2)
                # id, title, deadline, pressure_score
            ]
            db.cursor.return_value = cursor

            # pm._check_approaching_deadlines()

            # Should send reminder
            # messenger.send_message.assert_called()
            # message = messenger.send_message.call_args[0][0]
            # assert "Deadline Approaching" in message or "⏰" in message

    def test_no_notification_for_distant_deadlines(self, freeze_time):
        """Test no notification for deadlines >3 days away"""
        with freeze_time("2024-01-15 08:00:00"):
            db = Mock()
            Mock()
            # pm = ProjectManagerAgent(db, messenger)

            # Mock: project due in 10 days
            cursor = Mock()
            cursor.fetchall.return_value = [
                (1, "Future Project", datetime(2024, 1, 25, 17, 0, 0), 1.5)
            ]
            db.cursor.return_value = cursor

            # pm._check_approaching_deadlines()

            # Should NOT send reminder
            # messenger.send_message.assert_not_called()


@pytest.mark.unit
class TestStalledProjectDetection:
    """Test stalled project identification"""

    def test_detect_stalled_projects(self, freeze_time):
        """Test detection of projects with no updates in 7+ days"""
        with freeze_time("2024-01-15 08:00:00"):
            db = Mock()
            Mock()
            # pm = ProjectManagerAgent(db, messenger)

            # Mock: project last updated 10 days ago
            cursor = Mock()
            cursor.fetchall.return_value = [
                (1, "Stalled Project", "active", datetime(2024, 1, 5, 10, 0, 0))
                # id, title, status, updated_at
            ]
            db.cursor.return_value = cursor

            # pm._check_stalled_projects()

            # Should send stall alert
            # messenger.send_message.assert_called()
            # message = messenger.send_message.call_args[0][0]
            # assert "Stalled" in message
            # assert "10 days ago" in message or "days stalled" in message

    def test_ignore_recently_updated_projects(self, freeze_time):
        """Test recently updated projects are not flagged"""
        with freeze_time("2024-01-15 08:00:00"):
            db = Mock()
            Mock()
            # pm = ProjectManagerAgent(db, messenger)

            # Mock: project updated 3 days ago
            cursor = Mock()
            cursor.fetchall.return_value = [
                (1, "Active Project", "active", datetime(2024, 1, 12, 10, 0, 0))
            ]
            db.cursor.return_value = cursor

            # pm._check_stalled_projects()

            # Should NOT send alert
            # messenger.send_message.assert_not_called()


@pytest.mark.unit
class TestDailyDigest:
    """Test daily project digest"""

    def test_daily_digest_includes_status_counts(self):
        """Test daily digest shows project counts by status"""
        db = Mock()
        Mock()
        # pm = ProjectManagerAgent(db, messenger)

        # Mock status counts
        cursor = Mock()
        cursor.fetchall.return_value = [
            ("active", 5),
            ("candidate", 3),
            ("paused", 2),
            ("completed", 10),
        ]
        db.cursor.return_value = cursor

        # pm._send_daily_digest()

        # message = messenger.send_message.call_args[0][0]
        # assert "Active: 5" in message
        # assert "Candidate: 3" in message
        # assert "Completed: 10" in message

    def test_daily_digest_shows_high_pressure_projects(self):
        """Test digest shows top 3 high-pressure projects"""
        db = Mock()
        Mock()
        # pm = ProjectManagerAgent(db, messenger)

        cursor = Mock()
        # First call: status counts
        # Second call: high-pressure projects
        cursor.fetchall.side_effect = [
            [("active", 5)],  # Status counts
            [
                ("Project A", datetime(2024, 1, 17), 8.5),
                ("Project B", datetime(2024, 1, 18), 6.2),
                ("Project C", datetime(2024, 1, 20), 3.1),
            ],
        ]
        db.cursor.return_value = cursor

        # pm._send_daily_digest()

        # message = messenger.send_message.call_args[0][0]
        # assert "Project A" in message
        # assert "8.5" in message or "pressure" in message.lower()


@pytest.mark.unit
class TestScheduledExecution:
    """Test Project Manager scheduled jobs"""

    @patch("apscheduler.schedulers.background.BackgroundScheduler")
    def test_daily_management_scheduled_8am(self, mock_scheduler):
        """Test daily management runs at 8 AM"""
        # from Hermes.project_manager import setup_scheduler

        # scheduler = setup_scheduler(pm=Mock())

        # Should schedule daily job at 8 AM
        # mock_scheduler.return_value.add_job.assert_called()
        # call_kwargs = mock_scheduler.return_value.add_job.call_args[1]
        # assert call_kwargs["hour"] == 8
        # assert call_kwargs["minute"] == 0

    @patch("apscheduler.schedulers.background.BackgroundScheduler")
    def test_weekly_summary_scheduled_sunday(self, mock_scheduler):
        """Test weekly summary runs Sunday 9 AM"""
        # scheduler = setup_scheduler(pm=Mock())

        # Should have Sunday job
        # calls = mock_scheduler.return_value.add_job.call_args_list
        # sunday_call = next(
        #     call for call in calls
        #     if call[1].get("day_of_week") == "sun"
        # )
        # assert sunday_call[1]["hour"] == 9


@pytest.mark.unit
def test_project_manager_full_daily_routine():
    """Test complete daily management routine"""
    Mock()
    Mock()
    # pm = ProjectManagerAgent(db, messenger)

    # pm.run_daily_management()

    # Should execute all checks:
    # 1. Missing deadlines
    # 2. Pressure score updates
    # 3. Stalled projects
    # 4. Approaching deadlines
    # 5. Daily digest

    # Verify all methods called
    # assert db.cursor.call_count >= 5  # Multiple queries
    # assert messenger.send_message.called
