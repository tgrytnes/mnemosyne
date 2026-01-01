# Story 016: Project Manager Agent (Strategist)

**As a** user
**I want** an agent that actively manages projects in The Ananke
**So that** projects don't stall, deadlines are tracked, and I'm nudged to take action

**Status**: On hold (planned after Stories 010/014/015/027)

## Acceptance Criteria
- [ ] Background agent runs daily (scheduled job)
- [ ] Checks all projects in `candidate` and `active` status
- [ ] Ensures every active project has a deadline
- [ ] Calculates pressure scores (Work ÷ Time remaining)
- [ ] Identifies stalled projects (no updates in 7+ days)
- [ ] Sends daily/weekly project digest via Telegram
- [ ] Nudges user when deadlines approach (<3 days)
- [ ] Requests user input for missing deadlines
- [ ] Allows status updates via Telegram commands
- [ ] Generates project health reports
- [ ] Project views include `discovery_id` when available (traceability)
- [ ] Project status transitions follow explicit rules and update timestamps

## 🎯 Architectural Role

**This story implements The Project Manager, a core component of Hermes (Interaction Layer).**

Also known as "Strategist", The Project Manager ensures projects in The Ananke don't become "write and forget." While it has scheduled triggers (daily 8 AM), it's architecturally part of Hermes because it manages the dialogue between you and project state.

Inspired by project_crystal's Strategist concept:
> **Strategist**: Calculate pressure scores (Work ÷ Time) to prioritize action.

The Project Manager transforms The Ananke from a static database into an **active project management system** that:
1. Watches for stalls
2. Enforces deadline hygiene
3. Calculates urgency (pressure scores)
4. Nudges user to take action via The Liaison

**Philosophy (from Crystal)**: "Accept the Drift" - Obsidian and SQL will never match perfectly. The Project Manager surfaces the gaps and asks for reconciliation.

## Technical Notes

### Project Manager Agent Class

```python
class ProjectManagerAgent:
    """
    Active project management for The Ananke
    Based on project_crystal Strategist concept
    """
    def __init__(self, db_conn, messenger):
        self.db = db_conn
        self.messenger = messenger  # Hermes

    def run_daily_management(self):
        """
        Daily project management routine
        """
        # 1. Check for missing deadlines
        self._check_missing_deadlines()

        # 2. Calculate pressure scores
        self._update_pressure_scores()

        # 3. Identify stalled projects
        self._check_stalled_projects()

        # 4. Check approaching deadlines
        self._check_approaching_deadlines()

        # 5. Send daily digest
        self._send_daily_digest()

    def _check_missing_deadlines(self):
        """
        Active projects should have deadlines
        """
        cursor = self.db.cursor()

        cursor.execute("""
            SELECT id, title, created_at
            FROM projects
            WHERE status = 'active'
              AND deadline IS NULL
        """)

        projects_without_deadlines = cursor.fetchall()

        for project_id, title, created_at in projects_without_deadlines:
            # Request deadline from user
            self._request_deadline(project_id, title, created_at)

    def _request_deadline(self, project_id: int, title: str, created_at: datetime):
        """
        Ask user to set a deadline
        """
        age_days = (datetime.now() - created_at).days

        message = f"""
⚠️ **Project Needs Deadline**

**Project**: {title}
**Status**: Active (no deadline set)
**Created**: {format_time_ago(created_at)} ({age_days} days ago)

**Action required**: Set a deadline to track this project.

Quick options:
`/set_deadline {project_id} 7d` - Due in 7 days
`/set_deadline {project_id} 2w` - Due in 2 weeks
`/set_deadline {project_id} 1m` - Due in 1 month
`/set_deadline {project_id} 2024-12-31` - Specific date

Or mark as:
`/pause_project {project_id}` - Not urgent right now
"""

        self.messenger.send_message(message)

    def _update_pressure_scores(self):
        """
        Calculate pressure = Work ÷ Time for all active projects
        Based on Crystal's Strategist algorithm
        """
        cursor = self.db.cursor()

        cursor.execute("""
            SELECT id, title, deadline, work_estimate
            FROM projects
            WHERE status = 'active'
              AND deadline IS NOT NULL
        """)

        for project_id, title, deadline, work_estimate in cursor.fetchall():
            # Calculate pressure score
            pressure = self._calculate_pressure(deadline, work_estimate)

            # Update in database
            cursor.execute("""
                UPDATE projects
                SET pressure_score = %s,
                    updated_at = %s
                WHERE id = %s
            """, (pressure, datetime.now(), project_id))

        self.db.commit()

    def _calculate_pressure(self, deadline: datetime, work_estimate: int = None) -> float:
        """
        Pressure = Work ÷ Time

        If no work estimate, use default heuristic:
        - Simple project: 5 hours
        - Medium project: 20 hours
        - Complex project: 50 hours
        """
        if not work_estimate:
            work_estimate = 20  # Default: medium project

        time_remaining_hours = (deadline - datetime.now()).total_seconds() / 3600

        if time_remaining_hours <= 0:
            return 999.0  # Overdue!

        pressure = work_estimate / time_remaining_hours

        return round(pressure, 2)

    def _check_stalled_projects(self):
        """
        Identify projects with no updates in 7+ days
        """
        cursor = self.db.cursor()

        cursor.execute("""
            SELECT id, title, status, updated_at
            FROM projects
            WHERE status IN ('candidate', 'active')
              AND updated_at < NOW() - INTERVAL '7 days'
        """)

        stalled = cursor.fetchall()

        if stalled:
            self._send_stall_alert(stalled)

    def _send_stall_alert(self, stalled_projects: List[Tuple]):
        """
        Notify user about stalled projects
        """
        message = f"""
🚨 **Stalled Projects Alert**

{len(stalled_projects)} project(s) have no updates in 7+ days:

"""

        for project_id, title, status, updated_at in stalled_projects:
            days_stalled = (datetime.now() - updated_at).days

            message += f"""
• **{title}**
  Status: {status}
  Last update: {days_stalled} days ago
  `/view_project {project_id}` | `/update_project {project_id}`

"""

        message += """
**Actions**:
• Update progress to unstall
• Pause if not urgent
• Complete if done
• Cancel if no longer relevant
"""

        self.messenger.send_message(message)

    def _check_approaching_deadlines(self):
        """
        Nudge user for deadlines within 3 days
        """
        cursor = self.db.cursor()

        cursor.execute("""
            SELECT id, title, deadline, pressure_score
            FROM projects
            WHERE status = 'active'
              AND deadline IS NOT NULL
              AND deadline BETWEEN NOW() AND NOW() + INTERVAL '3 days'
        """)

        approaching = cursor.fetchall()

        for project_id, title, deadline, pressure in approaching:
            self._send_deadline_reminder(project_id, title, deadline, pressure)

    def _send_deadline_reminder(self, project_id: int, title: str, deadline: datetime, pressure: float):
        """
        Urgent reminder for approaching deadline
        """
        time_left = deadline - datetime.now()
        days_left = time_left.days
        hours_left = time_left.seconds // 3600

        urgency_emoji = "🔥" if days_left < 1 else "⏰"

        message = f"""
{urgency_emoji} **Deadline Approaching**

**Project**: {title}
**Deadline**: {format_datetime(deadline)}
**Time left**: {days_left}d {hours_left}h
**Pressure**: {pressure:.2f}

**Quick actions**:
`/complete_project {project_id}` - Mark as done
`/extend_deadline {project_id} 3d` - Extend by 3 days
`/view_project {project_id}` - View details
"""

        self.messenger.send_message(message)

    def _send_daily_digest(self):
        """
        Daily project status summary
        """
        cursor = self.db.cursor()

        # Count by status
        cursor.execute("""
            SELECT status, COUNT(*)
            FROM projects
            GROUP BY status
        """)

        status_counts = dict(cursor.fetchall())

        # Top 3 high-pressure projects
        cursor.execute("""
            SELECT title, deadline, pressure_score
            FROM projects
            WHERE status = 'active'
              AND pressure_score IS NOT NULL
            ORDER BY pressure_score DESC
            LIMIT 3
        """)

        high_pressure = cursor.fetchall()

        message = f"""
📋 **Daily Project Digest**
{datetime.now().strftime('%B %d, %Y')}

**Status**:
• Active: {status_counts.get('active', 0)}
• Candidate: {status_counts.get('candidate', 0)}
• Paused: {status_counts.get('paused', 0)}
• Completed: {status_counts.get('completed', 0)}

**High Pressure** (top 3):
"""

        for title, deadline, pressure in high_pressure:
            time_left = deadline - datetime.now()
            message += f"• {title} ({time_left.days}d left, pressure: {pressure:.1f})\n"

        message += """
Use `/projects` to see all projects.
"""

        self.messenger.send_message(message)
```

### Project State Transitions

Statuses: `candidate`, `active`, `paused`, `completed`

Transitions:
- `candidate` → `active` on user approval/activation
- `candidate` → `paused` when user defers
- `active` → `paused` when user pauses
- `paused` → `active` when user resumes
- `active` → `completed` when user marks complete
- `paused` → `completed` only via explicit user action

All transitions update `updated_at` and are logged for audit.

### Telegram Commands (Project Management)

```python
# In Hermes bot

@hermes_bot.command("projects")
def cmd_projects(message, status: str = "active"):
    """
    List projects by status
    Usage: /projects [active|candidate|paused|completed|all]
    """
    cursor = db.cursor()

    if status == "all":
        cursor.execute("SELECT * FROM projects ORDER BY pressure_score DESC NULLS LAST")
    else:
        cursor.execute(
            "SELECT * FROM projects WHERE status = %s ORDER BY pressure_score DESC NULLS LAST",
            (status,)
        )

    projects = cursor.fetchall()

    if not projects:
        return f"No {status} projects found."

    response = f"📋 **{status.title()} Projects**\n\n"

    for p in projects:
        deadline_str = format_date(p.deadline) if p.deadline else "No deadline"
        pressure_str = f"Pressure: {p.pressure_score:.1f}" if p.pressure_score else ""

        response += f"""
**{p.title}**
Status: {p.status} | {deadline_str} | {pressure_str}
`/view_project {p.id}`

"""

    bot.send_message(
        chat_id=message.chat.id,
        text=response,
        parse_mode='Markdown'
    )

@hermes_bot.command("set_deadline")
def cmd_set_deadline(message, project_id: int, deadline: str):
    """
    Set project deadline
    Usage: /set_deadline 123 7d OR /set_deadline 123 2024-12-31
    """
    # Parse deadline
    deadline_dt = parse_deadline(deadline)

    cursor = db.cursor()

    cursor.execute("""
        UPDATE projects
        SET deadline = %s, updated_at = %s
        WHERE id = %s
    """, (deadline_dt, datetime.now(), project_id))

    db.commit()

    # Recalculate pressure
    project_manager.update_pressure_score(project_id)

    bot.send_message(
        chat_id=message.chat.id,
        text=f"✅ Deadline set to {format_date(deadline_dt)}"
    )

@hermes_bot.command("complete_project")
def cmd_complete_project(message, project_id: int):
    """
    Mark project as completed
    """
    cursor = db.cursor()

    cursor.execute("""
        UPDATE projects
        SET status = 'completed',
            completed_at = %s,
            updated_at = %s
        WHERE id = %s
    """, (datetime.now(), datetime.now(), project_id))

    db.commit()

    bot.send_message(
        chat_id=message.chat.id,
        text="🎉 Project marked as completed!"
    )

@hermes_bot.command("pause_project")
def cmd_pause_project(message, project_id: int):
    """
    Pause project (not urgent right now)
    """
    cursor = db.cursor()

    cursor.execute("""
        UPDATE projects
        SET status = 'paused', updated_at = %s
        WHERE id = %s
    """, (datetime.now(), project_id))

    db.commit()

    bot.send_message(
        chat_id=message.chat.id,
        text="⏸️ Project paused. Use `/activate_project {project_id}` to resume."
    )

@hermes_bot.command("extend_deadline")
def cmd_extend_deadline(message, project_id: int, extension: str):
    """
    Extend deadline
    Usage: /extend_deadline 123 3d
    """
    project = get_project(project_id)

    if not project.deadline:
        return "Project has no deadline to extend."

    # Parse extension
    extension_delta = parse_duration(extension)
    new_deadline = project.deadline + extension_delta

    cursor = db.cursor()

    cursor.execute("""
        UPDATE projects
        SET deadline = %s, updated_at = %s
        WHERE id = %s
    """, (new_deadline, datetime.now(), project_id))

    db.commit()

    bot.send_message(
        chat_id=message.chat.id,
        text=f"✅ Deadline extended to {format_date(new_deadline)}"
    )

@hermes_bot.command("update_project")
def cmd_update_project(message, project_id: int):
    """
    Update project (marks as recently touched to unstall)
    """
    cursor = db.cursor()

    cursor.execute("""
        UPDATE projects
        SET updated_at = %s
        WHERE id = %s
    """, (datetime.now(), project_id))

    db.commit()

    bot.send_message(
        chat_id=message.chat.id,
        text="✅ Project updated. Add a note about your progress with:\n"
             f"`/note_project {project_id} [your note here]`"
    )

@hermes_bot.command("view_project")
def cmd_view_project(message, project_id: int):
    """
    View full project details
    """
    project = get_project(project_id)

    if not project:
        return "Project not found."

    # Get linked discovery
    discovery = get_discovery(project.discovery_id) if project.discovery_id else None

    detail_message = f"""
📊 **Project Details**

**Title**: {project.title}
**Description**: {project.description or 'No description'}

**Status**: {project.status}
**Deadline**: {format_date(project.deadline) if project.deadline else 'Not set'}
**Pressure**: {project.pressure_score:.1f} if project.pressure_score else 'N/A'}

**Discovered by**: {project.discovered_by}
**Discovery ID**: {project.discovery_id or 'N/A'}
**Created**: {format_datetime(project.created_at)}
**Last updated**: {format_time_ago(project.updated_at)}

**Confidence**: {project.confidence_score:.0%} if project.confidence_score else 'N/A'}
"""

    if discovery:
        detail_message += f"""
**Source Discovery**:
• {len(discovery.cluster_ids)} clusters analyzed
• {format_datetime(discovery.detected_at)}
"""

    detail_message += f"""
**Actions**:
`/set_deadline {project_id} [date]`
`/complete_project {project_id}`
`/pause_project {project_id}`
"""

    bot.send_message(
        chat_id=message.chat.id,
        text=detail_message,
        parse_mode='Markdown'
    )
```

### Scheduled Job Integration

```python
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()

# Daily management routine (8 AM)
scheduler.add_job(
    project_manager.run_daily_management,
    'cron',
    hour=8,
    minute=0
)

# Weekly summary (Sunday 9 AM)
scheduler.add_job(
    project_manager.send_weekly_summary,
    'cron',
    day_of_week='sun',
    hour=9,
    minute=0
)

scheduler.start()
```

### Weekly Summary

```python
def send_weekly_summary(self):
    """
    Comprehensive weekly project report
    """
    cursor = self.db.cursor()

    # Projects completed this week
    cursor.execute("""
        SELECT title FROM projects
        WHERE completed_at >= NOW() - INTERVAL '7 days'
    """)

    completed = cursor.fetchall()

    # New projects this week
    cursor.execute("""
        SELECT title FROM projects
        WHERE created_at >= NOW() - INTERVAL '7 days'
    """)

    new_projects = cursor.fetchall()

    # Overdue projects
    cursor.execute("""
        SELECT title, deadline FROM projects
        WHERE status = 'active'
          AND deadline < NOW()
    """)

    overdue = cursor.fetchall()

    message = f"""
📊 **Weekly Project Summary**
Week of {get_week_start().strftime('%B %d, %Y')}

**Completed** ({len(completed)}):
{format_project_list(completed)}

**New Projects** ({len(new_projects)}):
{format_project_list(new_projects)}

**Overdue** ({len(overdue)}):
{format_overdue_list(overdue)}

**Next Week Focus**:
{get_upcoming_deadlines()}

Keep up the momentum! 🚀
"""

    self.messenger.send_message(message)
```

### Dependencies
- The Ananke (PostgreSQL projects table)
- Hermes (Telegram bot)
- project_crystal Strategist concept (pressure scores)

## Affected Components
- **Argus**: Project Manager agent (Strategist)
- **Alexandria**: The Ananke (PostgreSQL)
- **Hermes**: Project management Telegram commands

## Priority
**High** - Turns static SQL into active project management

## Estimate
8 story points (5-8 days)

## Linear Labels
`phase-4`, `project-management`, `strategist`, `argus`, `hermes`, `alexandria`

## Related Stories
- Story 014: SQL Project Gatekeeper (creates projects)
- Story 015: Monitor Agent (ensures discoveries become projects)
- project_crystal Strategist concept

## Future Enhancements
- Work estimates: Ask user to estimate hours for pressure calculation
- Progress tracking: % complete updates
- Sub-tasks: Break projects into actionable steps
- Calendar integration: Sync deadlines to Google Calendar
- Team mode: Assign projects to team members
- Burndown charts: Visualize project progress over time
