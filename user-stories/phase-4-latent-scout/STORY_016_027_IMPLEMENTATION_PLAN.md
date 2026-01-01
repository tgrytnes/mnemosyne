# Implementation Plan: Stories 016 & 027 + Gatekeeper Update

**Feature Branch**: `feature/016-027-project-manager-outbox`

**Sprint Goal**: Implement Project Manager Agent with incremental enrichment, bidirectional Obsidian sync, and Message Outbox for interactive communication.

## Stories Included

- **Story 016**: Project Manager Agent (Strategist) - 13 story points
- **Story 027**: Message Outbox Relay (Nexus Middle-Man) - 5 story points
- **Change Request to Story 014**: SQL Gatekeeper direct user updates - 2 story points

**Total**: 20 story points (estimated 12-15 days)

---

## Dependencies

### Prerequisites (Must be complete)
- ✅ Story 014: SQL Project Gatekeeper (already implemented)
- ⏳ Story 015: Monitor Agent (creates proposal queue)
- The Ananke PostgreSQL schema (from project_crystal)
- Hermes Telegram bot infrastructure
- Obsidian vault access

### External Dependencies
- APScheduler library for background jobs
- Watchdog library (FileSystemWatcher) for Obsidian file monitoring
- PyYAML for frontmatter parsing
- SQLite for message outbox

---

## Implementation Sequence

### Phase 1: Message Outbox Foundation (Story 027)
**Priority**: Implement first, as Project Manager depends on it

1. **Create Message Outbox Database** (1 day)
   - Create SQLite database for outbox
   - Implement schema with tables: `message_outbox`
   - Add indexes for status, agent, context, and type
   - Create migration script

2. **Implement Producer API** (1 day)
   - `MessageOutbox.enqueue()` - Queue messages for delivery
   - `MessageOutbox.send_message()` - Simple text-only helper
   - Idempotency logic (message_id deduplication)
   - Unit tests for producer API

3. **Implement Consumer API** (1 day)
   - `MessageOutbox.fetch_pending()` - Get pending messages
   - `MessageOutbox.mark_delivered()` - Mark successful delivery
   - `MessageOutbox.mark_failed()` - Handle failures with retry
   - `MessageOutbox.record_response()` - Record user responses
   - Unit tests for consumer API

4. **Integrate with Hermes Telegram Bot** (1 day)
   - Background job to poll `fetch_pending()` every 30 seconds
   - Send messages to Telegram
   - Handle delivery failures with backoff
   - Route responses back to originating agent
   - Integration tests with mock Telegram API

5. **CLI Commands** (0.5 day)
   - `/mcp outbox status` - Show pending/delivered/failed counts
   - `/mcp outbox inspect <message_id>` - View message details
   - `/mcp outbox requeue <message_id>` - Retry failed message
   - `/mcp outbox clear` - Clear old delivered messages

**Story 027 Total**: ~4.5 days

---

### Phase 2: SQL Gatekeeper Enhancement (Change Request to Story 014)
**Priority**: Implement second, before Project Manager

1. **Add Direct Update Method** (1 day)
   - Implement `SQLProjectGatekeeper.update_project_direct()`
   - Whitelist validation (importance, urgency, deadline, description, status, work_estimate)
   - Field safety checks (cannot modify title, discovered_by, discovery_id, etc.)
   - Unit tests for direct updates

2. **Enhance Audit Schema** (0.5 day)
   - Add `action_type` field to `gatekeeper_audit` table ('approval', 'rejection', 'direct_update')
   - Add `updates_json` field for storing update payloads
   - Add `user_initiated` boolean field
   - Migration script for schema changes

3. **Logging and Audit** (0.5 day)
   - `_log_direct_update()` method
   - Ensure all direct updates are logged with timestamp
   - Add query methods to retrieve audit history

**Gatekeeper Update Total**: ~2 days

---

### Phase 3: Ananke Schema Extension (Story 016 - Part 1)
**Priority**: Must happen before Project Manager implementation

1. **Extend Projects Table** (0.5 day)
   - Add `importance INTEGER CHECK (importance >= 1 AND importance <= 5)`
   - Add `urgency INTEGER CHECK (urgency >= 1 AND urgency <= 5)`
   - Add `work_estimate INTEGER`
   - Add `obsidian_file_path TEXT`
   - Add `last_synced_to_obsidian TIMESTAMP`
   - Add `last_synced_from_obsidian TIMESTAMP`
   - Create index on `(importance, urgency)` for priority queries
   - Migration script

2. **Verify Discovery ID Uniqueness** (0.5 day)
   - Add unique constraint on `discovery_id` (if not exists)
   - Ensure idempotency for Monitor Agent writes

**Schema Extension Total**: ~1 day

---

### Phase 4: Obsidian Sync Layer (Story 016 - Part 2)
**Priority**: Core infrastructure for bidirectional sync

1. **Implement ObsidianProjectSync Class** (2 days)
   - `sync_project_to_obsidian()` - SQL → Obsidian markdown
   - YAML frontmatter generation with all SQL metadata
   - Filename sanitization (handle special characters)
   - Create `Projects/` folder in Obsidian vault
   - Unit tests with temp Obsidian vault

2. **Implement FileSystemWatcher** (1.5 days)
   - `ProjectFileHandler` using watchdog library
   - Monitor `Projects/` folder for file changes
   - Parse YAML frontmatter on file modification
   - `sync_obsidian_to_sql()` - Obsidian → SQL via Gatekeeper
   - Debouncing (avoid rapid-fire sync on auto-save)
   - Integration tests

3. **Prevent Duplicate Project Detection** (1 day)
   - Update Monitor Agent to check if `discovery_id` exists in SQL
   - Query: `SELECT id FROM projects WHERE discovery_id = ?`
   - If exists → Skip project creation (already tracked)
   - Add logging for skipped duplicates
   - Integration tests with Mock Monitor Agent

**Obsidian Sync Total**: ~4.5 days

---

### Phase 5: Project Manager Agent (Story 016 - Part 3)
**Priority**: Core agent logic

1. **Implement Incremental Enrichment Queue** (2 days)
   - `_build_enrichment_queue()` - Prioritize missing metadata
   - Stage 1: Request importance (1-5 scale)
   - Stage 2: Request urgency (1-5 scale)
   - Stage 3: Focus on high-priority projects (importance+urgency >= 7)
   - Stage 4: Request deadline for high-priority active projects
   - Stage 5: Enrich description if Scout-generated is too vague
   - Unit tests for queue prioritization logic

2. **Implement Question Handlers** (1.5 days)
   - `_request_importance()` - Format and enqueue question
   - `_request_urgency()` - Format and enqueue question
   - `_request_deadline()` - Format and enqueue question
   - `_request_description()` - Format and enqueue question
   - Use Message Outbox with `expects_response=True`
   - Unit tests for message formatting

3. **Implement Event-Driven Response Handler** (1 day)
   - `continue_enrichment(project_id)` - Ask next question immediately after user response
   - Determine next missing field from project state
   - Call appropriate `_request_*()` method
   - Integration tests with mock responses

4. **Implement Natural PM Check Cycle** (2 days)
   - `run_pm_check_cycle()` - Main "thinking" loop (every 30 minutes)
   - `_follow_up_on_unanswered_questions()` - Natural follow-up timing
   - `_get_critical_deadlines()` - Identify urgent items (deadline <24h)
   - `_handle_critical_deadline()` - Send urgent reminders
   - `_check_new_projects()` - New projects needing initial metadata
   - `_check_stalled_projects()` - High-priority projects stalled >7 days
   - `_send_opportunistic_nudge()` - Gentle nudges if not too many messages sent
   - `_messages_sent_last_hour()` - Anti-spam throttling
   - Unit tests for timing logic

5. **Implement Pressure Score Calculation** (1 day)
   - `_update_pressure_scores()` - Calculate Work ÷ Time
   - Time pressure calculation: `work_estimate / time_remaining_hours`
   - Priority factor: `importance × urgency`
   - Combined pressure score: `time_pressure × priority_factor`
   - Handle overdue projects (pressure = 999.0)
   - Scheduled job every hour
   - Unit tests

6. **Implement Reminder Handlers** (1 day)
   - `_send_gentle_reminder()` - Non-pushy follow-up
   - `_send_escalated_reminder()` - For high-priority items
   - `_send_final_reminder()` - Last attempt before backing off
   - `_mark_as_avoiding()` - User not responding after 5+ questions
   - `_stop_asking()` - Stop nudging low-priority items
   - Unit tests

**Project Manager Agent Total**: ~8.5 days

---

### Phase 6: Telegram Command Integration (Story 016 - Part 4)
**Priority**: User interface for Project Manager

1. **Implement Metadata Commands** (1.5 days)
   - `/importance <project_id> <1-5>` - Set importance
   - `/urgency <project_id> <1-5>` - Set urgency
   - `/deadline <project_id> <date/duration>` - Set deadline
   - `/describe <project_id> <text>` - Update description
   - All commands use `sql_gatekeeper.update_project_direct(user_initiated=True)`
   - All commands trigger `obsidian_sync.sync_project_to_obsidian()`
   - All commands call `project_manager.continue_enrichment()` for event-driven next question
   - Input validation and error handling

2. **Implement Project View Commands** (1 day)
   - `/projects [status]` - List projects sorted by priority
   - `/view <project_id>` - View full project details
   - `/complete <project_id>` - Mark project as completed
   - Format output with priority, deadline, pressure scores
   - Include Obsidian file path in output

3. **Response Routing** (0.5 day)
   - Record responses in Message Outbox using `record_response()`
   - Route to Project Manager using returned `originating_agent`
   - Integration tests

**Telegram Commands Total**: ~3 days

---

### Phase 7: Scheduled Job Integration (Story 016 - Part 5)
**Priority**: Background automation

1. **Setup APScheduler Jobs** (1 day)
   - Main PM check cycle - every 30 minutes
   - Pressure score updates - every hour
   - Obsidian sync - every 15 minutes
   - Graceful startup and shutdown
   - Error handling and logging
   - Integration tests

**Scheduled Jobs Total**: ~1 day

---

### Phase 8: Testing & Documentation
**Priority**: Quality assurance

1. **Integration Tests** (2 days)
   - End-to-end test: Scout → Monitor → Gatekeeper → Project Manager → Obsidian
   - Test incremental enrichment flow (importance → urgency → deadline)
   - Test bidirectional Obsidian sync (SQL ↔ Obsidian)
   - Test event-driven next question after user response
   - Test natural PM rhythm (follow-ups, reminders, back-off)
   - Test duplicate project prevention (discovery_id matching)

2. **Documentation** (1 day)
   - Update Argus README with Project Manager section
   - Document Message Outbox API for other agents
   - Document SQL Gatekeeper direct update API
   - Add examples for Telegram commands
   - Update architecture diagrams

**Testing & Docs Total**: ~3 days

---

## Total Estimated Duration

- **Story 027**: 4.5 days
- **Gatekeeper Update**: 2 days
- **Schema Extension**: 1 day
- **Obsidian Sync**: 4.5 days
- **Project Manager Agent**: 8.5 days
- **Telegram Commands**: 3 days
- **Scheduled Jobs**: 1 day
- **Testing & Docs**: 3 days

**Grand Total**: ~27.5 days (realistic with buffer)

**Optimistic**: 20 story points × 0.6 days/point = 12 days
**Realistic**: 20 story points × 1.0 days/point = 20 days
**Pessimistic**: 20 story points × 1.4 days/point = 28 days

---

## File Structure

```
src/mnemosyne/
├── alexandria/
│   ├── message_outbox.py          # Story 027 - Message Outbox
│   ├── migrations/
│   │   ├── 016_extend_projects_schema.sql
│   │   ├── 027_create_message_outbox.sql
│   │   └── 014_enhance_gatekeeper_audit.sql
│   └── tests/
│       └── test_message_outbox.py
│
├── argus/
│   ├── project_manager/
│   │   ├── __init__.py
│   │   ├── agent.py                # Story 016 - Project Manager Agent
│   │   ├── enrichment.py           # Incremental enrichment logic
│   │   ├── natural_pm.py           # Natural PM timing/rhythm
│   │   └── pressure.py             # Pressure score calculation
│   ├── gatekeeper/
│   │   └── sql_gatekeeper.py       # Updated with update_project_direct()
│   └── tests/
│       ├── test_project_manager.py
│       └── test_enrichment.py
│
├── aletheia/
│   ├── obsidian_sync/
│   │   ├── __init__.py
│   │   ├── project_sync.py         # Story 016 - Obsidian bidirectional sync
│   │   └── file_watcher.py         # FileSystemWatcher for Projects/
│   └── tests/
│       └── test_obsidian_sync.py
│
├── hermes/
│   ├── telegram/
│   │   ├── commands/
│   │   │   ├── project_commands.py  # /importance, /urgency, /deadline, etc.
│   │   │   └── outbox_consumer.py   # Background job to poll outbox
│   │   └── bot.py                   # Updated with new commands
│   └── tests/
│       └── test_telegram_commands.py
│
└── cli/
    └── commands/
        └── outbox.py                # CLI for outbox inspection
```

---

## Integration Points

### Three Update Pathways to SQL (All via Gatekeeper)

1. **Scout → Gatekeeper → SQL** (Story 014 existing flow)
   - Monitor Agent creates proposal in SQLite queue
   - Gatekeeper requests approval via Message Outbox
   - User approves via `/approve_project <approval_id>`
   - Gatekeeper writes to SQL with: `title, description, discovered_by, discovery_id, cluster_ids, confidence_score, status='candidate'`

2. **User → Telegram → Gatekeeper → SQL** (NEW - Story 016)
   - User responds to Project Manager questions via Telegram
   - Commands: `/importance`, `/urgency`, `/deadline`, `/describe`
   - Gatekeeper `update_project_direct(user_initiated=True)` updates SQL
   - Obsidian sync triggered immediately after
   - Project Manager asks next question (event-driven)

3. **User → Obsidian → Gatekeeper → SQL** (NEW - Story 016)
   - User edits project markdown file in Obsidian
   - FileSystemWatcher detects change
   - `sync_obsidian_to_sql()` parses frontmatter
   - Gatekeeper `update_project_direct(user_initiated=True)` updates SQL
   - No Project Manager interaction (silent sync)

### Message Outbox Response Routing

```
User Command: /importance 42 5
    ↓
Telegram Handler parses: project_id=42, importance=5
    ↓
SQL Gatekeeper: update_project_direct(42, {'importance': 5}, user_initiated=True)
    ↓
Message Outbox: record_response('project:42', {'field': 'importance', 'value': 5})
    ↓
Returns: originating_agent='project_manager'
    ↓
Hermes routes to: project_manager.continue_enrichment(42)
    ↓
Project Manager asks NEXT question: "How urgent is this? (1-5)"
```

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
- Importance-based follow-up timing (high importance: 2 hours, low: 24 hours)

### Risk 3: Duplicate Projects from Scout Rediscovery
**Mitigation**:
- Monitor Agent checks `discovery_id` existence in SQL before creating proposal
- Unique constraint on `projects.discovery_id`
- Log all skipped duplicates for audit

### Risk 4: Message Outbox Delivery Failures
**Mitigation**:
- Retry with exponential backoff (3 max attempts)
- Mark as `failed` after 3 attempts
- CLI command to manually requeue failed messages
- Alert user via Telegram if critical message fails

---

## Success Criteria

### Story 027 Success
- [ ] Message Outbox accepts messages from agents
- [ ] Hermes consumes outbox and delivers to Telegram
- [ ] Failures retry with backoff (max 3 attempts)
- [ ] User responses route back to originating agent
- [ ] Interactive questions transition to `awaiting_response` state
- [ ] CLI commands work for inspection and requeue

### Story 016 Success
- [ ] Project Manager incrementally enriches projects (importance → urgency → deadline)
- [ ] Event-driven: User responds → Next question within seconds
- [ ] Natural PM rhythm: Follow-ups based on importance, not fixed quotas
- [ ] Bidirectional Obsidian sync: SQL ↔ Obsidian stay consistent
- [ ] Monitor Agent doesn't rediscover existing projects (via `discovery_id`)
- [ ] Telegram commands update SQL via Gatekeeper and sync to Obsidian
- [ ] Scheduled jobs run without errors (30min check cycle, hourly pressure scores, 15min Obsidian sync)
- [ ] User can work in either Telegram OR Obsidian seamlessly

### Gatekeeper Update Success
- [ ] `update_project_direct()` method works with whitelist validation
- [ ] Direct updates logged in audit trail with `action_type='direct_update'`
- [ ] User-initiated updates bypass approval queue
- [ ] Cannot modify protected fields (title, discovered_by, discovery_id, etc.)

---

## Rollback Plan

If critical issues arise during implementation:

1. **Revert SQL Schema Changes**:
   - Run rollback migration for `projects` table extensions
   - Run rollback migration for `gatekeeper_audit` changes

2. **Disable Project Manager Agent**:
   - Comment out APScheduler jobs
   - Keep Message Outbox operational for other agents

3. **Disable Obsidian Sync**:
   - Stop FileSystemWatcher
   - SQL → Obsidian sync can remain (read-only for user)

4. **Preserve Audit Trail**:
   - All gatekeeper decisions and updates remain in audit log
   - Can reconstruct state from audit history

---

## Post-Implementation Tasks

1. **Performance Monitoring**:
   - Monitor Message Outbox delivery latency
   - Monitor Obsidian sync performance (file I/O)
   - Monitor SQL Gatekeeper query performance

2. **User Feedback Collection**:
   - Track user response rate to Project Manager questions
   - Monitor dismissal rate (how often users ignore questions)
   - Adjust timing parameters based on feedback

3. **Future Enhancements**:
   - Sub-tasks within projects (breakdown large projects)
   - Calendar integration (sync deadlines to Google Calendar)
   - Smart work estimates (learn typical project durations)
   - Context-aware nudges (adjust frequency based on user patterns)

---

## Change Request: Story 014 SQL Project Gatekeeper

### Summary
Add direct user update pathway to SQL Gatekeeper to support Project Manager incremental enrichment without approval queue.

### Motivation
When users provide metadata via Telegram commands or Obsidian edits, these changes should bypass the approval queue since they are user-initiated actions. The approval queue exists to prevent autonomous agents from polluting The Ananke, but user-provided data is inherently trusted.

### Changes Required

1. **New Method**: `update_project_direct()`
   - Accept `project_id`, `updates` dict, `user_initiated` flag
   - Whitelist validation (only allow: importance, urgency, deadline, description, status, work_estimate)
   - Cannot modify protected fields (title, discovered_by, discovery_id, cluster_ids, confidence_score)
   - Log all updates to audit trail with `action_type='direct_update'`

2. **Schema Change**: Extend `gatekeeper_audit` table
   - Add `action_type TEXT DEFAULT 'approval'` ('approval', 'rejection', 'direct_update')
   - Add `updates_json TEXT` (store update payloads for direct updates)
   - Add `user_initiated BOOLEAN DEFAULT FALSE`
   - Migration script to add new columns

3. **Audit Enhancement**:
   - `_log_direct_update()` method to record user-initiated changes
   - Include timestamp, project_id, updates payload, user_initiated flag

### Acceptance Criteria
- [ ] `update_project_direct()` validates whitelist of allowed fields
- [ ] Cannot update protected fields (raises ValueError)
- [ ] All direct updates logged to `gatekeeper_audit` table
- [ ] `user_initiated=True` flag required (safety check)
- [ ] Audit trail distinguishes between approvals and direct updates (`action_type`)
- [ ] Unit tests for direct update method
- [ ] Integration tests with Project Manager workflow

### Estimate
2 story points (1-2 days)

---

**End of Implementation Plan**
