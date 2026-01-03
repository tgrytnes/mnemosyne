# Story 014-CR-001: SQL Gatekeeper Direct User Updates (Change Request)

**Change Request Type**: Enhancement
**Parent Story**: Story 014: SQL Project Gatekeeper
**Requested By**: Project Manager Agent (Story 016) requirements
**Feature Branch**: `feature/016-027-project-manager-outbox`

---

## Summary

Add direct user update pathway to SQL Gatekeeper to support Project Manager incremental enrichment and Obsidian bidirectional sync without requiring approval queue.

---

## Business Justification

### Problem Statement

The current SQL Gatekeeper (Story 014) only supports project creation via approval queue. When users provide metadata through:
1. **Telegram commands** (`/importance`, `/urgency`, `/deadline`)
2. **Obsidian markdown edits** (editing YAML frontmatter)

These user-initiated changes must also go through The Ananke, but requiring approval for user's own edits creates unnecessary friction.

### Why This Change is Needed

**Current Flow** (Story 014):
```
Scout → Monitor → Gatekeeper → User Approval → SQL
```

**New Requirement** (Story 016):
```
User → Telegram/Obsidian → ??? → SQL
```

The approval queue exists to prevent **autonomous agents** from polluting The Ananke. However, when the **user directly provides** metadata (importance, urgency, deadline), this data is inherently trusted and should bypass approval.

### Impact if Not Implemented

- Project Manager cannot update projects with user-provided metadata
- Bidirectional Obsidian sync cannot write back to SQL
- User would need to manually approve their own edits (poor UX)
- Story 016 (Project Manager Agent) would be blocked

---

## Acceptance Criteria

### Functional Requirements
- [ ] Add `update_project_direct()` method to `SQLProjectGatekeeper` class
- [ ] Method accepts: `project_id`, `updates` dict, `user_initiated` boolean flag
- [ ] Requires `user_initiated=True` flag (safety check to prevent misuse)
- [ ] Only allows updates to existing projects (cannot create new projects)
- [ ] Whitelist validation: Only allow specific fields to be updated
- [ ] Reject updates to protected fields (title, discovered_by, discovery_id, cluster_ids, confidence_score)
- [ ] All direct updates logged to enhanced audit trail
- [ ] Method returns boolean success/failure
- [ ] Failed updates rollback transaction and log error

### Allowed Update Fields (Whitelist)
- `importance` (INTEGER 1-5)
- `urgency` (INTEGER 1-5)
- `deadline` (TIMESTAMP)
- `description` (TEXT)
- `status` (TEXT: 'candidate', 'active', 'paused', 'completed')
- `work_estimate` (INTEGER)

### Protected Fields (Cannot Be Updated)
- `id` (PRIMARY KEY)
- `title` (only Scout/Monitor can set)
- `discovered_by` (immutable source tracking)
- `discovery_id` (immutable link to Discovery DB)
- `cluster_ids` (immutable Scout metadata)
- `confidence_score` (immutable Scout confidence)
- `verified_by_user` (only Gatekeeper approval can set)
- `verified_at` (only Gatekeeper approval can set)
- `created_at` (immutable timestamp)

### Audit Trail Enhancement
- [ ] Add `action_type` column to `gatekeeper_audit` table
  - Values: `'approval'`, `'rejection'`, `'direct_update'`
- [ ] Add `updates_json` column to store update payloads
  - Example: `{'importance': 5, 'urgency': 4, 'deadline': '2024-12-31T23:59:59'}`
- [ ] Add `user_initiated` boolean column
  - `TRUE` for direct user updates
  - `FALSE` for approval-based writes
- [ ] All direct updates logged with full context
- [ ] Audit log queryable by `action_type` and `user_initiated`

### Error Handling
- [ ] Raise `ValueError` if `user_initiated=False` (must be True)
- [ ] Raise `ValueError` if trying to update protected fields
- [ ] Raise `ValueError` if `project_id` does not exist
- [ ] Log all errors with full context
- [ ] Rollback transaction on any failure
- [ ] Return `False` on failure (don't raise exception to caller)

---

## Technical Specification

### New Method Signature

```python
def update_project_direct(
    self,
    project_id: int,
    updates: dict,
    user_initiated: bool = True
) -> bool:
    """
    Direct project update (bypasses approval for user-initiated changes)

    Used by Project Manager when user provides metadata via Telegram/Obsidian.
    This is safe because the user is DIRECTLY making the change.

    Args:
        project_id: Existing project ID in The Ananke
        updates: Dict of fields to update (importance, urgency, deadline, description, status, work_estimate)
        user_initiated: Must be True (safety check to prevent agent misuse)

    Returns:
        True if update succeeded, False otherwise

    Raises:
        ValueError: If user_initiated=False or trying to update protected fields

    Example:
        success = gatekeeper.update_project_direct(
            project_id=42,
            updates={'importance': 5, 'urgency': 4},
            user_initiated=True
        )
    """
```

### Implementation Pseudocode

```python
def update_project_direct(self, project_id: int, updates: dict, user_initiated: bool = True) -> bool:
    # 1. Validate user_initiated flag
    if not user_initiated:
        raise ValueError("Direct updates require user_initiated=True flag")

    # 2. Whitelist validation
    allowed_fields = {'importance', 'urgency', 'deadline', 'description', 'status', 'work_estimate'}
    update_fields = set(updates.keys())

    if not update_fields.issubset(allowed_fields):
        disallowed = update_fields - allowed_fields
        raise ValueError(f"Cannot update fields via direct update: {disallowed}")

    # 3. Build dynamic UPDATE query
    set_clauses = []
    values = []

    for field, value in updates.items():
        set_clauses.append(f"{field} = %s")
        values.append(value)

    # Always update timestamp
    set_clauses.append("updated_at = %s")
    values.append(datetime.now())

    values.append(project_id)

    # 4. Execute update
    cursor = self.db.cursor()

    query = f"""
        UPDATE projects
        SET {', '.join(set_clauses)}
        WHERE id = %s
        RETURNING id
    """

    try:
        cursor.execute(query, values)
        result = cursor.fetchone()

        if not result:
            log_error(f"Project {project_id} not found for update")
            return False

        self.db.commit()

        # 5. Log to audit trail
        self._log_direct_update(project_id, updates, user_initiated=True)

        log_info(f"Direct update to project {project_id}: {updates}")
        return True

    except Exception as e:
        log_error(f"Failed to update project {project_id}: {e}")
        self.db.rollback()
        return False
```

### Audit Logging Method

```python
def _log_direct_update(self, project_id: int, updates: dict, user_initiated: bool):
    """
    Audit trail for direct user updates
    """
    cursor = self.db.cursor()

    cursor.execute("""
        INSERT INTO gatekeeper_audit (
            project_id,
            action_type,
            updates_json,
            user_initiated,
            decided_at
        ) VALUES (%s, %s, %s, %s, %s)
    """, (
        project_id,
        'direct_update',
        json.dumps(updates),
        user_initiated,
        datetime.now()
    ))

    self.db.commit()
```

---

## Database Schema Changes

### Migration: `014_enhance_gatekeeper_audit.sql`

```sql
-- Add new columns to gatekeeper_audit table
ALTER TABLE gatekeeper_audit ADD COLUMN action_type TEXT DEFAULT 'approval';
-- Values: 'approval', 'rejection', 'direct_update'

ALTER TABLE gatekeeper_audit ADD COLUMN updates_json TEXT;
-- For direct updates: {'importance': 5, 'urgency': 4}

ALTER TABLE gatekeeper_audit ADD COLUMN user_initiated BOOLEAN DEFAULT FALSE;
-- TRUE for direct user updates, FALSE for approval-based writes

-- Add index for querying by action type
CREATE INDEX idx_gatekeeper_audit_action ON gatekeeper_audit(action_type);

-- Add index for querying user-initiated updates
CREATE INDEX idx_gatekeeper_audit_user_initiated ON gatekeeper_audit(user_initiated);
```

### Rollback Migration

```sql
-- Rollback: Drop new columns and indexes
DROP INDEX IF EXISTS idx_gatekeeper_audit_action;
DROP INDEX IF EXISTS idx_gatekeeper_audit_user_initiated;

ALTER TABLE gatekeeper_audit DROP COLUMN IF EXISTS action_type;
ALTER TABLE gatekeeper_audit DROP COLUMN IF EXISTS updates_json;
ALTER TABLE gatekeeper_audit DROP COLUMN IF EXISTS user_initiated;
```

---

## Integration Points

### 1. Project Manager Agent (Story 016)

**Use Case**: User responds to Project Manager questions via Telegram

```python
@hermes_bot.command("importance")
def cmd_set_importance(message, project_id: int, importance: int):
    """
    User responds to Project Manager's importance question
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
        # Record response in Message Outbox for agent routing
        agent = outbox.record_response(
            context_id=f'project:{project_id}',
            response_data={'field': 'importance', 'value': importance}
        )

        # Sync to Obsidian
        obsidian_sync.sync_project_to_obsidian(project_id)

        # EVENT-DRIVEN: Immediately ask next question
        project_manager.continue_enrichment(project_id)

        bot.send_message(message.chat.id, f"✅ Importance set to {importance}")
    else:
        bot.send_message(message.chat.id, f"❌ Failed to update project {project_id}")
```

### 2. Obsidian Bidirectional Sync (Story 016)

**Use Case**: User edits project markdown file in Obsidian

```python
class ObsidianProjectSync:
    def sync_obsidian_to_sql(self, file_path: Path):
        """
        Obsidian → SQL: User edited markdown, update SQL
        """
        content = file_path.read_text()

        # Parse frontmatter
        match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
        if not match:
            return

        frontmatter = yaml.safe_load(match.group(1))
        project_id = frontmatter.get('project_id')

        if not project_id:
            return

        # Extract user-editable fields
        updates = {
            'importance': frontmatter.get('importance'),
            'urgency': frontmatter.get('urgency'),
            'deadline': datetime.fromisoformat(frontmatter['deadline']) if frontmatter.get('deadline') else None,
            'description': frontmatter.get('description'),
            'status': frontmatter.get('status'),
        }

        # Remove None values
        updates = {k: v for k, v in updates.items() if v is not None}

        # Update SQL via Gatekeeper
        success = sql_gatekeeper.update_project_direct(
            project_id=project_id,
            updates=updates,
            user_initiated=True
        )

        if success:
            log_info(f"Synced {file_path} to SQL project {project_id}")
        else:
            log_error(f"Failed to sync {file_path} to SQL")
```

---

## Testing Requirements

### Unit Tests

```python
class TestSQLGatekeeperDirectUpdates:
    def test_update_project_direct_success(self):
        """Test successful direct update"""
        success = gatekeeper.update_project_direct(
            project_id=1,
            updates={'importance': 5, 'urgency': 4},
            user_initiated=True
        )
        assert success == True

        # Verify SQL updated
        project = db.query("SELECT * FROM projects WHERE id = 1")
        assert project['importance'] == 5
        assert project['urgency'] == 4

        # Verify audit log
        audit = db.query("SELECT * FROM gatekeeper_audit WHERE project_id = 1 AND action_type = 'direct_update'")
        assert audit['user_initiated'] == True
        assert json.loads(audit['updates_json']) == {'importance': 5, 'urgency': 4}

    def test_update_requires_user_initiated_true(self):
        """Test that user_initiated=False raises error"""
        with pytest.raises(ValueError, match="require user_initiated=True"):
            gatekeeper.update_project_direct(
                project_id=1,
                updates={'importance': 5},
                user_initiated=False
            )

    def test_update_rejects_protected_fields(self):
        """Test that protected fields cannot be updated"""
        with pytest.raises(ValueError, match="Cannot update fields"):
            gatekeeper.update_project_direct(
                project_id=1,
                updates={'title': 'New Title', 'discovery_id': 'fake'},
                user_initiated=True
            )

    def test_update_nonexistent_project_returns_false(self):
        """Test that updating nonexistent project returns False"""
        success = gatekeeper.update_project_direct(
            project_id=99999,
            updates={'importance': 5},
            user_initiated=True
        )
        assert success == False

    def test_whitelist_validation(self):
        """Test that only whitelisted fields are allowed"""
        # Should succeed
        success = gatekeeper.update_project_direct(
            project_id=1,
            updates={'importance': 5, 'urgency': 4, 'deadline': datetime.now()},
            user_initiated=True
        )
        assert success == True

        # Should fail
        with pytest.raises(ValueError):
            gatekeeper.update_project_direct(
                project_id=1,
                updates={'cluster_ids': ['fake']},
                user_initiated=True
            )
```

### Integration Tests

```python
class TestProjectManagerGatekeeperIntegration:
    def test_telegram_command_updates_via_gatekeeper(self):
        """Test that Telegram commands use Gatekeeper"""
        # Simulate user command: /importance 1 5
        response = telegram_bot.handle_command("/importance 1 5")

        # Verify SQL updated via Gatekeeper
        project = db.query("SELECT * FROM projects WHERE id = 1")
        assert project['importance'] == 5

        # Verify audit log shows direct_update
        audit = db.query("SELECT * FROM gatekeeper_audit WHERE project_id = 1 ORDER BY decided_at DESC LIMIT 1")
        assert audit['action_type'] == 'direct_update'
        assert audit['user_initiated'] == True

    def test_obsidian_edit_syncs_via_gatekeeper(self):
        """Test that Obsidian edits use Gatekeeper"""
        # Edit Obsidian markdown file
        project_file = Path(vault_path / "Projects/Test Project.md")
        frontmatter = yaml.safe_load(project_file.read_text().split('---')[1])
        frontmatter['importance'] = 5

        # Trigger FileSystemWatcher
        obsidian_sync.sync_obsidian_to_sql(project_file)

        # Verify SQL updated via Gatekeeper
        project = db.query("SELECT * FROM projects WHERE id = 1")
        assert project['importance'] == 5

        # Verify audit log
        audit = db.query("SELECT * FROM gatekeeper_audit WHERE project_id = 1 ORDER BY decided_at DESC LIMIT 1")
        assert audit['action_type'] == 'direct_update'
```

---

## Affected Components

- **Argus**: `src/mnemosyne/argus/gatekeeper/sql_gatekeeper.py` (updated)
- **Alexandria**: `gatekeeper_audit` table schema (updated)
- **Hermes**: Telegram commands will use new method
- **Aletheia**: Obsidian sync will use new method

---

## Dependencies

### Upstream (Blocks This CR)
- Story 014: SQL Project Gatekeeper (must be implemented first)

### Downstream (Blocked By This CR)
- Story 016: Project Manager Agent (requires this CR)
- Story 027: Message Outbox Relay (Project Manager uses this)

---

## Risks and Mitigations

### Risk 1: Bypassing Approval Could Allow Unwanted Data
**Mitigation**:
- Whitelist validation ensures only user-metadata fields can be updated
- Protected fields (title, discovery_id, cluster_ids) cannot be modified
- `user_initiated=True` flag required (prevents accidental misuse)
- Full audit trail logs all direct updates

### Risk 2: Obsidian Edits Could Corrupt SQL Data
**Mitigation**:
- YAML frontmatter parsing validates data types
- SQL constraints enforce data integrity (e.g., `CHECK (importance >= 1 AND importance <= 5)`)
- Transaction rollback on any error
- Audit log captures all changes for recovery

### Risk 3: Audit Trail Fragmentation
**Mitigation**:
- Enhanced `gatekeeper_audit` table captures BOTH approval-based and direct updates
- `action_type` field distinguishes between approval/rejection/direct_update
- All updates logged with timestamp and full payload

---

## Rollback Plan

If critical issues arise:

1. **Code Rollback**:
   - Remove `update_project_direct()` method from `SQLProjectGatekeeper`
   - Revert Telegram commands to previous implementation
   - Disable Obsidian → SQL sync

2. **Schema Rollback**:
   - Run rollback migration to remove new columns from `gatekeeper_audit`

3. **Preserve Audit Trail**:
   - Do NOT delete audit records
   - Existing `direct_update` records remain for historical analysis

---

## Priority

**Critical** - Blocks Story 016 (Project Manager Agent)

---

## Estimate

**2 story points** (1-2 days)

- 0.5 day: Implement `update_project_direct()` method
- 0.5 day: Enhance `gatekeeper_audit` schema and migration
- 0.5 day: Unit tests
- 0.5 day: Integration tests and documentation

---

## Acceptance Checklist

- [ ] `update_project_direct()` method implemented with whitelist validation
- [ ] `user_initiated=True` flag required (raises error if False)
- [ ] Protected fields cannot be updated (raises ValueError)
- [ ] Migration script for enhanced `gatekeeper_audit` schema
- [ ] Audit log captures all direct updates with `action_type='direct_update'`
- [ ] Unit tests pass (whitelist validation, error handling, audit logging)
- [ ] Integration tests pass (Telegram commands, Obsidian sync)
- [ ] Code reviewed and approved
- [ ] Documentation updated (Gatekeeper README, API docs)
- [ ] Rollback migration tested

---

## Related Stories

- **Story 014**: SQL Project Gatekeeper (parent story)
- **Story 016**: Project Manager Agent (requires this CR)
- **Story 027**: Message Outbox Relay (used by Project Manager)
- **Story 025**: Shadow Copy & Hygiene Layer (Obsidian safety)

---

## Linear Labels

`phase-4`, `change-request`, `gatekeeper`, `sql`, `alexandria`, `critical`

---

**Status**: ✅ Ready for implementation (in `feature/016-027-project-manager-outbox` branch)

**Approved By**: Project requirements for Story 016

**Implementation Branch**: `feature/016-027-project-manager-outbox`
