"""
Unit tests for Project Manager Agent Scheduler (Story 016 - Phase 7)

Tests the APScheduler integration for running PM check cycles and
pressure score updates on a natural rhythm (30 min / 1 hour).
"""

from unittest.mock import MagicMock, Mock, patch

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


class TestSchedulerSetup:
    """Test APScheduler setup and job registration."""

    def test_scheduler_creates_background_scheduler(self, project_manager):
        """Test that scheduler creates a BackgroundScheduler instance."""
        from mnemosyne.aletheia.agents.project_manager_scheduler import (
            ProjectManagerScheduler,
        )

        with patch(
            "mnemosyne.aletheia.agents.project_manager_scheduler.BackgroundScheduler"
        ) as mock_scheduler_class:
            mock_scheduler = MagicMock()
            mock_scheduler_class.return_value = mock_scheduler

            scheduler = ProjectManagerScheduler(project_manager=project_manager)
            scheduler.start()  # Scheduler is created in start()

            # Should create BackgroundScheduler
            mock_scheduler_class.assert_called_once()

    def test_scheduler_registers_pm_check_cycle_job(self, project_manager):
        """Test PM check cycle job is registered with 30-minute interval."""
        from mnemosyne.aletheia.agents.project_manager_scheduler import (
            ProjectManagerScheduler,
        )

        with patch(
            "mnemosyne.aletheia.agents.project_manager_scheduler.BackgroundScheduler"
        ) as mock_scheduler_class:
            mock_scheduler = MagicMock()
            mock_scheduler_class.return_value = mock_scheduler

            scheduler = ProjectManagerScheduler(project_manager=project_manager)
            scheduler.start()

            # Should register PM check cycle job
            add_job_calls = mock_scheduler.add_job.call_args_list

            # Find the PM check cycle job
            pm_check_job = None
            for call_item in add_job_calls:
                kwargs = call_item.kwargs
                if kwargs.get("id") == "pm_check_cycle":
                    pm_check_job = kwargs
                    break

            assert pm_check_job is not None
            assert pm_check_job["trigger"] == "interval"
            assert pm_check_job["minutes"] == 30

    def test_scheduler_registers_pressure_score_job(self, project_manager):
        """Test pressure score job is registered with 1-hour interval."""
        from mnemosyne.aletheia.agents.project_manager_scheduler import (
            ProjectManagerScheduler,
        )

        with patch(
            "mnemosyne.aletheia.agents.project_manager_scheduler.BackgroundScheduler"
        ) as mock_scheduler_class:
            mock_scheduler = MagicMock()
            mock_scheduler_class.return_value = mock_scheduler

            scheduler = ProjectManagerScheduler(project_manager=project_manager)
            scheduler.start()

            # Find the pressure score job
            add_job_calls = mock_scheduler.add_job.call_args_list
            pressure_job = None
            for call_item in add_job_calls:
                kwargs = call_item.kwargs
                if kwargs.get("id") == "pressure_score_updater":
                    pressure_job = kwargs
                    break

            assert pressure_job is not None
            assert pressure_job["trigger"] == "interval"
            assert pressure_job["hours"] == 1


class TestSchedulerLifecycle:
    """Test scheduler start/stop lifecycle."""

    def test_start_starts_scheduler(self, project_manager):
        """Test start() starts the APScheduler."""
        from mnemosyne.aletheia.agents.project_manager_scheduler import (
            ProjectManagerScheduler,
        )

        with patch(
            "mnemosyne.aletheia.agents.project_manager_scheduler.BackgroundScheduler"
        ) as mock_scheduler_class:
            mock_scheduler = MagicMock()
            mock_scheduler_class.return_value = mock_scheduler

            scheduler = ProjectManagerScheduler(project_manager=project_manager)
            scheduler.start()

            # Should start the scheduler
            mock_scheduler.start.assert_called_once()

    def test_stop_shuts_down_scheduler(self, project_manager):
        """Test stop() shuts down the APScheduler."""
        from mnemosyne.aletheia.agents.project_manager_scheduler import (
            ProjectManagerScheduler,
        )

        with patch(
            "mnemosyne.aletheia.agents.project_manager_scheduler.BackgroundScheduler"
        ) as mock_scheduler_class:
            mock_scheduler = MagicMock()
            mock_scheduler_class.return_value = mock_scheduler

            scheduler = ProjectManagerScheduler(project_manager=project_manager)
            scheduler.start()
            scheduler.stop()

            # Should shutdown the scheduler
            mock_scheduler.shutdown.assert_called_once()

    def test_context_manager_starts_and_stops(self, project_manager):
        """Test using scheduler as context manager."""
        from mnemosyne.aletheia.agents.project_manager_scheduler import (
            ProjectManagerScheduler,
        )

        with patch(
            "mnemosyne.aletheia.agents.project_manager_scheduler.BackgroundScheduler"
        ) as mock_scheduler_class:
            mock_scheduler = MagicMock()
            mock_scheduler_class.return_value = mock_scheduler

            with ProjectManagerScheduler(project_manager=project_manager):
                pass

            # Should start and shutdown
            mock_scheduler.start.assert_called_once()
            mock_scheduler.shutdown.assert_called_once()


class TestJobExecution:
    """Test that scheduled jobs execute correctly."""

    def test_pm_check_cycle_job_calls_agent_method(self, project_manager):
        """Test PM check cycle job calls run_pm_check_cycle()."""
        from mnemosyne.aletheia.agents.project_manager_scheduler import (
            ProjectManagerScheduler,
        )

        with patch(
            "mnemosyne.aletheia.agents.project_manager_scheduler.BackgroundScheduler"
        ) as mock_scheduler_class:
            mock_scheduler = MagicMock()
            mock_scheduler_class.return_value = mock_scheduler

            # Spy on project_manager.run_pm_check_cycle
            project_manager.run_pm_check_cycle = Mock()

            scheduler = ProjectManagerScheduler(project_manager=project_manager)
            scheduler.start()

            # Get the registered job function
            add_job_calls = mock_scheduler.add_job.call_args_list
            pm_check_func = None
            for call_item in add_job_calls:
                kwargs = call_item.kwargs
                if kwargs.get("id") == "pm_check_cycle":
                    pm_check_func = kwargs["func"]  # Function is passed as kwarg
                    break

            # Execute the job function
            pm_check_func()

            # Should call agent's run_pm_check_cycle
            project_manager.run_pm_check_cycle.assert_called_once()

    def test_pressure_score_job_calls_update_method(self, project_manager):
        """Test pressure score job calls _update_pressure_scores()."""
        from mnemosyne.aletheia.agents.project_manager_scheduler import (
            ProjectManagerScheduler,
        )

        with patch(
            "mnemosyne.aletheia.agents.project_manager_scheduler.BackgroundScheduler"
        ) as mock_scheduler_class:
            mock_scheduler = MagicMock()
            mock_scheduler_class.return_value = mock_scheduler

            # Spy on project_manager._update_pressure_scores
            project_manager._update_pressure_scores = Mock()

            scheduler = ProjectManagerScheduler(project_manager=project_manager)
            scheduler.start()

            # Get the registered job function
            add_job_calls = mock_scheduler.add_job.call_args_list
            pressure_func = None
            for call_item in add_job_calls:
                kwargs = call_item.kwargs
                if kwargs.get("id") == "pressure_score_updater":
                    pressure_func = kwargs["func"]  # Function is passed as kwarg
                    break

            # Execute the job function
            pressure_func()

            # Should call agent's _update_pressure_scores
            project_manager._update_pressure_scores.assert_called_once()


class TestErrorHandling:
    """Test error handling in scheduled jobs."""

    def test_pm_check_cycle_logs_errors_and_continues(self, project_manager):
        """Test that errors in PM check cycle are logged but don't crash scheduler."""
        from mnemosyne.aletheia.agents.project_manager_scheduler import (
            ProjectManagerScheduler,
        )

        with patch(
            "mnemosyne.aletheia.agents.project_manager_scheduler.BackgroundScheduler"
        ) as mock_scheduler_class:
            mock_scheduler = MagicMock()
            mock_scheduler_class.return_value = mock_scheduler

            # Make run_pm_check_cycle raise an error
            project_manager.run_pm_check_cycle = Mock(side_effect=Exception("Database error"))

            scheduler = ProjectManagerScheduler(project_manager=project_manager)
            scheduler.start()

            # Get the job function
            add_job_calls = mock_scheduler.add_job.call_args_list
            pm_check_func = None
            for call_item in add_job_calls:
                kwargs = call_item.kwargs
                if kwargs.get("id") == "pm_check_cycle":
                    pm_check_func = kwargs["func"]  # Function is passed as kwarg
                    break

            # Should not raise (error is caught and logged)
            try:
                pm_check_func()
            except Exception:
                pytest.fail("Job function should catch and log errors, not raise")


class TestConfigurableIntervals:
    """Test configurable job intervals."""

    def test_custom_pm_check_interval(self, project_manager):
        """Test custom PM check cycle interval."""
        from mnemosyne.aletheia.agents.project_manager_scheduler import (
            ProjectManagerScheduler,
        )

        with patch(
            "mnemosyne.aletheia.agents.project_manager_scheduler.BackgroundScheduler"
        ) as mock_scheduler_class:
            mock_scheduler = MagicMock()
            mock_scheduler_class.return_value = mock_scheduler

            scheduler = ProjectManagerScheduler(
                project_manager=project_manager,
                pm_check_interval_minutes=15,  # Custom interval
            )
            scheduler.start()

            # Find the PM check cycle job
            add_job_calls = mock_scheduler.add_job.call_args_list
            pm_check_job = None
            for call_item in add_job_calls:
                kwargs = call_item.kwargs
                if kwargs.get("id") == "pm_check_cycle":
                    pm_check_job = kwargs
                    break

            assert pm_check_job["minutes"] == 15

    def test_custom_pressure_update_interval(self, project_manager):
        """Test custom pressure score update interval."""
        from mnemosyne.aletheia.agents.project_manager_scheduler import (
            ProjectManagerScheduler,
        )

        with patch(
            "mnemosyne.aletheia.agents.project_manager_scheduler.BackgroundScheduler"
        ) as mock_scheduler_class:
            mock_scheduler = MagicMock()
            mock_scheduler_class.return_value = mock_scheduler

            scheduler = ProjectManagerScheduler(
                project_manager=project_manager,
                pressure_update_interval_hours=2,  # Custom interval
            )
            scheduler.start()

            # Find the pressure score job
            add_job_calls = mock_scheduler.add_job.call_args_list
            pressure_job = None
            for call_item in add_job_calls:
                kwargs = call_item.kwargs
                if kwargs.get("id") == "pressure_score_updater":
                    pressure_job = kwargs
                    break

            assert pressure_job["hours"] == 2
