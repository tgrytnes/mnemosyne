"""
Project Manager Agent (Story 016)

Incrementally enriches projects discovered by Latent Scout with metadata
(importance, urgency, deadline) through natural conversation with the user.
"""

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from dateutil import parser as date_parser

logger = logging.getLogger(__name__)


class ProjectManagerAgent:
    """
    Project Manager Agent for incremental project enrichment.

    Asks natural questions to gather metadata (importance, urgency, deadline)
    and maintains gentle, non-pushy rhythm of follow-ups.
    """

    def __init__(
        self,
        db_conn,
        message_outbox,
        gatekeeper=None,
        max_messages_per_hour: int = 10,
    ):
        """
        Initialize Project Manager Agent.

        Args:
            db_conn: PostgreSQL database connection
            message_outbox: Message Outbox for sending questions
            gatekeeper: SQL Gatekeeper for direct updates (optional)
            max_messages_per_hour: Throttle limit for messages
        """
        self.db_conn = db_conn
        self.message_outbox = message_outbox
        self.gatekeeper = gatekeeper
        self.max_messages_per_hour = max_messages_per_hour

    # ==========================================================================
    # Enrichment Queue Building
    # ==========================================================================

    def _build_enrichment_queue(self) -> list[dict[str, Any]]:
        """
        Build prioritized queue of projects needing enrichment.

        Stages:
        1. Request importance for projects missing it
        2. Request urgency for projects with importance but no urgency
        3. Focus on high-priority projects (importance+urgency >= 7)
        4. Request deadline for high-priority active projects
        5. Enrich description if Scout-generated is too vague

        Returns:
            List of queue items with {id, stage, priority}
        """
        queue = []

        with self.db_conn.cursor() as cursor:
            # Get all projects that need enrichment
            cursor.execute(
                """
                SELECT
                    id, title, status, importance, urgency, deadline,
                    work_estimate, created_at
                FROM projects
                WHERE status IN ('candidate', 'active')
                ORDER BY created_at DESC
            """
            )
            projects = cursor.fetchall()

        for row in projects:
            # Handle both dict and tuple rows
            if isinstance(row, dict):
                project_id = row["id"]
                importance = row["importance"]
                urgency = row["urgency"]
                deadline = row["deadline"]
            else:
                project_id = row[0]
                importance = row[3]
                urgency = row[4]
                deadline = row[5]

            # Stage 1: Request importance (highest priority)
            if importance is None:
                queue.append(
                    {
                        "id": project_id,
                        "stage": "importance",
                        "priority": 1,  # Highest priority
                    }
                )
                continue

            # Stage 2: Request urgency
            if urgency is None:
                queue.append(
                    {
                        "id": project_id,
                        "stage": "urgency",
                        "priority": 2,
                    }
                )
                continue

            # Stage 3: Focus on high-priority projects
            if importance + urgency >= 7:
                # Stage 4: Request deadline for high-priority projects
                if deadline is None:
                    queue.append(
                        {
                            "id": project_id,
                            "stage": "deadline",
                            "priority": 3,
                        }
                    )

        # Sort by priority (lowest number = highest priority)
        queue.sort(key=lambda x: x["priority"])

        return queue

    # ==========================================================================
    # Question Handlers
    # ==========================================================================

    def _request_importance(self, project: dict[str, Any]) -> None:
        """
        Request importance rating for a project.

        Args:
            project: Project dictionary with id, title, description
        """
        message_content = f"""📊 **New Project Discovered: {project['title']}**

How important is this project to you? (Rate importance from 1-5)

• 1 = Nice to have
• 3 = Moderately important
• 5 = Critical/High impact

Reply with a number 1-5."""

        self.message_outbox.enqueue(
            content=message_content,
            sender="project_manager",
            expects_response=True,
            metadata={
                "project_id": project["id"],
                "question_type": "importance",
            },
        )

        logger.info(f"Requested importance for project {project['id']}")

    def _request_urgency(self, project: dict[str, Any]) -> None:
        """
        Request urgency rating for a project.

        Args:
            project: Project dictionary with id, title, importance
        """
        message_content = f"""⏰ **Project: {project['title']}**

How urgent is this project? (Rate urgency from 1-5)

• 1 = Can wait months
• 3 = Should do in weeks
• 5 = Needs attention ASAP

Reply with a number 1-5."""

        self.message_outbox.enqueue(
            content=message_content,
            sender="project_manager",
            expects_response=True,
            metadata={
                "project_id": project["id"],
                "question_type": "urgency",
            },
        )

        logger.info(f"Requested urgency for project {project['id']}")

    def _request_deadline(self, project: dict[str, Any]) -> None:
        """
        Request deadline for a high-priority project.

        Args:
            project: Project dictionary with id, title, importance, urgency
        """
        message_content = f"""📅 **High Priority Project: {project['title']}**

This project has high importance ({project['importance']}) and urgency ({project['urgency']}).

Do you have a target deadline?

Reply with:
• A date (e.g., "2026-03-15" or "March 15")
• A duration (e.g., "2 weeks" or "1 month")
• "no deadline" if flexible"""

        self.message_outbox.enqueue(
            content=message_content,
            sender="project_manager",
            expects_response=True,
            metadata={
                "project_id": project["id"],
                "question_type": "deadline",
            },
        )

        logger.info(f"Requested deadline for project {project['id']}")

    def _request_description(self, project: dict[str, Any]) -> None:
        """
        Request richer description for a project with vague details.

        Args:
            project: Project dictionary with id, title, description
        """
        message_content = f"""📝 **Project: {project['title']}**

Can you describe this project in more detail?

What specifically needs to be done?

Reply with a brief description."""

        self.message_outbox.enqueue(
            content=message_content,
            sender="project_manager",
            expects_response=True,
            metadata={
                "project_id": project["id"],
                "question_type": "description",
            },
        )

        logger.info(f"Requested description for project {project['id']}")

    # ==========================================================================
    # User Response Handlers (Story 016 - Phase 6)
    # ==========================================================================

    def handle_importance_response(self, project_id: int, value: int) -> None:
        """
        Handle user response to importance question.

        Args:
            project_id: ID of the project
            value: Importance rating (1-5)
        """
        # Validate input
        if not (1 <= value <= 5):
            raise ValueError("Importance must be between 1 and 5")

        # Update via gatekeeper (user-initiated)
        if self.gatekeeper:
            self.gatekeeper.update_project_direct(
                project_id,
                {"importance": value},
                user_initiated=True,
            )

        logger.info(f"Updated importance for project {project_id}: {value}")

        # Continue enrichment (ask next question)
        self.continue_enrichment(project_id)

    def handle_urgency_response(self, project_id: int, value: int) -> None:
        """
        Handle user response to urgency question.

        Args:
            project_id: ID of the project
            value: Urgency rating (1-5)
        """
        # Validate input
        if not (1 <= value <= 5):
            raise ValueError("Urgency must be between 1 and 5")

        # Update via gatekeeper (user-initiated)
        if self.gatekeeper:
            self.gatekeeper.update_project_direct(
                project_id,
                {"urgency": value},
                user_initiated=True,
            )

        logger.info(f"Updated urgency for project {project_id}: {value}")

        # Continue enrichment (ask next question)
        self.continue_enrichment(project_id)

    def handle_deadline_response(self, project_id: int, deadline_text: str) -> None:
        """
        Handle user response to deadline question.

        Args:
            project_id: ID of the project
            deadline_text: Deadline as text (ISO date, natural date, or duration)
        """
        # Parse deadline
        deadline = self._parse_deadline(deadline_text)

        # Update via gatekeeper (user-initiated)
        if self.gatekeeper:
            self.gatekeeper.update_project_direct(
                project_id,
                {"deadline": deadline},
                user_initiated=True,
            )

        logger.info(f"Updated deadline for project {project_id}: {deadline}")

        # Continue enrichment (ask next question if needed)
        self.continue_enrichment(project_id)

    def handle_description_response(self, project_id: int, description: str) -> None:
        """
        Handle user response to description question.

        Args:
            project_id: ID of the project
            description: Richer project description
        """
        # Update via gatekeeper (user-initiated)
        if self.gatekeeper:
            self.gatekeeper.update_project_direct(
                project_id,
                {"description": description},
                user_initiated=True,
            )

        logger.info(f"Updated description for project {project_id}")

    def _parse_deadline(self, deadline_text: str) -> datetime | None:
        """
        Parse deadline text into datetime.

        Supports:
        - ISO format: "2026-03-15"
        - Natural dates: "March 15", "Jan 20"
        - Relative durations: "2 weeks", "1 month"
        - No deadline: "no deadline", "flexible"

        Args:
            deadline_text: Deadline as text

        Returns:
            Parsed datetime or None if no deadline

        Raises:
            ValueError: If deadline text cannot be parsed
        """
        text = deadline_text.strip().lower()

        # Check for "no deadline"
        if text in ("no deadline", "flexible", "none"):
            return None

        # Try parsing relative duration FIRST (before dateutil)
        # Pattern: "2 weeks", "1 month", "3 days"
        duration_match = re.match(r"(\d+)\s*(day|week|month)s?", text)
        if duration_match:
            amount = int(duration_match.group(1))
            unit = duration_match.group(2)

            now = datetime.now(UTC)

            if unit == "day":
                return now + timedelta(days=amount)
            elif unit == "week":
                return now + timedelta(weeks=amount)
            elif unit == "month":
                # Approximate month as 30 days
                return now + timedelta(days=amount * 30)

        # Try parsing as ISO date or natural date
        try:
            parsed = date_parser.parse(text, fuzzy=True)
            # Ensure timezone-aware
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed
        except (ValueError, date_parser.ParserError):
            pass

        # Could not parse
        raise ValueError(f"Could not parse deadline: '{deadline_text}'")

    # ==========================================================================
    # Event-Driven Response Handler
    # ==========================================================================

    def continue_enrichment(self, project_id: int) -> None:
        """
        Continue enrichment after user responds to a question.

        Determines the next missing field and asks the appropriate question.

        Args:
            project_id: ID of the project to continue enriching
        """
        # Fetch current project state
        with self.db_conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id, title, discovered_by, discovery_id, status,
                    importance, urgency, deadline, work_estimate, pressure_score,
                    created_at, updated_at
                FROM projects
                WHERE id = %s
            """,
                (project_id,),
            )
            row = cursor.fetchone()

        if not row:
            logger.warning(f"Project {project_id} not found")
            return

        # Convert row to dict
        project = {
            "id": row[0],
            "title": row[1],
            "importance": row[5],
            "urgency": row[6],
            "deadline": row[7],
        }

        # Determine next question
        if project["importance"] is None:
            self._request_importance(project)
        elif project["urgency"] is None:
            self._request_urgency(project)
        elif project["importance"] + project["urgency"] >= 7 and project["deadline"] is None:
            self._request_deadline(project)
        else:
            # Fully enriched for now
            logger.info(f"Project {project_id} fully enriched")

    # ==========================================================================
    # PM Check Cycle
    # ==========================================================================

    def run_pm_check_cycle(self) -> None:
        """
        Main PM check cycle (runs every 30 minutes).

        Checks for:
        - New projects needing initial metadata
        - Critical deadlines approaching
        - Unanswered questions needing follow-up
        - Opportunistic nudges (if not too many messages sent)
        """
        # Check throttling
        messages_sent = self._messages_sent_last_hour()
        if messages_sent >= self.max_messages_per_hour:
            logger.info(
                f"Throttled: {messages_sent}/{self.max_messages_per_hour} "
                "messages sent in last hour"
            )
            return

        # Build enrichment queue
        queue = self._build_enrichment_queue()

        if not queue:
            logger.info("No projects need enrichment")
            return

        # Process first item in queue (don't spam user with many questions)
        item = queue[0]
        project_id = item["id"]
        stage = item["stage"]

        # Fetch project details
        with self.db_conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, title, importance, urgency, description
                FROM projects
                WHERE id = %s
            """,
                (project_id,),
            )
            row = cursor.fetchone()

        if not row:
            return

        project = {
            "id": row[0],
            "title": row[1],
            "importance": row[2],
            "urgency": row[3],
            "description": row[4],
        }

        # Ask appropriate question based on stage
        if stage == "importance":
            self._request_importance(project)
        elif stage == "urgency":
            self._request_urgency(project)
        elif stage == "deadline":
            self._request_deadline(project)

    def _messages_sent_last_hour(self) -> int:
        """
        Count messages sent by Project Manager in the last hour.

        Returns:
            Number of messages sent
        """
        import sqlite3

        one_hour_ago = datetime.now(UTC) - timedelta(hours=1)

        # Query the SQLite message outbox (not PostgreSQL)
        # Use the existing MessageOutbox connection
        cursor = self.message_outbox.db.cursor()

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM message_outbox
            WHERE created_at > ?
            """,
            (one_hour_ago.isoformat(),),
        )
        row = cursor.fetchone()
        count = row[0] if row else 0

        cursor.close()
        return count

    def _get_critical_deadlines(self) -> list[tuple]:
        """
        Get projects with deadlines < 24 hours.

        Returns:
            List of (id, title, deadline, importance, urgency) tuples
        """
        now = datetime.now(UTC)
        critical_threshold = now + timedelta(hours=24)

        with self.db_conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, title, deadline, importance, urgency
                FROM projects
                WHERE deadline IS NOT NULL
                AND deadline < %s
                AND deadline > %s
                AND status = 'active'
                ORDER BY deadline ASC
            """,
                (critical_threshold, now),
            )
            return cursor.fetchall()

    def _handle_critical_deadline(self, project: dict[str, Any]) -> None:
        """
        Send urgent reminder for critical deadline.

        Args:
            project: Project dictionary with deadline info
        """
        hours_remaining = (project["deadline"] - datetime.now(UTC)).total_seconds() / 3600

        message_content = f"""🚨 **Urgent: {project['title']}**

Deadline is in {hours_remaining:.1f} hours!

This is a high-priority project (importance: {project['importance']}, urgency: {
            project['urgency']
        }).

Just a heads up! 👍"""

        self.message_outbox.enqueue(
            content=message_content,
            sender="project_manager",
            expects_response=False,
            metadata={
                "project_id": project["id"],
                "message_type": "critical_deadline_reminder",
            },
        )

        logger.info(f"Sent critical deadline reminder for project {project['id']}")

    # ==========================================================================
    # Pressure Score Calculation
    # ==========================================================================

    def _update_pressure_scores(self) -> None:
        """
        Update pressure scores for all active projects.

        Pressure = (work_estimate / time_remaining) × priority_factor
        Where priority_factor = importance × urgency

        Overdue projects get maximum pressure (999.0).
        """
        now = datetime.now(UTC)

        with self.db_conn.cursor() as cursor:
            # Get projects with deadlines and work estimates
            cursor.execute(
                """
                SELECT id, work_estimate, deadline, importance, urgency
                FROM projects
                WHERE deadline IS NOT NULL
                AND work_estimate IS NOT NULL
                AND status = 'active'
            """
            )
            projects = cursor.fetchall()

        for row in projects:
            project_id, work_estimate, deadline, importance, urgency = row

            # Skip if missing priority data or deadline
            if importance is None or urgency is None or deadline is None:
                continue

            # Check if overdue
            if deadline < now:
                pressure_score = 999.0  # Maximum pressure
            else:
                # Calculate time remaining in hours
                time_remaining = (deadline - now).total_seconds() / 3600

                if time_remaining <= 0:
                    pressure_score = 999.0
                else:
                    # Time pressure = work / time
                    time_pressure = work_estimate / time_remaining

                    # Priority factor = importance × urgency
                    priority_factor = importance * urgency

                    # Combined pressure score
                    pressure_score = time_pressure * priority_factor

            # Update via gatekeeper if available
            if self.gatekeeper:
                self.gatekeeper.update_project_direct(
                    project_id,
                    {"pressure_score": pressure_score},
                    user_initiated=False,  # System-generated
                )
                logger.debug(
                    f"Updated pressure score for project {project_id}: {pressure_score:.2f}"
                )

    # ==========================================================================
    # Reminder Handlers
    # ==========================================================================

    def _send_gentle_reminder(self, project: dict[str, Any], question_type: str) -> None:
        """
        Send gentle, friendly reminder for unanswered question.

        Args:
            project: Project dictionary
            question_type: Type of question (importance, urgency, deadline)
        """
        message_content = f"""👋 Hey! Just a gentle reminder about **{project['title']}**

No pressure, but when you have a moment, could you share the {
            question_type
        } for this project?

Thanks! 😊"""

        self.message_outbox.enqueue(
            content=message_content,
            sender="project_manager",
            expects_response=True,
            metadata={
                "project_id": project["id"],
                "question_type": question_type,
                "reminder_type": "gentle",
            },
        )

        logger.info(f"Sent gentle reminder for project {project['id']}")

    def _send_escalated_reminder(self, project: dict[str, Any], question_type: str) -> None:
        """
        Send escalated reminder for high-priority items.

        Args:
            project: Project dictionary with importance/urgency
            question_type: Type of question
        """
        message_content = f"""⚡ **Important: {project['title']}**

This is a high-priority project (importance: {project['importance']}, urgency: {
            project['urgency']
        }).

Could you help me understand the {question_type} for this project?
It would really help with planning!

Thanks for your time! 🙏"""

        self.message_outbox.enqueue(
            content=message_content,
            sender="project_manager",
            expects_response=True,
            metadata={
                "project_id": project["id"],
                "question_type": question_type,
                "reminder_type": "escalated",
            },
        )

        logger.info(f"Sent escalated reminder for project {project['id']}")

    def _mark_as_avoiding(self, project_id: int) -> None:
        """
        Mark project as user-avoiding after many unanswered questions.

        Args:
            project_id: Project ID
        """
        logger.info(f"User appears to be avoiding project {project_id}")

        if self.gatekeeper:
            # Mark in metadata or adjust status
            # For now, we could lower the importance or pause the project
            self.gatekeeper.update_project_direct(
                project_id,
                {"status": "paused"},  # Or add metadata field
                user_initiated=False,
            )

    def _should_stop_asking(self, project: dict[str, Any]) -> bool:
        """
        Determine if we should stop asking questions for a project.

        Stop asking if:
        - Low priority (importance + urgency < 5)
        - Multiple unanswered questions (>= 4)

        Args:
            project: Project dictionary

        Returns:
            True if should stop asking
        """
        importance = project.get("importance", 1)
        urgency = project.get("urgency", 1)
        unanswered = project.get("unanswered_questions", 0)

        # Low priority and many unanswered questions
        if importance + urgency < 5 and unanswered >= 4:
            return True

        return False
