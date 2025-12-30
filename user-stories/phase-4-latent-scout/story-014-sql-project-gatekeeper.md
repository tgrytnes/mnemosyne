# Story 014: SQL Project Gatekeeper (The Gates)

**As a** user
**I want** strict control over what gets written to my SQL project database
**So that** only verified, high-confidence projects become hard commitments in The Ananke

## 🎯 Architectural Role

**This story implements the SQL Project Gatekeeper (part of The Gates approval layer).**

The SQL Gatekeeper is one of two gatekeepers in The Gates layer (along with the Obsidian Gatekeeper from Story 025). It controls ALL writes to The Ananke, ensuring projects only become commitments after your explicit approval.

## Acceptance Criteria
- [ ] No direct writes to The Ananke `projects` table without gatekeeper approval
- [ ] High-confidence discoveries (>80%) trigger automatic approval request
- [ ] Medium-confidence discoveries (60-80%) require user confirmation
- [ ] Low-confidence discoveries (<60%) never auto-request, only visible in feed
- [ ] User approval via Telegram: `/approve_project {discovery_id}`
- [ ] SQL write only happens AFTER user confirms
- [ ] Failed writes logged and retryable
- [ ] Audit trail: all approved/rejected project writes
- [ ] Rollback capability: `/remove_project {project_id}`

## Critical Architectural Decision

**The Ananke (PostgreSQL) is the "hard facts" database.**

Once a project is written to The Ananke, it becomes:
- A commitment (not just a suggestion)
- Tracked with deadlines and pressure scores
- Subject to Monitor agent oversight (Phase 4 future)
- Part of your "execution reality" (vs fuzzy creative brain)

**This is why the gatekeeper is critical**: We must prevent noise from polluting the hard facts database.

**See [SYSTEM_ARCHITECTURE.md](../SYSTEM_ARCHITECTURE.md) and project_crystal README for the Crystal philosophy.**

## Technical Notes

### The Ananke Schema (Projects Table)

```sql
-- From project_crystal/init.sql
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

    -- Project management fields
    status TEXT DEFAULT 'candidate',  -- candidate, active, paused, completed
    deadline TIMESTAMP,
    pressure_score FLOAT,  -- Work ÷ Time (Strategist calculates)

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_projects_confidence ON projects(confidence_score);
CREATE INDEX idx_projects_verified ON projects(verified_by_user);
```

### SQL Gatekeeper Class

```python
class SQLProjectGatekeeper:
    """
    Controls ALL writes to The Ananke projects table
    Based on project_crystal gatekeeper concept
    """
    def __init__(self, db_conn, messenger):
        self.db = db_conn
        self.messenger = messenger  # Hermes Telegram bot
        self.pending_approvals = {}

    def request_project_write(self, discovery: DiscoveryRecord):
        """
        Latent Scout wants to write a project - ask for permission
        """
        # 1. Check confidence threshold
        if discovery.confidence_score < 0.60:
            # Too low - don't even ask
            log_info(f"Discovery {discovery.id} below threshold (0.60), not requesting approval")
            return

        # 2. High confidence: auto-request approval
        if discovery.confidence_score >= 0.80:
            return self._request_approval(discovery, auto_approve=False)

        # 3. Medium confidence: require explicit confirmation
        if discovery.confidence_score >= 0.60:
            return self._request_approval(discovery, auto_approve=False)

    def _request_approval(self, discovery: DiscoveryRecord, auto_approve: bool = False):
        """
        Send approval request via Telegram
        """
        approval_id = str(uuid4())

        # Store pending approval
        self.pending_approvals[approval_id] = {
            'discovery': discovery,
            'requested_at': datetime.now(),
            'auto_approve': auto_approve
        }

        # Format message
        message = self._format_approval_request(discovery, approval_id)

        # Send to user via Hermes
        self.messenger.send_message(message)

    def _format_approval_request(self, discovery: DiscoveryRecord, approval_id: str) -> str:
        """
        Format Telegram message requesting project approval
        """
        confidence_emoji = "🟢" if discovery.confidence_score >= 0.80 else "🟡"

        return f"""
{confidence_emoji} **Project Approval Request**

**Title**: {discovery.title}
**Description**: {discovery.description}

**Confidence**: {discovery.confidence_score:.0%}
**Clusters**: {len(discovery.cluster_ids)} clusters analyzed
**Sources**: {', '.join(discovery.metadata.get('sources', [])[:3])}...

**This will be written to The Ananke (SQL) as a tracked project.**

Approve?
`/approve_project {approval_id}`
`/reject_project {approval_id}`
`/view_project {approval_id}` (see full details)
"""

    def approve_project(self, approval_id: str) -> bool:
        """
        User approved via Telegram - write to SQL
        """
        if approval_id not in self.pending_approvals:
            raise ValueError(f"Approval {approval_id} not found")

        approval = self.pending_approvals[approval_id]
        discovery = approval['discovery']

        try:
            # Write to The Ananke (SQL)
            project_id = self._write_to_sql(discovery)

            # Mark discovery as converted to project
            self._update_discovery_status(discovery.id, converted=True)

            # Log approval
            self._log_approval(approval_id, approved=True, project_id=project_id)

            # Remove from pending
            del self.pending_approvals[approval_id]

            # Notify user
            self.messenger.send_message(
                f"✅ Project '{discovery.title}' written to The Ananke.\n"
                f"Project ID: {project_id}\n"
                f"Status: candidate → Monitor will track it."
            )

            return True

        except Exception as e:
            log_error(f"Failed to write project: {e}")
            self.messenger.send_message(
                f"❌ Failed to write project: {e}\n"
                f"This has been logged for retry."
            )
            return False

    def _write_to_sql(self, discovery: DiscoveryRecord) -> int:
        """
        ONLY place SQL writes can happen
        """
        cursor = self.db.cursor()

        cursor.execute("""
            INSERT INTO projects (
                title,
                description,
                discovered_by,
                discovery_id,
                cluster_ids,
                confidence_score,
                verified_by_user,
                verified_at,
                status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            discovery.title,
            discovery.description,
            'latent_scout',
            discovery.id,
            discovery.cluster_ids,
            discovery.confidence_score,
            True,  # User just approved it
            datetime.now(),
            'candidate'
        ))

        project_id = cursor.fetchone()[0]
        self.db.commit()

        return project_id

    def reject_project(self, approval_id: str):
        """
        User rejected - don't write to SQL
        """
        if approval_id not in self.pending_approvals:
            raise ValueError(f"Approval {approval_id} not found")

        approval = self.pending_approvals[approval_id]
        discovery = approval['discovery']

        # Log rejection
        self._log_approval(approval_id, approved=False)

        # Update discovery (mark as reviewed but rejected)
        self._update_discovery_status(discovery.id, rejected=True)

        # Remove from pending
        del self.pending_approvals[approval_id]

        # Notify user
        self.messenger.send_message(
            f"✅ Rejected project '{discovery.title}'.\n"
            f"It will remain in the Discovery Feed but won't be tracked."
        )

    def _log_approval(self, approval_id: str, approved: bool, project_id: int = None):
        """
        Audit trail for all gatekeeper decisions
        """
        cursor = self.db.cursor()

        cursor.execute("""
            INSERT INTO gatekeeper_audit (
                approval_id,
                approved,
                project_id,
                decided_at
            ) VALUES (%s, %s, %s, %s)
        """, (
            approval_id,
            approved,
            project_id,
            datetime.now()
        ))

        self.db.commit()
```

### Hermes Integration (Telegram Commands)

```python
# In Hermes bot

@hermes_bot.command("approve_project")
def cmd_approve_project(message, approval_id: str):
    """
    Approve a project write to SQL
    """
    try:
        success = sql_gatekeeper.approve_project(approval_id)
        # Success message sent by gatekeeper
    except Exception as e:
        bot.send_message(
            chat_id=message.chat.id,
            text=f"❌ Error approving project: {e}"
        )

@hermes_bot.command("reject_project")
def cmd_reject_project(message, approval_id: str):
    """
    Reject a project write to SQL
    """
    try:
        sql_gatekeeper.reject_project(approval_id)
        # Rejection message sent by gatekeeper
    except Exception as e:
        bot.send_message(
            chat_id=message.chat.id,
            text=f"❌ Error rejecting project: {e}"
        )

@hermes_bot.command("view_project")
def cmd_view_project(message, approval_id: str):
    """
    View full details before approving
    """
    approval = sql_gatekeeper.get_pending_approval(approval_id)

    if not approval:
        return "Approval request not found."

    discovery = approval['discovery']

    # Show full cluster details
    clusters = [get_cluster(cid) for cid in discovery.cluster_ids]

    detail_message = f"""
📊 **Project Proposal Details**

**Title**: {discovery.title}
**Description**: {discovery.description}

**Confidence**: {discovery.confidence_score:.0%}

**Clusters Analyzed**:
"""

    for cluster in clusters:
        detail_message += f"""
• {cluster.profile.theme_summary}
  Notes: {cluster.note_count}
  Tags: {', '.join(cluster.profile.tags[:3])}

"""

    detail_message += f"""
**Evidence Notes**:
{format_evidence_notes(discovery.metadata.get('evidence', []))}

**Actions**:
`/approve_project {approval_id}`
`/reject_project {approval_id}`
"""

    bot.send_message(
        chat_id=message.chat.id,
        text=detail_message,
        parse_mode='Markdown'
    )

@hermes_bot.command("pending_projects")
def cmd_pending_projects(message):
    """
    List all pending project approvals
    """
    pending = sql_gatekeeper.get_all_pending()

    if not pending:
        return "No pending project approvals."

    response = "📋 **Pending Project Approvals**\n\n"

    for approval_id, approval in pending.items():
        discovery = approval['discovery']
        age = datetime.now() - approval['requested_at']

        response += f"""
{discovery.title}
Confidence: {discovery.confidence_score:.0%}
Requested: {format_time_ago(approval['requested_at'])}
`/view_project {approval_id}`

"""

    bot.send_message(
        chat_id=message.chat.id,
        text=response,
        parse_mode='Markdown'
    )
```

### Rollback Capability

```python
@hermes_bot.command("remove_project")
def cmd_remove_project(message, project_id: int):
    """
    Remove a project from SQL (rollback)
    """
    # Only allow removal of projects created in last 7 days
    project = sql_gatekeeper.get_project(project_id)

    if not project:
        return f"Project {project_id} not found."

    age_days = (datetime.now() - project.created_at).days

    if age_days > 7:
        return f"⚠️ Cannot remove project older than 7 days (age: {age_days} days). Manual SQL required."

    # Confirmation required
    confirmation_code = generate_confirmation_code()

    bot.send_message(
        chat_id=message.chat.id,
        text=f"""
⚠️ **Remove Project?**

Title: {project.title}
Created: {format_datetime(project.created_at)}
Status: {project.status}

This will DELETE the project from The Ananke (SQL).

To confirm, reply with: `/confirm_remove {project_id} {confirmation_code}`
"""
    )

@hermes_bot.command("confirm_remove")
def cmd_confirm_remove(message, project_id: int, code: str):
    """
    Confirmed project removal
    """
    if not verify_confirmation_code(code):
        return "❌ Invalid confirmation code."

    sql_gatekeeper.remove_project(project_id)

    bot.send_message(
        chat_id=message.chat.id,
        text=f"✅ Project {project_id} removed from The Ananke."
    )
```

### Confidence Threshold Configuration

```python
# Environment variables or config
CONFIDENCE_THRESHOLDS = {
    'auto_reject': 0.60,      # Below this: don't even ask
    'require_approval': 0.80,  # Above this: still ask, but flag as high confidence
    'suggestion_only': 0.60    # Between 0.60-0.80: normal approval flow
}

# Allow user to adjust thresholds
@hermes_bot.command("set_confidence")
def cmd_set_confidence(message, threshold_type: str, value: float):
    """
    Adjust confidence thresholds
    Usage: /set_confidence require_approval 0.85
    """
    if threshold_type not in CONFIDENCE_THRESHOLDS:
        return f"Unknown threshold type. Options: {', '.join(CONFIDENCE_THRESHOLDS.keys())}"

    if not 0 <= value <= 1:
        return "Threshold must be between 0 and 1."

    CONFIDENCE_THRESHOLDS[threshold_type] = value
    save_config(CONFIDENCE_THRESHOLDS)

    bot.send_message(
        chat_id=message.chat.id,
        text=f"✅ Updated {threshold_type} threshold to {value:.0%}"
    )
```

### Integration with Story 010 (Autonomous Pattern Detection)

```python
# In Story 010's final node
@langgraph_node
def notify_via_hermes_node(state: LatentScoutState) -> LatentScoutState:
    """
    Final node in scout graph - sends notifications AND requests SQL writes
    """
    # ... (existing notification logic)

    # NEW: Request SQL writes for high-confidence project candidates
    project_candidates = [
        d for d in state.patterns_detected.get('project_candidate', [])
        if d.confidence_score >= 0.60
    ]

    for candidate in project_candidates:
        sql_gatekeeper.request_project_write(candidate)

    return state
```

### Audit Log Schema

```sql
CREATE TABLE gatekeeper_audit (
    id SERIAL PRIMARY KEY,
    approval_id TEXT NOT NULL,
    approved BOOLEAN NOT NULL,
    project_id INTEGER REFERENCES projects(id),
    decided_at TIMESTAMP DEFAULT NOW(),
    decided_by TEXT DEFAULT 'telegram_user'  -- Future: multi-user support
);

CREATE INDEX idx_gatekeeper_audit_approval ON gatekeeper_audit(approval_id);
CREATE INDEX idx_gatekeeper_audit_project ON gatekeeper_audit(project_id);
```

### Dependencies
- Story 010: Autonomous Pattern Detection (generates project candidates)
- Story 012: Proactive Insight Notifications (sends approval requests)
- Hermes: Telegram bot for approval commands
- Alexandria: The Ananke (PostgreSQL)
- project_crystal SQL Gatekeeper concept

## Affected Components
- **Argus**: Latent Scout calls gatekeeper before SQL writes
- **Alexandria**: The Ananke (PostgreSQL projects table)
- **Hermes**: Telegram approval workflow

## Priority
**Critical** - No SQL writes should happen without this gatekeeper

## Estimate
8 story points (5-8 days)

## Linear Labels
`phase-4`, `latent-scout`, `gatekeeper`, `sql`, `alexandria`, `hermes`, `safety`

## Related Stories
- Story 025: Shadow Copy & Hygiene (Obsidian Gatekeeper)
- Story 010: Autonomous Pattern Detection (generates candidates)
- Story 012: Proactive Insight Notifications (approval workflow)
- Story 013: Discovery Feed Management (alternative review path)

## Future Enhancements
- Multi-user approval (team projects)
- Approval workflows (require 2+ approvals)
- Scheduled approvals (auto-approve at specific times)
- Confidence calibration (learn from user accept/reject patterns)
- Batch approval: "approve all above 85%"
