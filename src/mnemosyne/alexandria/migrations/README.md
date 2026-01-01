# Database Migrations for Mnemosyne

This directory contains SQL migration scripts for The Ananke (PostgreSQL) and other Mnemosyne databases.

## Migration Files

### Story 014 & CR-014-001: SQL Project Gatekeeper
- **014_enhance_gatekeeper_audit.sql** - Enhances `gatekeeper_audit` table to support direct user updates
  - Adds `action_type` column (approval, rejection, direct_update, rollback)
  - Adds `updates_json` column to store update payloads
  - Adds `user_initiated` flag to distinguish user vs agent actions
  - Creates indexes for efficient audit queries

### Story 016: Project Manager Agent
- **016_extend_projects_schema.sql** - Extends `projects` table for project management
  - Adds `importance` (1-5 scale, user metadata)
  - Adds `urgency` (1-5 scale, user metadata)
  - Adds `deadline` (timestamp for time-sensitive projects)
  - Adds `work_estimate` (hours, for pressure calculation)
  - Adds `pressure_score` (calculated: work ÷ time)
  - Adds Obsidian sync fields: `obsidian_file_path`, `last_synced_to_obsidian`, `last_synced_from_obsidian`
  - Creates indexes for efficient priority and sync queries

### Story 027: Message Outbox Relay
- **027_create_message_outbox.sql** - Creates `message_outbox` table (SQLite)
  - Agent-to-user communication queue
  - Supports idempotent message delivery
  - Response routing back to originating agents
  - State machine: pending → delivered/awaiting_response → delivered
  - Retry logic with attempt tracking

## Migration Execution

### PostgreSQL Migrations (The Ananke)

```bash
# Execute migrations in order
psql -h $ANANKE_HOST -U $ANANKE_USER -d $ANANKE_DB -f 014_enhance_gatekeeper_audit.sql
psql -h $ANANKE_HOST -U $ANANKE_USER -d $ANANKE_DB -f 016_extend_projects_schema.sql
```

### SQLite Migrations (Message Outbox)

```bash
# Create message outbox database
sqlite3 $MESSAGE_OUTBOX_PATH < 027_create_message_outbox.sql
```

Or programmatically:

```python
import sqlite3

# PostgreSQL migrations (via psycopg2)
with psycopg2.connect(ananke_dsn) as conn:
    with conn.cursor() as cur:
        with open('migrations/014_enhance_gatekeeper_audit.sql') as f:
            cur.execute(f.read())
        with open('migrations/016_extend_projects_schema.sql') as f:
            cur.execute(f.read())
    conn.commit()

# SQLite migrations
with sqlite3.connect(message_outbox_path) as conn:
    with open('migrations/027_create_message_outbox.sql') as f:
        conn.executescript(f.read())
    conn.commit()
```

## Migration Order

**IMPORTANT**: Execute migrations in this order to avoid dependency issues:

1. `014_enhance_gatekeeper_audit.sql` - Enhances existing table
2. `016_extend_projects_schema.sql` - Extends projects table
3. `027_create_message_outbox.sql` - Creates new table (independent)

## Rollback

To rollback migrations (if needed):

```sql
-- Rollback 016_extend_projects_schema.sql
ALTER TABLE projects DROP COLUMN IF EXISTS importance;
ALTER TABLE projects DROP COLUMN IF EXISTS urgency;
ALTER TABLE projects DROP COLUMN IF EXISTS deadline;
ALTER TABLE projects DROP COLUMN IF EXISTS work_estimate;
ALTER TABLE projects DROP COLUMN IF EXISTS pressure_score;
ALTER TABLE projects DROP COLUMN IF EXISTS obsidian_file_path;
ALTER TABLE projects DROP COLUMN IF EXISTS last_synced_to_obsidian;
ALTER TABLE projects DROP COLUMN IF EXISTS last_synced_from_obsidian;
DROP INDEX IF EXISTS idx_projects_importance;
DROP INDEX IF EXISTS idx_projects_urgency;
DROP INDEX IF EXISTS idx_projects_deadline;
DROP INDEX IF EXISTS idx_projects_pressure;
DROP INDEX IF EXISTS idx_projects_obsidian_path;

-- Rollback 014_enhance_gatekeeper_audit.sql
ALTER TABLE gatekeeper_audit DROP COLUMN IF EXISTS action_type;
ALTER TABLE gatekeeper_audit DROP COLUMN IF EXISTS updates_json;
ALTER TABLE gatekeeper_audit DROP COLUMN IF EXISTS user_initiated;
DROP INDEX IF EXISTS idx_gatekeeper_audit_action;
DROP INDEX IF EXISTS idx_gatekeeper_audit_user;

-- Rollback 027_create_message_outbox.sql
DROP TABLE IF EXISTS message_outbox;
```

## Testing Migrations

Before applying to production, test migrations on a copy of the database:

```bash
# Create test database copy
pg_dump -h $PROD_HOST -U $USER $DB > backup.sql
createdb test_ananke
psql test_ananke < backup.sql

# Test migrations
psql test_ananke -f 014_enhance_gatekeeper_audit.sql
psql test_ananke -f 016_extend_projects_schema.sql

# Verify schema
psql test_ananke -c "\d projects"
psql test_ananke -c "\d gatekeeper_audit"
```

## Schema Verification

After applying migrations, verify the schema:

```sql
-- Check projects table columns
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'projects'
ORDER BY ordinal_position;

-- Check gatekeeper_audit table columns
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'gatekeeper_audit'
ORDER BY ordinal_position;

-- Check message_outbox table (SQLite)
-- .schema message_outbox
```

## Related Documentation

- [Story 014: SQL Project Gatekeeper](../../../user-stories/phase-4-latent-scout/story-014-sql-project-gatekeeper.md)
- [Story 016: Project Manager Agent](../../../user-stories/phase-4-latent-scout/story-016-project-manager-agent.md)
- [Story 027: Message Outbox Relay](../../../user-stories/phase-4-latent-scout/story-027-message-outbox-relay.md)
- [CR-014-001: Direct User Updates](../../../user-stories/phase-4-latent-scout/story-014-CR-001-direct-user-updates.md)
