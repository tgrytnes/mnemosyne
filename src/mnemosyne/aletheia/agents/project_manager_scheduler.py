"""
Project Manager Agent Scheduler (Story 016 - Phase 7)

APScheduler wrapper for running PM check cycles and pressure score updates
on a natural rhythm (30 minutes / 1 hour).
"""

import logging
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)


class ProjectManagerScheduler:
    """
    Scheduler for Project Manager Agent background jobs.

    Runs:
    - PM check cycle every 30 minutes (configurable)
    - Pressure score updates every 1 hour (configurable)
    """

    def __init__(
        self,
        project_manager,
        pm_check_interval_minutes: int = 30,
        pressure_update_interval_hours: int = 1,
    ):
        """
        Initialize Project Manager Scheduler.

        Args:
            project_manager: ProjectManagerAgent instance
            pm_check_interval_minutes: Minutes between PM check cycles (default: 30)
            pressure_update_interval_hours: Hours between pressure score updates (default: 1)
        """
        self.project_manager = project_manager
        self.pm_check_interval_minutes = pm_check_interval_minutes
        self.pressure_update_interval_hours = pressure_update_interval_hours

        self.scheduler: Optional[BackgroundScheduler] = None
        self.is_running = False

    def start(self):
        """Start the scheduler and register jobs."""
        if self.is_running:
            logger.warning("Scheduler already running")
            return

        logger.info("Starting Project Manager Scheduler...")

        self.scheduler = BackgroundScheduler()

        # Register PM check cycle job (every 30 minutes)
        self.scheduler.add_job(
            func=self._run_pm_check_cycle_safe,
            trigger="interval",
            minutes=self.pm_check_interval_minutes,
            id="pm_check_cycle",
            name="PM Check Cycle",
            replace_existing=True,
        )

        logger.info(
            f"Registered PM check cycle job (every {self.pm_check_interval_minutes} minutes)"
        )

        # Register pressure score update job (every 1 hour)
        self.scheduler.add_job(
            func=self._update_pressure_scores_safe,
            trigger="interval",
            hours=self.pressure_update_interval_hours,
            id="pressure_score_updater",
            name="Pressure Score Updater",
            replace_existing=True,
        )

        logger.info(
            f"Registered pressure score update job (every {self.pressure_update_interval_hours} hour)"
        )

        # Start the scheduler
        self.scheduler.start()
        self.is_running = True

        logger.info("Project Manager Scheduler started successfully")

    def stop(self):
        """Stop the scheduler."""
        if not self.is_running:
            logger.warning("Scheduler not running")
            return

        logger.info("Stopping Project Manager Scheduler...")

        if self.scheduler:
            self.scheduler.shutdown(wait=True)

        self.is_running = False
        logger.info("Project Manager Scheduler stopped")

    def __enter__(self):
        """Context manager entry - start scheduler."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - stop scheduler."""
        self.stop()
        return False

    # ==========================================================================
    # Safe Job Wrappers (Error Handling)
    # ==========================================================================

    def _run_pm_check_cycle_safe(self):
        """
        Safe wrapper for PM check cycle job.

        Catches and logs errors to prevent scheduler crashes.
        """
        try:
            logger.debug("Running PM check cycle...")
            self.project_manager.run_pm_check_cycle()
            logger.debug("PM check cycle completed")
        except Exception as e:
            logger.error(f"Error in PM check cycle: {e}", exc_info=True)

    def _update_pressure_scores_safe(self):
        """
        Safe wrapper for pressure score update job.

        Catches and logs errors to prevent scheduler crashes.
        """
        try:
            logger.debug("Updating pressure scores...")
            self.project_manager._update_pressure_scores()
            logger.debug("Pressure score update completed")
        except Exception as e:
            logger.error(f"Error updating pressure scores: {e}", exc_info=True)
