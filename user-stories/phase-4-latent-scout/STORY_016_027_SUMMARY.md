# Stories 016 & 027: Implementation Summary

**Feature Branch**: `feature/016-027-project-manager-outbox`

**Status**: Ready for implementation

---

## Overview

This feature branch combines three interconnected changes to enable intelligent, incremental project management with bidirectional Obsidian sync:

1. **Story 027**: Message Outbox Relay - Transport-agnostic messaging with response routing
2. **Story 016**: Project Manager Agent - Incremental enrichment with natural PM behavior
3. **Change Request to Story 014**: SQL Gatekeeper direct user updates

---

## What Gets Built

### 1. Message Outbox (Story 027)

**Purpose**: Decouple agent communication from Telegram, enable interactive questions with response routing.

**Key Features**:
- SQLite-based message queue
- Producer API for agents to enqueue messages
- Consumer API for Hermes to deliver to Telegram
- Response routing back to originating agent
- State management: `pending` → `awaiting_response` → `delivered` (or `failed`)
- Retry logic with exponential backoff (max 3 attempts)
- CLI commands for inspection and manual requeue

**Files**:
- `src/mnemosyne/alexandria/message_outbox.py`
- `src/mnemosyne/alexandria/migrations/027_create_message_outbox.sql`
- `src/mnemosyne/hermes/telegram/commands/outbox_consumer.py`
- `src/mnemosyne/cli/commands/outbox.py`

---

### 2. Project Manager Agent (Story 016)

**Purpose**: Transform The Ananke from static database into active project management system with incremental enrichment and bidirectional Obsidian sync.

**Key Features**:

#### Incremental Enrichment Strategy
- Stage 1: Accept from Gatekeeper (`title, description, discovered_by, discovery_id, cluster_ids, confidence_score, status='candidate'`)
- Stage 2: Request `importance` (1-5 scale) - user-only metadata
- Stage 3: Request `urgency` (1-5 scale) - user-only metadata
- Stage 4: Focus on high-priority (importance+urgency >= 7)
- Stage 5: Request `deadline` for high-priority active projects
- Stage 6: Enrich `description` if Scout-generated is too vague
- Stage 7: Calculate `pressure_score` (Work ÷ Time)

#### Natural PM Communication
- **Event-driven**: User responds → Ask next question within seconds
- **Natural follow-up rhythm**: Varies by importance (high: 2-3h, medium: 8h, low: 24h)
- **Anti-spam throttling**: Max 3 messages/hour
- **Back off gracefully**: After 3+ unanswered questions
- **Stop asking**: After 5 unanswered questions → mark as "user_avoiding"
- **No fixed schedules**: Only event-driven and natural follow-ups

#### Bidirectional Obsidian Sync
- SQL → Obsidian: Every 15 minutes for changed projects
- Obsidian → SQL: FileSystemWatcher detects changes immediately
- YAML frontmatter contains all SQL metadata
- User can work in EITHER Obsidian OR Telegram
- Both pathways use SQL Gatekeeper for consistency

#### Pressure Score Calculation
- `pressure_score = (work_estimate / time_remaining_hours) × importance × urgency`
- Calculated hourly for projects with deadlines
- Overdue projects get pressure = 999.0

**Files**:
- `src/mnemosyne/argus/project_manager/agent.py`
- `src/mnemosyne/argus/project_manager/enrichment.py`
- `src/mnemosyne/argus/project_manager/natural_pm.py`
- `src/mnemosyne/argus/project_manager/pressure.py`
- `src/mnemosyne/aletheia/obsidian_sync/project_sync.py`
- `src/mnemosyne/aletheia/obsidian_sync/file_watcher.py`
- `src/mnemosyne/hermes/telegram/commands/project_commands.py`
- `src/mnemosyne/alexandria/migrations/016_extend_projects_schema.sql`

---

### 3. SQL Gatekeeper Enhancement (Change Request to Story 014)

**Purpose**: Enable user-initiated updates to bypass approval queue while maintaining audit trail.

**Key Features**:
- New method: `update_project_direct(project_id, updates, user_initiated=True)`
- Whitelist validation (only: importance, urgency, deadline, description, status, work_estimate)
- Cannot modify protected fields (title, discovered_by, discovery_id, cluster_ids, confidence_score)
- All updates logged to `gatekeeper_audit` with `action_type='direct_update'`
- Requires `user_initiated=True` flag (safety check)

**Files**:
- `src/mnemosyne/argus/gatekeeper/sql_gatekeeper.py` (updated)
- `src/mnemosyne/alexandria/migrations/014_enhance_gatekeeper_audit.sql`

---

## Three Update Pathways to SQL

All pathways go through SQL Gatekeeper for consistency and audit trail:

### 1. Scout → Gatekeeper → SQL (Existing - Story 014)
```
Monitor Agent creates proposal
    ↓
Gatekeeper requests approval via Message Outbox
    ↓
User approves via /approve_project <approval_id>
    ↓
Gatekeeper writes to SQL with: title, description, discovered_by, discovery_id,
                                 cluster_ids, confidence_score, status='candidate'
```

### 2. User → Telegram → Gatekeeper → SQL (NEW - Story 016)
```
User responds: /importance 42 5
    ↓
Telegram handler parses: project_id=42, importance=5
    ↓
Gatekeeper: update_project_direct(42, {'importance': 5}, user_initiated=True)
    ↓
Obsidian sync triggered immediately
    ↓
Project Manager asks next question (event-driven)
```

### 3. User → Obsidian → Gatekeeper → SQL (NEW - Story 016)
```
User edits project markdown file in Obsidian
    ↓
FileSystemWatcher detects change
    ↓
Parse YAML frontmatter
    ↓
Gatekeeper: update_project_direct(42, updates, user_initiated=True)
    ↓
SQL updated (silent sync, no Project Manager interaction)
```

---

## Schema Changes

### Extended Projects Table (Story 016)
```sql
ALTER TABLE projects ADD COLUMN importance INTEGER CHECK (importance >= 1 AND importance <= 5);
ALTER TABLE projects ADD COLUMN urgency INTEGER CHECK (urgency >= 1 AND urgency <= 5);
ALTER TABLE projects ADD COLUMN work_estimate INTEGER;
ALTER TABLE projects ADD COLUMN obsidian_file_path TEXT;
ALTER TABLE projects ADD COLUMN last_synced_to_obsidian TIMESTAMP;
ALTER TABLE projects ADD COLUMN last_synced_from_obsidian TIMESTAMP;

CREATE INDEX idx_projects_priority ON projects(importance, urgency);
```

### Enhanced Gatekeeper Audit (Change Request)
```sql
ALTER TABLE gatekeeper_audit ADD COLUMN action_type TEXT DEFAULT 'approval';
-- Values: 'approval', 'rejection', 'direct_update'

ALTER TABLE gatekeeper_audit ADD COLUMN updates_json TEXT;
-- For direct updates: {'importance': 5, 'urgency': 4}

ALTER TABLE gatekeeper_audit ADD COLUMN user_initiated BOOLEAN DEFAULT FALSE;

CREATE INDEX idx_gatekeeper_audit_action ON gatekeeper_audit(action_type);
```

### Message Outbox Table (Story 027)
```sql
CREATE TABLE message_outbox (
    id INTEGER PRIMARY KEY,
    message_id TEXT NOT NULL UNIQUE,
    message_type TEXT NOT NULL,
    originating_agent TEXT,
    context_id TEXT,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    expects_response BOOLEAN DEFAULT FALSE,
    response_received_at TIMESTAMP,
    response_json TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_attempted_at TIMESTAMP,
    delivered_at TIMESTAMP
);

CREATE INDEX idx_outbox_status ON message_outbox(status);
CREATE INDEX idx_outbox_type ON message_outbox(message_type);
CREATE INDEX idx_outbox_agent ON message_outbox(originating_agent);
CREATE INDEX idx_outbox_context ON message_outbox(context_id);
```

---

## User Experience

### New Telegram Commands

#### Project Metadata
- `/importance <project_id> <1-5>` - Set project importance
- `/urgency <project_id> <1-5>` - Set project urgency
- `/deadline <project_id> <date/duration>` - Set deadline (e.g., `7d`, `2w`, `2024-12-31`)
- `/describe <project_id> <text>` - Update project description

#### Project Views
- `/projects [status]` - List projects sorted by priority (default: active)
- `/view <project_id>` - View full project details
- `/complete <project_id>` - Mark project as completed

#### Message Outbox
- `/mcp outbox status` - Show pending/delivered/failed message counts
- `/mcp outbox inspect <message_id>` - View message details
- `/mcp outbox requeue <message_id>` - Retry failed message

---

## Example User Flow

### Day 1: Project Approved
```
09:15 Scout discovers pattern
09:30 Monitor creates proposal
09:45 Gatekeeper sends approval request
10:00 USER: /approve_project abc-123
10:01 PROJECT MANAGER: "Quick question about 'Build auth system': how important is this? (1-5)"
10:05 USER: /importance 42 5
10:05 PROJECT MANAGER: "Got it. How urgent? (1-5)"  [IMMEDIATE - event-driven]
10:10 USER: /urgency 42 4
10:10 PROJECT MANAGER: "When should 'Build auth system' be done?"  [IMMEDIATE - event-driven]
10:15 USER: /deadline 42 2w
10:15 ✅ Project enriched, synced to Obsidian
```

### Day 2: User Edits in Obsidian
```
14:30 User opens Projects/Build auth system.md in Obsidian
14:35 User edits YAML frontmatter: importance: 5 (changed from 4)
14:35 FileSystemWatcher detects change → syncs to SQL
14:35 SQL updated via Gatekeeper (user_initiated=True)
14:35 ✅ Change logged in audit trail
```

### Day 3: Natural Follow-up
```
08:00 [Background check cycle runs every 30 minutes]
08:00 PROJECT MANAGER checks: 3 projects need attention
08:01 PROJECT MANAGER: "Hey, still need deadline for 'Refactor API' when you get a chance"
      [Gentle reminder - last asked 8 hours ago, medium importance]
```

### Day 14: Deadline Approaching
```
10:00 [Deadline in 18 hours for high-priority project]
10:00 PROJECT MANAGER: "🔥 'Build auth system' due in 18h - are you on track?"
12:00 [No response after 2 hours - high importance = 2-hour follow-up]
12:00 PROJECT MANAGER: "Following up on 'Build auth system' - deadline approaching!"
```

---

## Scheduled Jobs

### APScheduler Configuration
```python
# Main PM check cycle - runs every 30 minutes
scheduler.add_job(project_manager.run_pm_check_cycle, 'interval', minutes=30)

# Update pressure scores every hour
scheduler.add_job(project_manager.update_all_pressure_scores, 'interval', hours=1)

# Sync to Obsidian every 15 minutes
scheduler.add_job(project_manager.sync_changed_projects, 'interval', minutes=15)

# Outbox consumer - poll pending messages every 30 seconds
scheduler.add_job(outbox_consumer.process_pending, 'interval', seconds=30)
```

---

## Success Metrics

### Story 027 Success
- [ ] Messages successfully delivered to Telegram
- [ ] Failures retry with backoff (max 3 attempts)
- [ ] User responses route back to originating agent
- [ ] Interactive questions transition to `awaiting_response`
- [ ] CLI commands work for inspection and requeue

### Story 016 Success
- [ ] Projects incrementally enriched (importance → urgency → deadline)
- [ ] Event-driven: User responds → Next question within seconds
- [ ] Natural PM rhythm: Follow-ups based on importance, not fixed quotas
- [ ] Bidirectional sync: SQL ↔ Obsidian stay consistent
- [ ] Monitor doesn't rediscover existing projects (via `discovery_id`)
- [ ] Telegram commands update SQL via Gatekeeper and sync to Obsidian
- [ ] Scheduled jobs run without errors

### Gatekeeper Update Success
- [ ] `update_project_direct()` validates whitelist
- [ ] Direct updates logged in audit trail
- [ ] User-initiated updates bypass approval queue
- [ ] Protected fields cannot be modified

---

## Testing Strategy

### Unit Tests
- Message Outbox producer/consumer API
- Project Manager enrichment queue logic
- Natural PM timing calculations
- Pressure score calculation
- SQL Gatekeeper direct update validation
- Obsidian sync (SQL → Obsidian, Obsidian → SQL)

### Integration Tests
- End-to-end: Scout → Monitor → Gatekeeper → Project Manager → Obsidian
- Incremental enrichment flow (importance → urgency → deadline)
- Bidirectional Obsidian sync (both directions)
- Event-driven next question after user response
- Natural PM rhythm (follow-ups, reminders, back-off)
- Duplicate project prevention (discovery_id matching)
- Message delivery with retry logic
- Response routing back to originating agent

### Manual Testing Checklist
- [ ] Create new project from Scout discovery
- [ ] Respond to importance/urgency questions via Telegram
- [ ] Edit project in Obsidian, verify sync to SQL
- [ ] Verify SQL changes sync to Obsidian
- [ ] Verify event-driven next question after user response
- [ ] Verify natural follow-up timing
- [ ] Verify anti-spam throttling (max 3 messages/hour)
- [ ] Verify back-off after 3+ unanswered questions
- [ ] Verify critical deadline alerts (deadline <24h)
- [ ] Verify pressure score calculation
- [ ] Verify duplicate project prevention (Scout rediscovery)

---

## Risk Mitigation

### Risk 1: File Sync Conflicts (SQL ↔ Obsidian)
**Mitigation**:
- Use timestamps (`last_synced_to_obsidian`, `last_synced_from_obsidian`)
- Obsidian → SQL has priority (user is editing manually)
- SQL → Obsidian only syncs if `updated_at > last_synced_to_obsidian`
- Log all sync conflicts for manual review

### Risk 2: Overwhelming User with Messages
**Mitigation**:
- Natural PM rhythm with throttling (max 3 messages/hour)
- Back off after 3+ unanswered questions
- Stop asking after 5 unanswered questions for same project
- Importance-based follow-up timing

### Risk 3: Duplicate Projects from Scout Rediscovery
**Mitigation**:
- Monitor Agent checks `discovery_id` existence in SQL
- Unique constraint on `projects.discovery_id`
- Log all skipped duplicates

### Risk 4: Message Outbox Delivery Failures
**Mitigation**:
- Retry with exponential backoff (3 max attempts)
- Mark as `failed` after 3 attempts
- CLI command to manually requeue failed messages
- Alert user via Telegram if critical message fails

---

## Rollback Plan

If critical issues arise:

1. **Revert SQL Schema Changes**:
   - Run rollback migrations for `projects` table extensions
   - Run rollback migrations for `gatekeeper_audit` changes

2. **Disable Project Manager Agent**:
   - Comment out APScheduler jobs
   - Keep Message Outbox operational for other agents

3. **Disable Obsidian Sync**:
   - Stop FileSystemWatcher
   - SQL → Obsidian sync can remain (read-only for user)

4. **Preserve Audit Trail**:
   - All gatekeeper decisions remain in audit log
   - Can reconstruct state from audit history

---

## Next Steps

1. **Create Feature Branch**: `feature/016-027-project-manager-outbox`
2. **Implement Phase 1**: Message Outbox (Story 027) - 4.5 days
3. **Implement Phase 2**: SQL Gatekeeper Enhancement - 2 days
4. **Implement Phase 3**: Ananke Schema Extension - 1 day
5. **Implement Phase 4**: Obsidian Sync Layer - 4.5 days
6. **Implement Phase 5**: Project Manager Agent - 8.5 days
7. **Implement Phase 6**: Telegram Commands - 3 days
8. **Implement Phase 7**: Scheduled Jobs - 1 day
9. **Implement Phase 8**: Testing & Documentation - 3 days
10. **Create Pull Request** to `main` with comprehensive test coverage

**Total Estimated Duration**: 20-28 days

---

## Related Documentation

- [Implementation Plan](./STORY_016_027_IMPLEMENTATION_PLAN.md) - Detailed implementation sequence
- [Story 016: Project Manager Agent](./story-016-project-manager-agent.md) - Full specification
- [Story 027: Message Outbox Relay](./story-027-message-outbox-relay.md) - Full specification
- [Story 014: SQL Project Gatekeeper](./story-014-sql-project-gatekeeper.md) - Gatekeeper specification
- [SYSTEM_ARCHITECTURE.md](../SYSTEM_ARCHITECTURE.md) - Overall system architecture
- [project_crystal README](../../project_crystal/README.md) - Crystal philosophy

---

**Status**: ✅ Ready for implementation

**Acceptance Criteria**: Finalized and excellent

**Feature Branch**: `feature/016-027-project-manager-outbox`

**Estimated Completion**: 20-28 days from start
