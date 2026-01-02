# Story 014: SQL Project Gatekeeper (The Gates)

**As a** user
**I want** strict control over what gets written to my SQL project database
**So that** only verified, high-confidence projects become hard commitments in The Ananke

## 🎯 Architectural Role

**This story implements the SQL Project Gatekeeper (part of The Gates approval layer).**

The SQL Gatekeeper is one of two gatekeepers in The Gates layer (along with the Obsidian Gatekeeper from Story 025). It controls ALL writes to The Ananke, ensuring projects only become commitments after your explicit approval.

## Acceptance Criteria
- [ ] No direct writes to The Ananke `projects` table without gatekeeper approval
- [ ] Gatekeeper consumes proposal records from the Monitor Agent queue (SQLite)
- [ ] High-confidence proposals can be auto-approved (configurable; default threshold is very high)
- [ ] Other proposals require explicit approval via gatekeeper CLI/API
- [ ] Low-confidence proposals are rejected and marked `rejected` in the queue (no escalation here)
- [ ] SQL write only happens AFTER gatekeeper approval
- [ ] Rejections are recorded in the audit log; escalation is handled by the Monitor Agent
- [ ] Failed writes logged and retryable
- [ ] Audit trail: all approved/rejected project writes
- [ ] Rollback capability (CLI/API) with a time window and confirmation token
- [ ] Prevent duplicate inserts by enforcing unique `discovery_id` in SQL

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
CREATE UNIQUE INDEX idx_projects_discovery_id ON projects(discovery_id);
```

### SQL Gatekeeper Class

```python
class SQLProjectGatekeeper:
    """
    Controls ALL writes to The Ananke projects table
    Based on project_crystal gatekeeper concept
    """
    def __init__(self, db_conn, outbox, proposal_queue):
        self.db = db_conn
        self.outbox = outbox  # Message outbox (Story 027)
        self.proposal_queue = proposal_queue
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

        # 2. High confidence: auto-approve
        if discovery.confidence_score >= 0.80:
            return self._request_approval(discovery, auto_approve=True)

        # 3. Medium confidence: require explicit confirmation
        if discovery.confidence_score >= 0.60:
            return self._request_approval(discovery, auto_approve=False)

    def _request_approval(self, discovery: DiscoveryRecord, auto_approve: bool = False):
        """
        Queue an approval request in the outbox
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

        # Enqueue for delivery via Message Outbox
        self.outbox.enqueue(message)

    def _format_approval_request(self, discovery: DiscoveryRecord, approval_id: str) -> str:
        """
        Format approval message for the outbox
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
        External approval received - write to SQL
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
            self.outbox.enqueue(
                f"✅ Project '{discovery.title}' written to The Ananke.\n"
                f"Project ID: {project_id}\n"
                f"Status: candidate → Monitor will track it."
            )

            return True

        except Exception as e:
            log_error(f"Failed to write project: {e}")
            self.outbox.enqueue(
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

        # Update proposal queue (Monitor Agent handles escalation)
        self.proposal_queue.update_status(discovery.discovery_id, "rejected")

        # Remove from pending
        del self.pending_approvals[approval_id]

        # Notify user
        self.outbox.enqueue(
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

### Gatekeeper Queue (SQLite)

The gatekeeper reads proposals from a local SQLite queue created by the Monitor Agent.
Decisions are written back to SQLite (approved/rejected/awaiting_approval) and only
approved records are written to The Ananke. Rejection escalation is handled by the
Monitor Agent.

### Rollback Capability (CLI/API)

```python
def remove_project(project_id: int) -> str:
    """
    Remove a project from SQL (rollback) with a confirmation token.
    """
    project = sql_gatekeeper.get_project(project_id)
    if not project:
        raise ValueError(f"Project {project_id} not found")

    age_days = (datetime.now() - project.created_at).days
    if age_days > 7:
        raise ValueError("Project too old for automated removal")

    confirmation_code = generate_confirmation_code()
    sql_gatekeeper.store_removal_request(project_id, confirmation_code)
    return confirmation_code

def confirm_remove(project_id: int, code: str) -> None:
    """
    Confirmed project removal.
    """
    if not verify_confirmation_code(code):
        raise ValueError("Invalid confirmation code")
    sql_gatekeeper.remove_project(project_id)
```

### Confidence Threshold Configuration

```python
# Environment variables or config
CONFIDENCE_THRESHOLDS = {
    'auto_reject': 0.60,      # Below this: don't even ask
    'auto_approve': 0.90,     # Very high confidence auto-approves (configurable)
    'require_approval': 0.60  # Between 0.60-0.89: approval required
}
```

### Integration with Story 010 (Autonomous Pattern Detection)

```python
# The Scout writes project_candidate discoveries to Weaviate.
# The Monitor Agent (Story 015) turns those into proposals in SQLite.
# The Gatekeeper reads proposals and applies thresholds before SQL writes.
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
- Story 010: Autonomous Pattern Detection (generates discoveries)
- Story 015: Monitor Agent (creates proposal queue in SQLite)
- Story 027: Message Outbox Relay (optional escalation channel)
- Alexandria: The Ananke (PostgreSQL)
- project_crystal SQL Gatekeeper concept

## Affected Components
- **Argus**: Gatekeeper applies policy before SQL writes
- **Alexandria**: Proposal queue + audit state in SQLite
- **Alexandria**: The Ananke (PostgreSQL projects table)
- **Hermes**: Optional, consumes outbox later

## Priority
**Critical** - No SQL writes should happen without this gatekeeper

## Estimate
8 story points (5-8 days)

## Linear Labels
`phase-4`, `latent-scout`, `gatekeeper`, `sql`, `alexandria`, `safety`

## Related Stories
- Story 025: Shadow Copy & Hygiene (Obsidian Gatekeeper)
- Story 010: Autonomous Pattern Detection (generates candidates)
- Story 012: Proactive Insight Notifications (later delivery layer)
- Story 013: Discovery Feed Management (alternative review path)

## Future Enhancements
- Multi-user approval (team projects)
- Approval workflows (require 2+ approvals)
- Scheduled approvals (auto-approve at specific times)
- Confidence calibration (learn from user accept/reject patterns)
- Batch approval: "approve all above 85%"
