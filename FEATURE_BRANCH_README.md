# Feature Branch: Story 016, 027 & CR-014-001

**Branch Name**: `feature/016-027-project-manager-outbox`

**Worktree Location**: `/home/tgrytnes/projects/Mnemosyne-story-016-027`

**Status**: Ready for implementation

---

## What This Branch Implements

This feature branch contains three interconnected components that enable intelligent, incremental project management with bidirectional Obsidian sync:

### 1. Story 027: Message Outbox Relay (5 story points)
- SQLite-based message queue for agent → user communication
- Response routing back to originating agents
- State management: `pending` → `awaiting_response` → `delivered`
- Retry logic with exponential backoff

**Files**:
- `src/mnemosyne/alexandria/message_outbox.py`
- `src/mnemosyne/hermes/telegram/commands/outbox_consumer.py`
- `src/mnemosyne/cli/commands/outbox.py`

### 2. CR-014-001: SQL Gatekeeper Direct User Updates (2 story points)
- Enhancement to Story 014 (SQL Project Gatekeeper)
- New method: `update_project_direct(project_id, updates, user_initiated=True)`
- Whitelist validation for allowed update fields
- Enhanced audit trail with `action_type`, `updates_json`, `user_initiated`

**Files**:
- `src/mnemosyne/argus/gatekeeper/sql_gatekeeper.py` (updated)
- `src/mnemosyne/alexandria/migrations/014_enhance_gatekeeper_audit.sql`

### 3. Story 016: Project Manager Agent (13 story points)
- Incremental enrichment strategy (importance → urgency → deadline)
- Natural PM communication (event-driven, no fixed quotas)
- Bidirectional Obsidian sync (SQL ↔ Obsidian markdown)
- Pressure score calculation (Work ÷ Time)

**Files**:
- `src/mnemosyne/argus/project_manager/` (new package)
- `src/mnemosyne/aletheia/obsidian_sync/` (new package)
- `src/mnemosyne/hermes/telegram/commands/project_commands.py`
- `src/mnemosyne/alexandria/migrations/016_extend_projects_schema.sql`

---

## Total Scope

- **Story Points**: 20 points
- **Estimated Duration**: 20-28 days
- **Components**: 3 (Story 027 + CR-014-001 + Story 016)

---

## Implementation Phases

1. **Phase 1**: Message Outbox Foundation (4.5 days)
2. **Phase 2**: SQL Gatekeeper Enhancement (2 days)
3. **Phase 3**: Ananke Schema Extension (1 day)
4. **Phase 4**: Obsidian Sync Layer (4.5 days)
5. **Phase 5**: Project Manager Agent (8.5 days)
6. **Phase 6**: Telegram Commands (3 days)
7. **Phase 7**: Scheduled Jobs (1 day)
8. **Phase 8**: Testing & Documentation (3 days)

**See**: [STORY_016_027_IMPLEMENTATION_PLAN.md](user-stories/phase-4-latent-scout/STORY_016_027_IMPLEMENTATION_PLAN.md)

---

## Key Integration Points

### Three Update Pathways to SQL (All via Gatekeeper)

1. **Scout → Gatekeeper → SQL** (Existing - Story 014)
   - Monitor Agent creates proposal
   - User approves via `/approve_project <approval_id>`
   - Gatekeeper writes with Scout metadata

2. **User → Telegram → Gatekeeper → SQL** (NEW - Story 016)
   - User commands: `/importance`, `/urgency`, `/deadline`
   - Gatekeeper `update_project_direct(user_initiated=True)`
   - Obsidian sync triggered
   - Project Manager asks next question (event-driven)

3. **User → Obsidian → Gatekeeper → SQL** (NEW - Story 016)
   - User edits project markdown file
   - FileSystemWatcher detects change
   - Gatekeeper `update_project_direct(user_initiated=True)`
   - Silent sync (no Project Manager interaction)

---

## Schema Changes

### Extended Projects Table
```sql
ALTER TABLE projects ADD COLUMN importance INTEGER CHECK (importance >= 1 AND importance <= 5);
ALTER TABLE projects ADD COLUMN urgency INTEGER CHECK (urgency >= 1 AND urgency <= 5);
ALTER TABLE projects ADD COLUMN work_estimate INTEGER;
ALTER TABLE projects ADD COLUMN obsidian_file_path TEXT;
ALTER TABLE projects ADD COLUMN last_synced_to_obsidian TIMESTAMP;
ALTER TABLE projects ADD COLUMN last_synced_from_obsidian TIMESTAMP;
```

### Enhanced Gatekeeper Audit
```sql
ALTER TABLE gatekeeper_audit ADD COLUMN action_type TEXT DEFAULT 'approval';
ALTER TABLE gatekeeper_audit ADD COLUMN updates_json TEXT;
ALTER TABLE gatekeeper_audit ADD COLUMN user_initiated BOOLEAN DEFAULT FALSE;
```

### Message Outbox Table (New)
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
```

---

## New Telegram Commands

### Project Metadata
- `/importance <project_id> <1-5>` - Set project importance
- `/urgency <project_id> <1-5>` - Set project urgency
- `/deadline <project_id> <date/duration>` - Set deadline
- `/describe <project_id> <text>` - Update description

### Project Views
- `/projects [status]` - List projects by priority
- `/view <project_id>` - View project details
- `/complete <project_id>` - Mark as completed

### Message Outbox
- `/mcp outbox status` - Show message counts
- `/mcp outbox inspect <message_id>` - View details
- `/mcp outbox requeue <message_id>` - Retry failed message

---

## Testing Strategy

### Unit Tests
- Message Outbox producer/consumer API
- Project Manager enrichment queue logic
- Natural PM timing calculations
- Pressure score calculation
- SQL Gatekeeper direct update validation
- Obsidian sync (both directions)

### Integration Tests
- End-to-end: Scout → Monitor → Gatekeeper → PM → Obsidian
- Incremental enrichment flow
- Bidirectional Obsidian sync
- Event-driven next question
- Natural PM rhythm (follow-ups, back-off)
- Duplicate project prevention

---

## Success Criteria

### Story 027 Success
- [ ] Messages delivered to Telegram
- [ ] Failures retry with backoff
- [ ] User responses route to originating agent
- [ ] CLI commands work

### CR-014-001 Success
- [ ] `update_project_direct()` validates whitelist
- [ ] Direct updates logged in audit trail
- [ ] Protected fields cannot be modified

### Story 016 Success
- [ ] Projects incrementally enriched
- [ ] Event-driven next question after user response
- [ ] Natural PM rhythm (no fixed quotas)
- [ ] Bidirectional sync works (SQL ↔ Obsidian)
- [ ] Monitor doesn't rediscover existing projects
- [ ] Scheduled jobs run without errors

---

## Documentation

- **Implementation Plan**: [STORY_016_027_IMPLEMENTATION_PLAN.md](user-stories/phase-4-latent-scout/STORY_016_027_IMPLEMENTATION_PLAN.md)
- **Summary**: [STORY_016_027_SUMMARY.md](user-stories/phase-4-latent-scout/STORY_016_027_SUMMARY.md)
- **Story 027 Spec**: [story-027-message-outbox-relay.md](user-stories/phase-4-latent-scout/story-027-message-outbox-relay.md)
- **Story 016 Spec**: [story-016-project-manager-agent.md](user-stories/phase-4-latent-scout/story-016-project-manager-agent.md)
- **Change Request**: [story-014-CR-001-direct-user-updates.md](user-stories/phase-4-latent-scout/story-014-CR-001-direct-user-updates.md)

---

## Development Workflow

1. **Work in this worktree**: `/home/tgrytnes/projects/Mnemosyne-story-016-027`
2. **Branch**: `feature/016-027-project-manager-outbox`
3. **Based on**: `origin/main` (commit: `30aabbc`)
4. **Merge to**: `main` (when all acceptance criteria met)

### Git Commands

```bash
# Switch to this worktree
cd /home/tgrytnes/projects/Mnemosyne-story-016-027

# Create commits as you implement
git add <files>
git commit -m "Your commit message"

# Push to remote
git push origin feature/016-027-project-manager-outbox

# When ready, create PR to main
gh pr create --base main --head feature/016-027-project-manager-outbox
```

---

## Dependencies

### Upstream (Must exist before implementing)
- ✅ Story 014: SQL Project Gatekeeper (already implemented)
- ⏳ Story 015: Monitor Agent (creates proposal queue)
- The Ananke PostgreSQL schema
- Hermes Telegram bot infrastructure
- Obsidian vault access

### External Libraries
- APScheduler (background jobs)
- Watchdog (FileSystemWatcher)
- PyYAML (frontmatter parsing)
- SQLite (message outbox)

---

## Next Steps

1. ✅ Feature branch created
2. ✅ Worktree set up
3. ✅ Documentation in place
4. 🔲 Begin Phase 1: Message Outbox implementation
5. 🔲 Run unit tests after each phase
6. 🔲 Integration tests after all phases complete
7. 🔲 Create PR to main

---

**Last Updated**: 2026-01-01

**Assigned To**: TBD

**Status**: Ready for implementation 🚀
