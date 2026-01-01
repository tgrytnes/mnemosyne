"""
Unit tests for SQL Gatekeeper Direct User Updates (CR-014-001)

Tests the update_project_direct() method that allows user-initiated updates
to bypass the approval queue while maintaining audit trail.

TDD Approach: These tests are written BEFORE implementation.
"""

import json
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import pytest


# ==============================================================================
# Test Fixtures
# ==============================================================================

@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for testing"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    yield db_path

    # Cleanup
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def gatekeeper_db(temp_db):
    """Create SQL Gatekeeper database with enhanced schema"""
    conn = sqlite3.connect(temp_db)
    conn.row_factory = sqlite3.Row

    # Create projects table (simplified from The Ananke schema)
    conn.execute("""
        CREATE TABLE projects (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            discovered_by TEXT,
            discovery_id TEXT,
            cluster_ids TEXT,
            confidence_score REAL,
            verified_by_user BOOLEAN DEFAULT FALSE,
            verified_at TIMESTAMP,
            importance INTEGER CHECK (importance >= 1 AND importance <= 5),
            urgency INTEGER CHECK (urgency >= 1 AND urgency <= 5),
            work_estimate INTEGER,
            deadline TIMESTAMP,
            status TEXT DEFAULT 'candidate',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create enhanced gatekeeper_audit table
    conn.execute("""
        CREATE TABLE gatekeeper_audit (
            id INTEGER PRIMARY KEY,
            approval_id TEXT,
            action_type TEXT DEFAULT 'approval',
            approved BOOLEAN,
            project_id INTEGER REFERENCES projects(id),
            updates_json TEXT,
            user_initiated BOOLEAN DEFAULT FALSE,
            decided_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            decided_by TEXT DEFAULT 'telegram_user'
        )
    """)

    conn.execute("CREATE INDEX idx_gatekeeper_audit_approval ON gatekeeper_audit(approval_id)")
    conn.execute("CREATE INDEX idx_gatekeeper_audit_project ON gatekeeper_audit(project_id)")
    conn.execute("CREATE INDEX idx_gatekeeper_audit_action ON gatekeeper_audit(action_type)")

    conn.commit()

    yield conn

    conn.close()


@pytest.fixture
def sample_project(gatekeeper_db):
    """Create a sample project in the database"""
    cursor = gatekeeper_db.cursor()

    cursor.execute("""
        INSERT INTO projects (
            title, description, discovered_by, discovery_id,
            cluster_ids, confidence_score, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        'Test Project',
        'A test project',
        'latent_scout',
        'disco_001',
        '["cluster_1", "cluster_2"]',
        0.85,
        'candidate'
    ))

    gatekeeper_db.commit()

    return cursor.lastrowid


@pytest.fixture
def sql_gatekeeper(gatekeeper_db):
    """Create SQLProjectGatekeeper instance"""
    from mnemosyne.alexandria.sql_gatekeeper import SQLProjectGatekeeper

    return SQLProjectGatekeeper(gatekeeper_db)


# ==============================================================================
# Basic Functionality Tests
# ==============================================================================

class TestDirectUpdateBasicFunctionality:
    """Test basic update_project_direct() functionality"""

    def test_update_single_field(self, sql_gatekeeper, sample_project):
        """Test updating a single allowed field"""
        success = sql_gatekeeper.update_project_direct(
            project_id=sample_project,
            updates={'importance': 5},
            user_initiated=True
        )

        assert success is True

        # Verify update in database
        cursor = sql_gatekeeper.db.cursor()
        cursor.execute("SELECT importance FROM projects WHERE id = ?", (sample_project,))
        row = cursor.fetchone()

        assert row['importance'] == 5

    def test_update_multiple_fields(self, sql_gatekeeper, sample_project):
        """Test updating multiple allowed fields at once"""
        success = sql_gatekeeper.update_project_direct(
            project_id=sample_project,
            updates={
                'importance': 4,
                'urgency': 5,
                'work_estimate': 20
            },
            user_initiated=True
        )

        assert success is True

        # Verify all updates
        cursor = sql_gatekeeper.db.cursor()
        cursor.execute(
            "SELECT importance, urgency, work_estimate FROM projects WHERE id = ?",
            (sample_project,)
        )
        row = cursor.fetchone()

        assert row['importance'] == 4
        assert row['urgency'] == 5
        assert row['work_estimate'] == 20

    def test_update_description(self, sql_gatekeeper, sample_project):
        """Test updating description field"""
        new_description = "Updated description with more details"

        success = sql_gatekeeper.update_project_direct(
            project_id=sample_project,
            updates={'description': new_description},
            user_initiated=True
        )

        assert success is True

        # Verify update
        cursor = sql_gatekeeper.db.cursor()
        cursor.execute("SELECT description FROM projects WHERE id = ?", (sample_project,))
        row = cursor.fetchone()

        assert row['description'] == new_description

    def test_update_status(self, sql_gatekeeper, sample_project):
        """Test updating status field"""
        success = sql_gatekeeper.update_project_direct(
            project_id=sample_project,
            updates={'status': 'active'},
            user_initiated=True
        )

        assert success is True

        # Verify update
        cursor = sql_gatekeeper.db.cursor()
        cursor.execute("SELECT status FROM projects WHERE id = ?", (sample_project,))
        row = cursor.fetchone()

        assert row['status'] == 'active'

    def test_update_deadline(self, sql_gatekeeper, sample_project):
        """Test updating deadline field with datetime"""
        deadline = datetime(2026, 12, 31, 23, 59, 59)

        success = sql_gatekeeper.update_project_direct(
            project_id=sample_project,
            updates={'deadline': deadline},
            user_initiated=True
        )

        assert success is True

        # Verify update
        cursor = sql_gatekeeper.db.cursor()
        cursor.execute("SELECT deadline FROM projects WHERE id = ?", (sample_project,))
        row = cursor.fetchone()

        assert row['deadline'] is not None


# ==============================================================================
# Whitelist Validation Tests
# ==============================================================================

class TestWhitelistValidation:
    """Test that only whitelisted fields can be updated"""

    def test_allowed_fields_whitelist(self, sql_gatekeeper, sample_project):
        """Test that all allowed fields are accepted"""
        allowed_fields = {
            'importance': 5,
            'urgency': 4,
            'deadline': datetime(2026, 12, 31),
            'description': 'Test description',
            'status': 'active',
            'work_estimate': 30
        }

        # Should succeed for all allowed fields
        success = sql_gatekeeper.update_project_direct(
            project_id=sample_project,
            updates=allowed_fields,
            user_initiated=True
        )

        assert success is True

    def test_reject_protected_field_title(self, sql_gatekeeper, sample_project):
        """Test that updating 'title' is rejected (protected field)"""
        with pytest.raises(ValueError, match="Cannot update fields"):
            sql_gatekeeper.update_project_direct(
                project_id=sample_project,
                updates={'title': 'New Title'},
                user_initiated=True
            )

    def test_reject_protected_field_discovery_id(self, sql_gatekeeper, sample_project):
        """Test that updating 'discovery_id' is rejected (protected field)"""
        with pytest.raises(ValueError, match="Cannot update fields"):
            sql_gatekeeper.update_project_direct(
                project_id=sample_project,
                updates={'discovery_id': 'fake_disco_id'},
                user_initiated=True
            )

    def test_reject_protected_field_discovered_by(self, sql_gatekeeper, sample_project):
        """Test that updating 'discovered_by' is rejected (protected field)"""
        with pytest.raises(ValueError, match="Cannot update fields"):
            sql_gatekeeper.update_project_direct(
                project_id=sample_project,
                updates={'discovered_by': 'fake_agent'},
                user_initiated=True
            )

    def test_reject_protected_field_cluster_ids(self, sql_gatekeeper, sample_project):
        """Test that updating 'cluster_ids' is rejected (protected field)"""
        with pytest.raises(ValueError, match="Cannot update fields"):
            sql_gatekeeper.update_project_direct(
                project_id=sample_project,
                updates={'cluster_ids': '["fake_cluster"]'},
                user_initiated=True
            )

    def test_reject_protected_field_confidence_score(self, sql_gatekeeper, sample_project):
        """Test that updating 'confidence_score' is rejected (protected field)"""
        with pytest.raises(ValueError, match="Cannot update fields"):
            sql_gatekeeper.update_project_direct(
                project_id=sample_project,
                updates={'confidence_score': 0.99},
                user_initiated=True
            )

    def test_reject_mixed_allowed_and_protected(self, sql_gatekeeper, sample_project):
        """Test that mixing allowed and protected fields is rejected"""
        with pytest.raises(ValueError, match="Cannot update fields"):
            sql_gatekeeper.update_project_direct(
                project_id=sample_project,
                updates={
                    'importance': 5,  # Allowed
                    'title': 'New Title'  # Protected - should cause rejection
                },
                user_initiated=True
            )


# ==============================================================================
# Safety and Validation Tests
# ==============================================================================

class TestSafetyValidation:
    """Test safety checks and validation"""

    def test_require_user_initiated_true(self, sql_gatekeeper, sample_project):
        """Test that user_initiated=True is required"""
        with pytest.raises(ValueError, match="require user_initiated=True"):
            sql_gatekeeper.update_project_direct(
                project_id=sample_project,
                updates={'importance': 5},
                user_initiated=False
            )

    def test_nonexistent_project_returns_false(self, sql_gatekeeper):
        """Test that updating nonexistent project returns False"""
        success = sql_gatekeeper.update_project_direct(
            project_id=99999,
            updates={'importance': 5},
            user_initiated=True
        )

        assert success is False

    def test_empty_updates_dict(self, sql_gatekeeper, sample_project):
        """Test that empty updates dict is handled gracefully"""
        success = sql_gatekeeper.update_project_direct(
            project_id=sample_project,
            updates={},
            user_initiated=True
        )

        # Should succeed but make no changes
        assert success is True


# ==============================================================================
# Audit Trail Tests
# ==============================================================================

class TestAuditTrail:
    """Test that all direct updates are logged to audit trail"""

    def test_audit_log_created(self, sql_gatekeeper, sample_project):
        """Test that direct update creates audit log entry"""
        sql_gatekeeper.update_project_direct(
            project_id=sample_project,
            updates={'importance': 5, 'urgency': 4},
            user_initiated=True
        )

        # Verify audit log entry exists
        cursor = sql_gatekeeper.db.cursor()
        cursor.execute("""
            SELECT * FROM gatekeeper_audit
            WHERE project_id = ? AND action_type = 'direct_update'
        """, (sample_project,))

        row = cursor.fetchone()

        assert row is not None
        assert row['action_type'] == 'direct_update'
        assert row['user_initiated'] == 1  # SQLite BOOLEAN as INTEGER
        assert row['project_id'] == sample_project

    def test_audit_log_contains_updates(self, sql_gatekeeper, sample_project):
        """Test that audit log stores the updates payload"""
        updates = {'importance': 5, 'urgency': 4}

        sql_gatekeeper.update_project_direct(
            project_id=sample_project,
            updates=updates,
            user_initiated=True
        )

        # Verify updates_json in audit log
        cursor = sql_gatekeeper.db.cursor()
        cursor.execute("""
            SELECT updates_json FROM gatekeeper_audit
            WHERE project_id = ? AND action_type = 'direct_update'
        """, (sample_project,))

        row = cursor.fetchone()

        stored_updates = json.loads(row['updates_json'])
        assert stored_updates['importance'] == 5
        assert stored_updates['urgency'] == 4

    def test_audit_log_timestamp(self, sql_gatekeeper, sample_project):
        """Test that audit log includes timestamp"""
        sql_gatekeeper.update_project_direct(
            project_id=sample_project,
            updates={'importance': 5},
            user_initiated=True
        )

        # Verify decided_at timestamp exists
        cursor = sql_gatekeeper.db.cursor()
        cursor.execute("""
            SELECT decided_at FROM gatekeeper_audit
            WHERE project_id = ? AND action_type = 'direct_update'
        """, (sample_project,))

        row = cursor.fetchone()

        assert row['decided_at'] is not None

    def test_multiple_updates_create_multiple_audit_logs(self, sql_gatekeeper, sample_project):
        """Test that multiple updates create separate audit log entries"""
        # First update
        sql_gatekeeper.update_project_direct(
            project_id=sample_project,
            updates={'importance': 5},
            user_initiated=True
        )

        # Second update
        sql_gatekeeper.update_project_direct(
            project_id=sample_project,
            updates={'urgency': 4},
            user_initiated=True
        )

        # Verify two audit log entries
        cursor = sql_gatekeeper.db.cursor()
        cursor.execute("""
            SELECT COUNT(*) as count FROM gatekeeper_audit
            WHERE project_id = ? AND action_type = 'direct_update'
        """, (sample_project,))

        count = cursor.fetchone()['count']

        assert count == 2


# ==============================================================================
# Timestamp Update Tests
# ==============================================================================

class TestTimestampUpdates:
    """Test that updated_at timestamp is automatically updated"""

    def test_updated_at_timestamp_changed(self, sql_gatekeeper, sample_project):
        """Test that updated_at is set to current timestamp"""
        # Get original updated_at
        cursor = sql_gatekeeper.db.cursor()
        cursor.execute("SELECT updated_at FROM projects WHERE id = ?", (sample_project,))
        original_updated_at = cursor.fetchone()['updated_at']

        # Wait a tiny bit to ensure timestamp difference
        import time
        time.sleep(0.01)

        # Update project
        sql_gatekeeper.update_project_direct(
            project_id=sample_project,
            updates={'importance': 5},
            user_initiated=True
        )

        # Get new updated_at
        cursor.execute("SELECT updated_at FROM projects WHERE id = ?", (sample_project,))
        new_updated_at = cursor.fetchone()['updated_at']

        # Timestamps should be different
        assert new_updated_at != original_updated_at


# ==============================================================================
# Transaction and Rollback Tests
# ==============================================================================

class TestTransactionHandling:
    """Test transaction handling and rollback on failure"""

    def test_rollback_on_constraint_violation(self, sql_gatekeeper, sample_project):
        """Test that transaction rolls back on constraint violation"""
        # Try to set importance to invalid value (should fail CHECK constraint)
        success = sql_gatekeeper.update_project_direct(
            project_id=sample_project,
            updates={'importance': 10},  # Invalid: must be 1-5
            user_initiated=True
        )

        assert success is False

        # Verify no changes were made
        cursor = sql_gatekeeper.db.cursor()
        cursor.execute("SELECT importance FROM projects WHERE id = ?", (sample_project,))
        row = cursor.fetchone()

        assert row['importance'] is None  # Should still be NULL


# ==============================================================================
# Integration with Other Components Tests
# ==============================================================================

class TestIntegrationPoints:
    """Test integration with Project Manager and Obsidian sync"""

    def test_telegram_command_workflow(self, sql_gatekeeper, sample_project):
        """Test typical Telegram command workflow"""
        # Simulate: User sends /importance 1 5
        success = sql_gatekeeper.update_project_direct(
            project_id=sample_project,
            updates={'importance': 5},
            user_initiated=True
        )

        assert success is True

        # Would then:
        # 1. Record response in Message Outbox
        # 2. Sync to Obsidian
        # 3. Project Manager continues enrichment

    def test_obsidian_edit_workflow(self, sql_gatekeeper, sample_project):
        """Test typical Obsidian edit workflow"""
        # Simulate: User edits YAML frontmatter in Obsidian
        # FileSystemWatcher detects change and calls:
        success = sql_gatekeeper.update_project_direct(
            project_id=sample_project,
            updates={
                'importance': 4,
                'urgency': 5,
                'description': 'Updated from Obsidian'
            },
            user_initiated=True
        )

        assert success is True

        # Would then:
        # Silent sync (no Project Manager interaction)

    def test_project_manager_enrichment_workflow(self, sql_gatekeeper, sample_project):
        """Test Project Manager incremental enrichment workflow"""
        # Stage 1: User sets importance
        sql_gatekeeper.update_project_direct(
            project_id=sample_project,
            updates={'importance': 5},
            user_initiated=True
        )

        # Stage 2: User sets urgency
        sql_gatekeeper.update_project_direct(
            project_id=sample_project,
            updates={'urgency': 4},
            user_initiated=True
        )

        # Stage 3: User sets deadline (high priority: importance+urgency >= 7)
        sql_gatekeeper.update_project_direct(
            project_id=sample_project,
            updates={'deadline': datetime(2026, 12, 31)},
            user_initiated=True
        )

        # Verify all stages completed
        cursor = sql_gatekeeper.db.cursor()
        cursor.execute(
            "SELECT importance, urgency, deadline FROM projects WHERE id = ?",
            (sample_project,)
        )
        row = cursor.fetchone()

        assert row['importance'] == 5
        assert row['urgency'] == 4
        assert row['deadline'] is not None


# ==============================================================================
# Edge Cases Tests
# ==============================================================================

class TestEdgeCases:
    """Test edge cases and unusual inputs"""

    def test_update_with_none_values(self, sql_gatekeeper, sample_project):
        """Test updating fields to None (clearing values)"""
        # First set some values
        sql_gatekeeper.update_project_direct(
            project_id=sample_project,
            updates={'importance': 5, 'urgency': 4},
            user_initiated=True
        )

        # Then clear them
        success = sql_gatekeeper.update_project_direct(
            project_id=sample_project,
            updates={'importance': None, 'urgency': None},
            user_initiated=True
        )

        assert success is True

        # Verify values are NULL
        cursor = sql_gatekeeper.db.cursor()
        cursor.execute(
            "SELECT importance, urgency FROM projects WHERE id = ?",
            (sample_project,)
        )
        row = cursor.fetchone()

        assert row['importance'] is None
        assert row['urgency'] is None

    def test_update_same_value_twice(self, sql_gatekeeper, sample_project):
        """Test updating to the same value (idempotent)"""
        # First update
        sql_gatekeeper.update_project_direct(
            project_id=sample_project,
            updates={'importance': 5},
            user_initiated=True
        )

        # Same update again
        success = sql_gatekeeper.update_project_direct(
            project_id=sample_project,
            updates={'importance': 5},
            user_initiated=True
        )

        assert success is True

        # Should have two audit log entries (both updates logged)
        cursor = sql_gatekeeper.db.cursor()
        cursor.execute("""
            SELECT COUNT(*) as count FROM gatekeeper_audit
            WHERE project_id = ? AND action_type = 'direct_update'
        """, (sample_project,))

        count = cursor.fetchone()['count']

        assert count == 2
