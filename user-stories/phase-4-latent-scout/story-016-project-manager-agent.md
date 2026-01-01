# Story 016: Project Manager Agent (Strategist)

**As a** user
**I want** an agent that actively manages projects through incremental enrichment and bidirectional Obsidian sync
**So that** projects don't stall, I'm nudged intelligently based on priority, and I can work seamlessly in either SQL or Obsidian

**Status**: On hold (planned after Stories 010/014/015/027)

## Acceptance Criteria

### Core Agent Behavior
- [ ] Background agent runs check cycle every 30 minutes (scheduled job)
- [ ] Checks all projects in `candidate` and `active` status
- [ ] Uses incremental enrichment strategy (accepts title/description from Gatekeeper, builds up user metadata step-by-step)
- [ ] Prioritizes communication based on importance/urgency (natural PM rhythm, no fixed quotas)
- [ ] Only requests ONE piece of missing information per project per interaction
- [ ] Calculates pressure scores hourly for projects with deadlines
- [ ] Syncs changed projects to Obsidian every 15 minutes

### Incremental Metadata Enrichment
- [ ] Stage 1: Accepts new projects from Gatekeeper with: `title, description, discovered_by, discovery_id, cluster_ids, confidence_score, status='candidate'`
- [ ] Stage 2: Requests `importance` (1-5 scale) for projects lacking it (user-only metadata, never from Scout)
- [ ] Stage 3: Requests `urgency` (1-5 scale) for projects lacking it (user-only metadata, never from Scout)
- [ ] Stage 4: Focuses on high-priority projects (importance+urgency >= 7) for further enrichment
- [ ] Stage 5: Requests `deadline` for high-priority active projects (user-only metadata, never from Scout)
- [ ] Stage 6: Enriches `description` if Scout-generated description is too vague or missing
- [ ] Stage 7: Calculates and maintains `pressure_score` (Work ÷ Time) for projects with deadlines
- [ ] Agent NEVER gets importance/urgency/deadline from Scout (user-only metadata)
- [ ] Agent works incrementally to avoid overwhelming the user

### Bidirectional Obsidian Sync
- [ ] Creates markdown file in Obsidian vault for each project (e.g., `Projects/{sanitized_title}.md`)
- [ ] Syncs ALL SQL metadata to YAML frontmatter in project markdown file
- [ ] SQL → Obsidian sync runs every 15 minutes for changed projects
- [ ] Obsidian → SQL sync uses FileSystemWatcher to detect file changes immediately
- [ ] User edits in Obsidian trigger sync to SQL via Gatekeeper `update_project_direct(user_initiated=True)`
- [ ] 2-way sync ensures SQL and Obsidian converge (Accept the Drift philosophy)
- [ ] User can update project fields in EITHER Obsidian OR via Telegram commands (both paths use Gatekeeper)
- [ ] Project markdown files work with ingestion → embeddings → Scout → Monitor pipeline
- [ ] Monitor Agent checks if `discovery_id` exists in SQL before creating new project
- [ ] Prevents duplicate project creation when Scout rediscovers existing project notes
- [ ] Sync timestamps tracked: `last_synced_to_obsidian`, `last_synced_from_obsidian`

### Intelligent Communication Strategy (Natural PM Behavior)
- [ ] **Event-driven triggers**: Immediately asks next enrichment question when user responds (within seconds)
- [ ] **Natural follow-up rhythm**: Varies by importance (high: 2-3 hours, medium: 8 hours, low: 24 hours)
- [ ] **Critical deadline alerts**: Urgent projects (deadline <24 hours) get reminders every 2 hours
- [ ] **Anti-spam throttling**: Max 3 messages per hour unless truly urgent
- [ ] **Back off when appropriate**: After 3+ unanswered questions, reduce frequency
- [ ] **Stop asking gracefully**: After 5 unanswered questions for same project, mark as "user_avoiding"
- [ ] **Natural spacing**: Don't send 2+ messages within 10 minutes (unless emergency)
- [ ] Uses Message Outbox (Story 027) for all user communication with `expects_response=True` for questions
- [ ] Stalled project alerts only for high-priority projects (importance+urgency >= 7)
- [ ] No fixed daily digests - only event-driven and natural follow-ups

### Project Lifecycle Management
- [ ] Identifies stalled projects (no updates in 7+ days, high priority only: importance+urgency >= 7)
- [ ] Nudges user when deadlines approach (<3 days for high-priority projects)
- [ ] Allows status updates via Telegram commands (`/complete`, `/pause`) or Obsidian metadata edits
- [ ] Project views include `discovery_id` when available (traceability to Scout discovery)
- [ ] Project status transitions update `updated_at` timestamp automatically
- [ ] Handles project completion (status='completed', stops monitoring and enrichment)
- [ ] All user-provided metadata updates use SQL Gatekeeper `update_project_direct(user_initiated=True)`
- [ ] All SQL updates immediately sync to Obsidian markdown file

## 🎯 Architectural Role

**This story implements The Project Manager, a core component of Hermes (Interaction Layer).**

Also known as "Strategist", The Project Manager ensures projects in The Ananke don't become "write and forget." While it has scheduled triggers (daily 8 AM), it's architecturally part of Hermes because it manages the dialogue between you and project state.

Inspired by project_crystal's Strategist concept:
> **Strategist**: Calculate pressure scores (Work ÷ Time) to prioritize action.

The Project Manager transforms The Ananke from a static database into an **active project management system** that:
1. Watches for stalls (high-priority only)
2. Enforces metadata completeness (incrementally, never overwhelming)
3. Calculates urgency (pressure scores)
4. Syncs bidirectionally with Obsidian (user can work in either system)
5. Ensures Scout doesn't rediscover existing projects
6. Nudges user intelligently based on priority

**Philosophy**:
- **"Accept the Drift"** (from Crystal) - Obsidian and SQL will never match perfectly in real-time, but sync should converge
- **"Incremental Enrichment"** - Start minimal, build metadata through gentle conversation, not forms
- **"Priority-First Communication"** - Only bother the user about what matters NOW

## 🔄 Bidirectional Sync Architecture

### The Challenge
Projects exist in TWO places:
1. **The Ananke (PostgreSQL)** - Structured, queryable, trackable
2. **Obsidian Vault** - Markdown files the user can edit directly

Both must stay synchronized, and the Scout must recognize Obsidian project files as existing projects (not rediscover them).

### Sync Strategy

**SQL → Obsidian** (Project Manager creates/updates markdown):
```markdown
---
project_id: 42
discovery_id: "disco_2024_001"
title: "Build authentication system"
description: "Implement JWT-based auth with refresh tokens"
status: "active"
importance: 4
urgency: 5
deadline: 2024-12-31T23:59:59
pressure_score: 2.4
discovered_by: "latent_scout"
cluster_ids: ["cluster_123", "cluster_456"]
confidence_score: 0.85
created_at: 2024-01-15T08:00:00
updated_at: 2024-01-20T14:30:00
---

# Build authentication system

## Description
Implement JWT-based auth with refresh tokens

## Tasks
- [ ] Design token refresh flow
- [ ] Implement login endpoint
- [ ] Add session management

## Notes
Started planning on 2024-01-15. Reviewed security best practices.
```

**Obsidian → SQL** (User edits markdown, sync updates SQL):
- FileSystemWatcher monitors `Projects/` folder in Obsidian vault
- On file change, parse YAML frontmatter
- Update corresponding SQL row (match by `project_id` or `discovery_id`)
- Validate changes (can't change `project_id`, `created_at`, etc.)

**Scout Integration**:
- When Scout analyzes vault, it sees project markdown files
- Project files have `discovery_id` in frontmatter
- Monitor Agent checks: "Does this discovery_id already exist in SQL?"
- If yes → Skip creating new project (already tracked)
- If no → New discovery, send to Gatekeeper as usual

### Sync Implementation

```python
class ObsidianProjectSync:
    """
    Bidirectional sync between Ananke SQL and Obsidian markdown
    """
    def __init__(self, db_conn, vault_path: Path):
        self.db = db_conn
        self.vault_path = vault_path
        self.projects_folder = vault_path / "Projects"
        self.projects_folder.mkdir(exist_ok=True)

        # Setup file watcher
        self.observer = Observer()
        self.observer.schedule(
            ProjectFileHandler(self),
            str(self.projects_folder),
            recursive=False
        )
        self.observer.start()

    def sync_project_to_obsidian(self, project_id: int):
        """
        SQL → Obsidian: Create or update markdown file
        """
        cursor = self.db.cursor()
        cursor.execute("SELECT * FROM projects WHERE id = %s", (project_id,))
        project = cursor.fetchone()

        if not project:
            return

        # Generate markdown filename (sanitize title)
        filename = sanitize_filename(project['title']) + ".md"
        file_path = self.projects_folder / filename

        # Build YAML frontmatter
        frontmatter = {
            'project_id': project['id'],
            'discovery_id': project['discovery_id'],
            'title': project['title'],
            'description': project['description'],
            'status': project['status'],
            'importance': project['importance'],
            'urgency': project['urgency'],
            'deadline': project['deadline'].isoformat() if project['deadline'] else None,
            'pressure_score': project['pressure_score'],
            'discovered_by': project['discovered_by'],
            'cluster_ids': project['cluster_ids'],
            'confidence_score': project['confidence_score'],
            'created_at': project['created_at'].isoformat(),
            'updated_at': project['updated_at'].isoformat(),
        }

        # Build markdown content
        content = f"""---
{yaml.dump(frontmatter, sort_keys=False)}---

# {project['title']}

## Description
{project['description'] or 'No description yet.'}

## Tasks
<!-- Add your task checklist here -->

## Notes
<!-- Add your project notes here -->
"""

        # Write to file
        file_path.write_text(content)
        log_info(f"Synced project {project_id} to {file_path}")

    def sync_obsidian_to_sql(self, file_path: Path):
        """
        Obsidian → SQL: User edited markdown, update SQL
        """
        content = file_path.read_text()

        # Parse frontmatter
        match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
        if not match:
            log_warning(f"No frontmatter found in {file_path}")
            return

        frontmatter = yaml.safe_load(match.group(1))
        project_id = frontmatter.get('project_id')

        if not project_id:
            log_warning(f"No project_id in {file_path}")
            return

        # Extract user-editable fields from frontmatter
        updates = {
            'title': frontmatter.get('title'),
            'description': frontmatter.get('description'),
            'status': frontmatter.get('status'),
            'importance': frontmatter.get('importance'),
            'urgency': frontmatter.get('urgency'),
            'deadline': datetime.fromisoformat(frontmatter['deadline']) if frontmatter.get('deadline') else None,
            'updated_at': datetime.now(),
        }

        # Update SQL
        cursor = self.db.cursor()
        cursor.execute("""
            UPDATE projects
            SET title = %(title)s,
                description = %(description)s,
                status = %(status)s,
                importance = %(importance)s,
                urgency = %(urgency)s,
                deadline = %(deadline)s,
                updated_at = %(updated_at)s
            WHERE id = %(project_id)s
        """, {**updates, 'project_id': project_id})

        self.db.commit()
        log_info(f"Synced {file_path} to SQL project {project_id}")


class ProjectFileHandler(FileSystemEventHandler):
    """
    Watches Obsidian Projects/ folder for changes
    """
    def __init__(self, sync: ObsidianProjectSync):
        self.sync = sync

    def on_modified(self, event):
        if event.is_directory or not event.src_path.endswith('.md'):
            return

        file_path = Path(event.src_path)
        self.sync.sync_obsidian_to_sql(file_path)
```

## 📊 Enhanced Ananke Schema

The existing schema from Story 014 needs additional fields for incremental enrichment:

```sql
-- Extended from Story 014 schema
CREATE TABLE projects (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,

    -- Source tracking
    discovered_by TEXT,  -- 'latent_scout', 'manual', 'prometheus'
    discovery_id TEXT,   -- Link back to Discovery Vector DB
    cluster_ids TEXT[],  -- Which clusters contributed

    -- Confidence and verification
    confidence_score FLOAT,
    verified_by_user BOOLEAN DEFAULT FALSE,
    verified_at TIMESTAMP,

    -- NEW: User-provided priority fields (incremental enrichment)
    importance INTEGER CHECK (importance >= 1 AND importance <= 5),  -- How important? (1-5)
    urgency INTEGER CHECK (urgency >= 1 AND urgency <= 5),          -- How urgent? (1-5)
    work_estimate INTEGER,  -- Hours estimated (optional, for pressure calculation)

    -- Project management fields
    status TEXT DEFAULT 'candidate',  -- candidate, active, paused, completed
    deadline TIMESTAMP,
    pressure_score FLOAT,  -- Work ÷ Time (Strategist calculates)

    -- NEW: Obsidian sync tracking
    obsidian_file_path TEXT,  -- Path to markdown file in vault
    last_synced_to_obsidian TIMESTAMP,
    last_synced_from_obsidian TIMESTAMP,

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_projects_confidence ON projects(confidence_score);
CREATE INDEX idx_projects_verified ON projects(verified_by_user);
CREATE INDEX idx_projects_priority ON projects(importance, urgency);  -- NEW: for prioritization
CREATE UNIQUE INDEX idx_projects_discovery_id ON projects(discovery_id) WHERE discovery_id IS NOT NULL;
```

**Key additions**:
1. `importance` (1-5): How important is this project to your goals?
2. `urgency` (1-5): How time-sensitive is this?
3. `work_estimate`: Optional hours estimate for pressure calculation
4. `obsidian_file_path`: Track which markdown file represents this project
5. `last_synced_to_obsidian` / `last_synced_from_obsidian`: Sync timestamps

**Priority Calculation**: `priority_score = importance × urgency × time_pressure_factor`

## 🔄 Incremental Enrichment Strategy

The Project Manager builds project metadata step-by-step through conversation:

### Stage 1: Initial Creation (from Gatekeeper after Scout/Monitor approval)
```
Projects created by SQL Gatekeeper (Story 014) with:
✓ title (Scout-generated)
✓ description (Scout-generated, may be brief or empty)
✓ discovered_by = 'latent_scout'
✓ discovery_id (link to Discovery record)
✓ cluster_ids (which clusters contributed)
✓ confidence_score (Scout's confidence)
✓ verified_by_user = True (user approved via Gatekeeper)
✓ verified_at (timestamp of approval)
✓ status = 'candidate'

Missing user-only metadata (Project Manager will request):
✗ importance (NULL) - How important? (1-5)
✗ urgency (NULL) - How urgent? (1-5)
✗ deadline (NULL) - When is it due?
✗ work_estimate (NULL) - How long will it take? (optional)
```

### Stage 2: Gather Importance
```
Agent asks (for projects missing importance):
"📊 How important is 'Build authentication system'?
1 = Nice to have
3 = Should do
5 = Critical

Reply: /importance 42 5"
```

### Stage 3: Gather Urgency
```
Agent asks (for projects with importance, missing urgency):
"⏰ How urgent is 'Build authentication system'?
1 = Someday
3 = This month
5 = This week

Reply: /urgency 42 5"
```

### Stage 4: Focus on High Priority
```
Only projects with importance + urgency >= 7 get further enrichment requests.
Low-priority projects stay minimal until user changes priority.
```

### Stage 5: Gather Deadline (High Priority Only)
```
Agent asks (for active high-priority projects missing deadline):
"🎯 When should 'Build authentication system' be done?

Quick options:
/deadline 42 7d
/deadline 42 2w
/deadline 42 2024-12-31"
```

### Stage 6: Enrich Description (High Priority Only, if Scout description is vague)
```
Agent asks (for high-priority projects with empty/vague Scout-generated description):
"📝 Add more context to 'Build authentication system'?

Current description: 'Authentication related tasks'

Add details via:
/describe 42 [your description]
Or edit in Obsidian: Projects/Build authentication system.md"

Note: This stage is optional - Scout usually provides a description.
Only ask if description is missing or obviously too generic.
```

### Stage 7: Calculate Pressure
```
For projects with deadline:
pressure_score = work_estimate / hours_remaining
(uses default 20h if no work_estimate)
```

### Communication Prioritization (Duolingo-Inspired)

**Event-Driven (Immediate)**:
- User responds → Ask NEXT enrichment question immediately (within seconds)
- New project approved → Ask importance within 5 minutes
- Deadline approaching (<3 days) → Reminder every 2 hours until response

**Persistent Nudging (Background Scheduler)**:
- Check every 2 hours for unanswered enrichment questions
- If no response after 6 hours → Send gentle reminder
- If no response after 24 hours → Escalate in daily digest
- Urgent items get reminders every 2 hours (like Duolingo's "streak at risk!")

**Like a Real PM** (Natural Communication Patterns):

**Immediate** (Within seconds):
- New project approved → "Quick question about {title}: how important is this? (1-5)"
- User responds → "Got it. How urgent? (1-5)"
- Deadline <24 hours → "🔥 {title} due in {X} hours - are you on track?"

**Gentle Follow-up** (Hours later):
- No response after 4-6 hours → "Hey, still need to know importance for {title} when you have a sec"
- Second no-response (12-24 hours) → "Don't forget about {title} - blocking until I know importance/urgency"

**Escalating Persistence** (For important items):
- High priority item stalling → Check in every few hours
- Low priority item → Maybe once a day, then back off

**Back Off When Appropriate**:
- User marking things complete → No questions, just "Nice work!"
- Many active projects → Focus on top 2-3, don't overwhelm
- Weekend → Reduce frequency unless critical deadline

**Natural Throttling**:
- Don't send 2+ messages within 10 minutes (unless true emergency)
- If user hasn't responded to 3+ questions → Pause, wait for them to engage
- After 5 unanswered questions for same project → Stop asking, mark as "user_avoiding"

**Smart Context**:
- "3 projects need deadlines - want to set them now or later today?"
- "You completed 2 projects this week! 3 more approaching deadlines..."

**No rigid quotas** - Behave like a human PM would!

## Technical Notes

### Project Manager Agent Class

```python
class ProjectManagerAgent:
    """
    Active project management for The Ananke
    With incremental enrichment and Obsidian sync
    """
    def __init__(self, db_conn, messenger, obsidian_sync):
        self.db = db_conn
        self.messenger = messenger  # Hermes Message Outbox
        self.obsidian_sync = obsidian_sync
        self.enrichment_queue = []  # Track what to ask next

    def run_daily_management(self):
        """
        Daily project management routine
        """
        # 1. Sync all projects to Obsidian (if changed)
        self._sync_changed_projects_to_obsidian()

        # 2. Build enrichment queue (prioritized)
        self._build_enrichment_queue()

        # 3. Request ONE piece of missing data from ONE project
        self._request_next_enrichment()

        # 4. Calculate pressure scores
        self._update_pressure_scores()

        # 5. Check stalled projects (high priority only)
        self._check_stalled_projects()

        # 6. Check approaching deadlines
        self._check_approaching_deadlines()

        # 7. Send daily digest (top 3 priorities only)
        self._send_daily_digest()

    def _build_enrichment_queue(self):
        """
        Prioritize which metadata to request next
        Strategy: importance → urgency → deadline → description
        Only focus on high-priority (importance+urgency >= 7) for deadline/description
        """
        cursor = self.db.cursor()

        # Priority 1: Get importance for new projects
        cursor.execute("""
            SELECT id, title FROM projects
            WHERE importance IS NULL
            AND status IN ('candidate', 'active')
            ORDER BY created_at ASC
            LIMIT 3
        """)

        for project_id, title in cursor.fetchall():
            self.enrichment_queue.append({
                'project_id': project_id,
                'title': title,
                'field': 'importance',
                'priority': 1
            })

        # Priority 2: Get urgency for projects with importance
        cursor.execute("""
            SELECT id, title, importance FROM projects
            WHERE importance IS NOT NULL
            AND urgency IS NULL
            AND status IN ('candidate', 'active')
            ORDER BY importance DESC, created_at ASC
            LIMIT 3
        """)

        for project_id, title, importance in cursor.fetchall():
            self.enrichment_queue.append({
                'project_id': project_id,
                'title': title,
                'field': 'urgency',
                'priority': 2
            })

        # Priority 3: Get deadline for high-priority active projects
        cursor.execute("""
            SELECT id, title, importance, urgency FROM projects
            WHERE importance IS NOT NULL
            AND urgency IS NOT NULL
            AND (importance + urgency) >= 7
            AND deadline IS NULL
            AND status = 'active'
            ORDER BY (importance + urgency) DESC
            LIMIT 2
        """)

        for project_id, title, importance, urgency in cursor.fetchall():
            self.enrichment_queue.append({
                'project_id': project_id,
                'title': title,
                'field': 'deadline',
                'priority': 3
            })

        # Priority 4: Enrich description for high-priority projects (if Scout description is vague)
        cursor.execute("""
            SELECT id, title, description FROM projects
            WHERE importance IS NOT NULL
            AND urgency IS NOT NULL
            AND (importance + urgency) >= 7
            AND (description IS NULL OR description = '' OR LENGTH(description) < 20)
            AND status = 'active'
            ORDER BY (importance + urgency) DESC
            LIMIT 1
        """)

        for project_id, title, current_desc in cursor.fetchall():
            self.enrichment_queue.append({
                'project_id': project_id,
                'title': title,
                'current_description': current_desc,
                'field': 'description',
                'priority': 4
            })

    def _request_next_enrichment(self):
        """
        Request ONE piece of missing data (never overwhelm user)
        """
        if not self.enrichment_queue:
            return

        # Sort by priority, take top 1
        self.enrichment_queue.sort(key=lambda x: x['priority'])
        item = self.enrichment_queue[0]

        if item['field'] == 'importance':
            self._request_importance(item['project_id'], item['title'])
        elif item['field'] == 'urgency':
            self._request_urgency(item['project_id'], item['title'])
        elif item['field'] == 'deadline':
            self._request_deadline(item['project_id'], item['title'])
        elif item['field'] == 'description':
            current_desc = item.get('current_description')
            self._request_description(item['project_id'], item['title'], current_desc)

    def _request_importance(self, project_id: int, title: str):
        """
        Ask user to rate importance (1-5)
        """
        message_text = f"""
📊 **Rate Project Importance**

**Project**: {title}

How important is this project to your goals?
1️⃣ = Nice to have
3️⃣ = Should do
5️⃣ = Critical

Reply: `/importance {project_id} [1-5]`
"""
        self.messenger.enqueue(
            message_type='question',
            payload={'text': message_text},
            originating_agent='project_manager',
            context_id=f'project:{project_id}',
            expects_response=True
        )

    def _request_urgency(self, project_id: int, title: str):
        """
        Ask user to rate urgency (1-5)
        """
        message_text = f"""
⏰ **Rate Project Urgency**

**Project**: {title}

How time-sensitive is this project?
1️⃣ = Someday
3️⃣ = This month
5️⃣ = This week

Reply: `/urgency {project_id} [1-5]`
"""
        self.messenger.enqueue(
            message_type='question',
            payload={'text': message_text},
            originating_agent='project_manager',
            context_id=f'project:{project_id}',
            expects_response=True
        )

    def _request_deadline(self, project_id: int, title: str):
        """
        Ask user to set a deadline
        """
        message_text = f"""
🎯 **Set Project Deadline**

**Project**: {title}

When should this be done?

Quick options:
`/deadline {project_id} 7d` - Due in 7 days
`/deadline {project_id} 2w` - Due in 2 weeks
`/deadline {project_id} 1m` - Due in 1 month
`/deadline {project_id} 2024-12-31` - Specific date
"""
        self.messenger.enqueue(
            message_type='question',
            payload={'text': message_text},
            originating_agent='project_manager',
            context_id=f'project:{project_id}',
            expects_response=True
        )

    def _request_description(self, project_id: int, title: str, current_desc: str = None):
        """
        Ask user to enrich vague Scout-generated description
        """
        obsidian_path = self._get_obsidian_path(project_id)

        current_text = f'\nCurrent: "{current_desc}"' if current_desc else ""

        message_text = f"""
📝 **Enrich Project Description**

**Project**: {title}{current_text}

The Scout provided a basic description, but more context would help.

Add details via:
1. Telegram: `/describe {project_id} [your description]`
2. Obsidian: Edit `{obsidian_path}`

Better descriptions improve tracking and planning.
"""
        self.messenger.enqueue(
            message_type='question',
            payload={'text': message_text},
            originating_agent='project_manager',
            context_id=f'project:{project_id}',
            expects_response=True
        )

    def _sync_changed_projects_to_obsidian(self):
        """
        Sync any SQL changes to Obsidian markdown files
        """
        cursor = self.db.cursor()

        # Find projects modified since last Obsidian sync
        cursor.execute("""
            SELECT id FROM projects
            WHERE updated_at > last_synced_to_obsidian
            OR last_synced_to_obsidian IS NULL
        """)

        for (project_id,) in cursor.fetchall():
            self.obsidian_sync.sync_project_to_obsidian(project_id)

            # Mark as synced
            cursor.execute("""
                UPDATE projects
                SET last_synced_to_obsidian = %s
                WHERE id = %s
            """, (datetime.now(), project_id))

        self.db.commit()

    def _update_pressure_scores(self):
        """
        Calculate pressure = Work ÷ Time for all active projects with deadlines
        """
        cursor = self.db.cursor()

        cursor.execute("""
            SELECT id, deadline, work_estimate, importance, urgency
            FROM projects
            WHERE status = 'active'
            AND deadline IS NOT NULL
        """)

        for project_id, deadline, work_estimate, importance, urgency in cursor.fetchall():
            # Calculate time pressure
            time_remaining_hours = (deadline - datetime.now()).total_seconds() / 3600

            if time_remaining_hours <= 0:
                time_pressure = 999.0  # Overdue!
            else:
                # Use work estimate if available, else default by importance
                if not work_estimate:
                    work_estimate = importance * 10 if importance else 20

                time_pressure = work_estimate / time_remaining_hours

            # Combine with user-provided priority
            priority_factor = (importance or 3) * (urgency or 3)
            pressure_score = time_pressure * priority_factor

            # Update in database
            cursor.execute("""
                UPDATE projects
                SET pressure_score = %s,
                    updated_at = %s
                WHERE id = %s
            """, (pressure_score, datetime.now(), project_id))

        self.db.commit()

    def _check_stalled_projects(self):
        """
        Only alert on stalled HIGH-PRIORITY projects
        """
        cursor = self.db.cursor()

        cursor.execute("""
            SELECT id, title, status, updated_at, importance, urgency
            FROM projects
            WHERE status IN ('candidate', 'active')
            AND updated_at < NOW() - INTERVAL '7 days'
            AND importance IS NOT NULL
            AND urgency IS NOT NULL
            AND (importance + urgency) >= 7
        """)

        stalled = cursor.fetchall()

        if stalled:
            self._send_stall_alert(stalled)

    def _send_stall_alert(self, stalled_projects: List[Tuple]):
        """
        Notify about stalled high-priority projects only
        """
        message = f"""
🚨 **High-Priority Projects Stalled**

{len(stalled_projects)} important project(s) have no updates in 7+ days:

"""

        for project_id, title, status, updated_at, importance, urgency in stalled_projects:
            days_stalled = (datetime.now() - updated_at).days

            message += f"""
• **{title}**
  Priority: {importance}×{urgency} | Last update: {days_stalled}d ago
  `/view {project_id}` | `/update {project_id}`

"""

        self.messenger.send_message(message)

    def _check_approaching_deadlines(self):
        """
        Nudge for deadlines within 3 days (high priority only)
        """
        cursor = self.db.cursor()

        cursor.execute("""
            SELECT id, title, deadline, pressure_score, importance, urgency
            FROM projects
            WHERE status = 'active'
            AND deadline IS NOT NULL
            AND deadline BETWEEN NOW() AND NOW() + INTERVAL '3 days'
            AND importance IS NOT NULL
            AND urgency IS NOT NULL
            AND (importance + urgency) >= 7
        """)

        approaching = cursor.fetchall()

        for project_id, title, deadline, pressure, importance, urgency in approaching:
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
**Deadline**: {deadline.strftime('%Y-%m-%d %H:%M')}
**Time left**: {days_left}d {hours_left}h
**Pressure**: {pressure:.1f}

**Quick actions**:
`/complete {project_id}` - Mark as done
`/extend {project_id} 3d` - Extend deadline
`/view {project_id}` - View details
"""

        self.messenger.send_message(message)

    def _send_daily_digest(self):
        """
        Smart daily digest: TOP 3 priorities only
        """
        cursor = self.db.cursor()

        # Top 3 high-pressure projects
        cursor.execute("""
            SELECT title, deadline, pressure_score, importance, urgency
            FROM projects
            WHERE status = 'active'
            AND pressure_score IS NOT NULL
            ORDER BY pressure_score DESC
            LIMIT 3
        """)

        high_pressure = cursor.fetchall()

        if not high_pressure:
            return  # Don't send empty digest

        message = f"""
📋 **Daily Focus**
{datetime.now().strftime('%B %d, %Y')}

**Top Priorities**:
"""

        for title, deadline, pressure, importance, urgency in high_pressure:
            time_left = deadline - datetime.now()
            days_left = time_left.days

            message += f"• {title} ({days_left}d left, priority: {importance}×{urgency})\n"

        message += "\nUse `/projects` to see all."

        self.messenger.send_message(message)
```

### Telegram Commands (Updated)

```python
@hermes_bot.command("importance")
def cmd_set_importance(message, project_id: int, importance: int):
    """
    Set project importance (1-5)
    """
    if not 1 <= importance <= 5:
        return "Importance must be 1-5"

    # Use SQL Gatekeeper for direct user update (bypasses approval)
    success = sql_gatekeeper.update_project_direct(
        project_id=project_id,
        updates={'importance': importance},
        user_initiated=True
    )

    if success:
        # Record response in outbox for agent routing
        agent = outbox.record_response(
            context_id=f'project:{project_id}',
            response_data={'field': 'importance', 'value': importance}
        )

        # Sync to Obsidian
        obsidian_sync.sync_project_to_obsidian(project_id)

        bot.send_message(message.chat.id, f"✅ Importance set to {importance}")
    else:
        bot.send_message(message.chat.id, f"❌ Failed to update project {project_id}")


@hermes_bot.command("urgency")
def cmd_set_urgency(message, project_id: int, urgency: int):
    """
    Set project urgency (1-5)
    """
    if not 1 <= urgency <= 5:
        return "Urgency must be 1-5"

    # Use SQL Gatekeeper for direct user update
    success = sql_gatekeeper.update_project_direct(
        project_id=project_id,
        updates={'urgency': urgency},
        user_initiated=True
    )

    if success:
        outbox.record_response(
            context_id=f'project:{project_id}',
            response_data={'field': 'urgency', 'value': urgency}
        )
        obsidian_sync.sync_project_to_obsidian(project_id)
        bot.send_message(message.chat.id, f"✅ Urgency set to {urgency}")
    else:
        bot.send_message(message.chat.id, f"❌ Failed to update project {project_id}")


@hermes_bot.command("deadline")
def cmd_set_deadline(message, project_id: int, deadline: str):
    """
    Set project deadline
    Usage: /deadline 123 7d OR /deadline 123 2024-12-31
    """
    deadline_dt = parse_deadline(deadline)

    # Use SQL Gatekeeper for direct user update
    success = sql_gatekeeper.update_project_direct(
        project_id=project_id,
        updates={'deadline': deadline_dt},
        user_initiated=True
    )

    if success:
        outbox.record_response(
            context_id=f'project:{project_id}',
            response_data={'field': 'deadline', 'value': deadline_dt.isoformat()}
        )
        obsidian_sync.sync_project_to_obsidian(project_id)
        bot.send_message(message.chat.id, f"✅ Deadline: {deadline_dt.strftime('%Y-%m-%d')}")
    else:
        bot.send_message(message.chat.id, f"❌ Failed to update project {project_id}")


@hermes_bot.command("describe")
def cmd_set_description(message, project_id: int, *description_words):
    """
    Set project description
    Usage: /describe 123 This is the project description
    """
    description = " ".join(description_words)

    # Use SQL Gatekeeper for direct user update
    success = sql_gatekeeper.update_project_direct(
        project_id=project_id,
        updates={'description': description},
        user_initiated=True
    )

    if success:
        outbox.record_response(
            context_id=f'project:{project_id}',
            response_data={'field': 'description', 'value': description}
        )
        obsidian_sync.sync_project_to_obsidian(project_id)
        bot.send_message(message.chat.id, "✅ Description updated")
    else:
        bot.send_message(message.chat.id, f"❌ Failed to update project {project_id}")


@hermes_bot.command("projects")
def cmd_projects(message, status: str = "active"):
    """
    List projects (sorted by priority)
    """
    cursor = db.cursor()

    if status == "all":
        cursor.execute("""
            SELECT * FROM projects
            ORDER BY
                CASE WHEN importance IS NOT NULL AND urgency IS NOT NULL
                     THEN importance * urgency
                     ELSE 0
                END DESC,
                pressure_score DESC NULLS LAST
        """)
    else:
        cursor.execute("""
            SELECT * FROM projects
            WHERE status = %s
            ORDER BY
                CASE WHEN importance IS NOT NULL AND urgency IS NOT NULL
                     THEN importance * urgency
                     ELSE 0
                END DESC,
                pressure_score DESC NULLS LAST
        """, (status,))

    projects = cursor.fetchall()

    if not projects:
        return f"No {status} projects."

    response = f"📋 **{status.title()} Projects**\n\n"

    for p in projects:
        priority_str = ""
        if p['importance'] and p['urgency']:
            priority_str = f"Priority: {p['importance']}×{p['urgency']}"

        deadline_str = p['deadline'].strftime('%Y-%m-%d') if p['deadline'] else "No deadline"

        response += f"""
**{p['title']}**
{priority_str} | {deadline_str}
`/view {p['id']}`

"""

    bot.send_message(message.chat.id, response, parse_mode='Markdown')


@hermes_bot.command("view")
def cmd_view_project(message, project_id: int):
    """
    View full project details
    """
    project = get_project(project_id)

    if not project:
        return "Project not found."

    obsidian_path = project['obsidian_file_path'] or "Not synced yet"

    detail_message = f"""
📊 **Project Details**

**Title**: {project['title']}
**Description**: {project['description'] or 'No description'}

**Status**: {project['status']}
**Importance**: {project['importance'] or 'Not set'} (1-5)
**Urgency**: {project['urgency'] or 'Not set'} (1-5)
**Deadline**: {project['deadline'].strftime('%Y-%m-%d') if project['deadline'] else 'Not set'}
**Pressure**: {project['pressure_score']:.1f if project['pressure_score'] else 'N/A'}

**Obsidian**: `{obsidian_path}`
**Discovery ID**: {project['discovery_id'] or 'N/A'}
**Created**: {project['created_at'].strftime('%Y-%m-%d')}
**Updated**: {project['updated_at'].strftime('%Y-%m-%d')}

**Actions**:
`/importance {project_id} [1-5]`
`/urgency {project_id} [1-5]`
`/deadline {project_id} [date]`
`/complete {project_id}`
"""

    bot.send_message(message.chat.id, detail_message, parse_mode='Markdown')


@hermes_bot.command("complete")
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
    bot.send_message(message.chat.id, "🎉 Project completed!")
```

### Scheduled Job Integration (Natural PM Rhythm)

```python
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()

# Main check loop - runs every 30 minutes
# This is the "thinking" loop where PM decides what to do
scheduler.add_job(
    project_manager.run_pm_check_cycle,
    'interval',
    minutes=30,
    id='pm_check_cycle'
)

# Update pressure scores every hour (background calculation)
scheduler.add_job(
    project_manager.update_all_pressure_scores,
    'interval',
    hours=1,
    id='pressure_updater'
)

# Sync to Obsidian every 15 minutes (background)
scheduler.add_job(
    project_manager.sync_changed_projects,
    'interval',
    minutes=15,
    id='obsidian_syncer'
)

scheduler.start()
```

### Main PM Check Cycle

```python
def run_pm_check_cycle(self):
    """
    Main PM "thinking" loop - runs every 30 minutes
    Decides what needs attention RIGHT NOW based on natural PM behavior
    """
    # 1. Check for truly urgent items (deadline <24h)
    urgent_items = self._get_critical_deadlines()
    for item in urgent_items:
        self._handle_critical_deadline(item)
        time.sleep(2)  # Natural spacing between messages

    # 2. Check for unanswered questions (varying by time waiting)
    self._follow_up_on_unanswered_questions()

    # 3. Check for new projects needing initial metadata
    self._check_new_projects()

    # 4. Check for stalled high-priority projects
    self._check_stalled_projects()

    # 5. Opportunistic nudges (if haven't sent many messages recently)
    if self._messages_sent_last_hour() < 3:
        self._send_opportunistic_nudge()

def _follow_up_on_unanswered_questions(self):
    """
    Natural PM follow-up rhythm based on how long user has been silent
    """
    cursor = self.db.cursor()

    # Get unanswered questions with different time thresholds
    cursor.execute("""
        SELECT context_id, created_at, payload_json
        FROM message_outbox
        WHERE status = 'awaiting_response'
        AND originating_agent = 'project_manager'
    """)

    for context_id, created_at, payload in cursor.fetchall():
        hours_waiting = (datetime.now() - created_at).total_seconds() / 3600
        project_id = int(context_id.split(':')[1])

        # Get project to check importance
        project = self._get_project(project_id)

        # Natural follow-up timing based on importance
        if not project.importance:
            # Don't know importance yet - gentle persistence
            if 4 <= hours_waiting < 5:
                self._send_gentle_reminder(project_id, "first")
            elif 12 <= hours_waiting < 13:
                self._send_gentle_reminder(project_id, "second")
            elif hours_waiting >= 24:
                self._mark_as_avoiding(project_id)
        else:
            # Know importance - adjust rhythm
            importance = project.importance
            if importance >= 4:  # High importance
                if 2 <= hours_waiting < 3:
                    self._send_gentle_reminder(project_id, "first")
                elif 6 <= hours_waiting < 7:
                    self._send_escalated_reminder(project_id)
            elif importance == 3:  # Medium importance
                if 8 <= hours_waiting < 9:
                    self._send_gentle_reminder(project_id, "first")
                elif hours_waiting >= 24:
                    self._send_final_reminder(project_id)
            else:  # Low importance
                if hours_waiting >= 24:
                    self._send_gentle_reminder(project_id, "first")
                elif hours_waiting >= 72:
                    self._stop_asking(project_id)

def _messages_sent_last_hour(self) -> int:
    """
    Count how many messages PM sent in last hour
    Used to avoid overwhelming user
    """
    cursor = self.db.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM message_outbox
        WHERE originating_agent = 'project_manager'
        AND created_at > NOW() - INTERVAL '1 hour'
    """)
    return cursor.fetchone()[0]

def _send_gentle_reminder(self, project_id: int, attempt: str):
    """
    Gentle, non-pushy reminder
    """
    project = self._get_project(project_id)

    if attempt == "first":
        message = f"Hey, still need info on '{project.title}' when you get a chance 😊"
    else:
        message = f"Following up on '{project.title}' - need those details to help track it!"

    self.messenger.enqueue(
        message_type='question',
        payload={'text': message},
        originating_agent='project_manager',
        context_id=f'project:{project_id}',
        expects_response=True
    )
```

### Event-Driven Response Handler

```python
# In Telegram command handlers - trigger immediate next question
@hermes_bot.command("importance")
def cmd_importance(message, project_id: int, importance: int):
    """User responds to importance question"""
    # ... (existing SQL Gatekeeper update code)

    if success:
        # Record response
        outbox.record_response(...)
        obsidian_sync.sync_project_to_obsidian(project_id)

        # EVENT-DRIVEN: Immediately ask next question
        project_manager.continue_enrichment(project_id)

        bot.send_message(message.chat.id, f"✅ Importance set to {importance}")


class ProjectManagerAgent:
    # ...

    def continue_enrichment(self, project_id: int):
        """
        Event-driven: User just responded, ask next question immediately
        """
        # Rebuild queue for THIS project only
        cursor = self.db.cursor()

        # Check what's still missing
        cursor.execute("SELECT * FROM projects WHERE id = %s", (project_id,))
        project = cursor.fetchone()

        if not project:
            return

        # Determine next field to request
        if not project['urgency'] and project['importance']:
            self._request_urgency(project_id, project['title'])
        elif not project['deadline'] and project['importance'] and project['urgency']:
            if (project['importance'] + project['urgency']) >= 7:
                self._request_deadline(project_id, project['title'])
        # ... continue chain

    def check_pending_enrichments(self):
        """
        Background job: Check for unanswered enrichment questions
        Runs every 2 hours
        """
        cursor = self.db.cursor()

        # Find messages awaiting response for >6 hours
        cursor.execute("""
            SELECT context_id, created_at, payload_json
            FROM message_outbox
            WHERE status = 'awaiting_response'
            AND message_type = 'question'
            AND originating_agent = 'project_manager'
            AND created_at < NOW() - INTERVAL '6 hours'
        """)

        pending = cursor.fetchall()

        for context_id, created_at, payload in pending:
            hours_waiting = (datetime.now() - created_at).total_seconds() / 3600

            # Extract project_id from context_id (format: "project:42")
            project_id = int(context_id.split(':')[1])

            # Send reminder
            self._send_reminder(project_id, hours_waiting)

    def check_urgent_deadlines(self):
        """
        Background job: Aggressive reminders for approaching deadlines
        Runs every 2 hours
        """
        cursor = self.db.cursor()

        cursor.execute("""
            SELECT id, title, deadline, importance, urgency
            FROM projects
            WHERE status = 'active'
            AND deadline IS NOT NULL
            AND deadline < NOW() + INTERVAL '3 days'
            AND (importance + urgency) >= 7
        """)

        urgent = cursor.fetchall()

        for project_id, title, deadline, importance, urgency in urgent:
            self._send_urgent_reminder(project_id, title, deadline)
```

## Dependencies
- The Ananke (PostgreSQL projects table with new fields)
- Hermes (Telegram bot + Message Outbox from Story 027)
- Aletheia (Obsidian vault access for sync)
- project_crystal Strategist concept (pressure scores)
- FileSystemWatcher (watchdog library) for Obsidian file monitoring

## Affected Components
- **Argus**: Project Manager agent (Strategist)
- **Alexandria**: The Ananke (PostgreSQL schema extension)
- **Hermes**: Project management Telegram commands + Message Outbox integration
- **Aletheia**: Obsidian sync layer (read/write project markdown files)

## Priority
**High** - Turns static SQL into active, intelligent project management with seamless Obsidian integration

## Estimate
13 story points (8-10 days) - increased from 8 due to bidirectional sync complexity

## Linear Labels
`phase-4`, `project-management`, `strategist`, `argus`, `hermes`, `alexandria`, `aletheia`, `obsidian-sync`

## Related Stories
- Story 014: SQL Project Gatekeeper (creates projects in Ananke)
- Story 015: Monitor Agent (ensures discoveries become projects)
- Story 027: Message Outbox Relay (communication infrastructure)
- Story 025: Shadow Copy & Hygiene Layer (Obsidian safety)
- project_crystal Strategist concept

## Future Enhancements
- Sub-tasks: Break projects into actionable steps with progress tracking
- Calendar integration: Sync deadlines to Google Calendar
- Team mode: Assign projects to team members
- Burndown charts: Visualize project progress over time
- Smart work estimates: Learn typical project durations
- Context-aware nudges: Adjust frequency based on user response patterns
- Conflict resolution UI: When Obsidian and SQL diverge, present merge options
