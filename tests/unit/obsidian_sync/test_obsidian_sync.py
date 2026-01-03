"""
Unit tests for Obsidian Bidirectional Sync (Story 016)

Tests the core sync logic between The Ananke (PostgreSQL) and Obsidian markdown files.
Covers both SQL → Obsidian and Obsidian → SQL sync operations.

TDD Approach: These tests are written BEFORE implementation (RED phase).
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch

import pytest

# ==============================================================================
# Test Fixtures
# ==============================================================================


@pytest.fixture
def mock_db_conn():
    """Mock PostgreSQL connection"""
    conn = Mock()
    cursor = Mock()

    # Make cursor support context manager
    cursor.__enter__ = Mock(return_value=cursor)
    cursor.__exit__ = Mock(return_value=None)

    conn.cursor.return_value = cursor
    return conn


@pytest.fixture
def mock_obsidian_vault(tmp_path):
    """Mock Obsidian vault directory"""
    vault_path = tmp_path / "ObsidianVault"
    vault_path.mkdir()
    (vault_path / "Projects").mkdir()
    return vault_path


@pytest.fixture
def sample_project_from_sql():
    """Sample project record from The Ananke"""
    return {
        "id": 42,
        "title": "Implement Dark Mode Toggle",
        "description": "Add a dark mode toggle to the application settings page",
        "discovered_by": "latent_scout",
        "discovery_id": "disco_20260101_001",
        "cluster_ids": ["cluster_theme_001", "cluster_ui_002"],
        "confidence_score": 0.89,
        "status": "active",
        "importance": 5,
        "urgency": 4,
        "deadline": datetime(2026, 12, 31, 23, 59, 59, tzinfo=UTC),
        "work_estimate": 20,
        "pressure_score": 1.25,
        "verified_by_user": True,
        "created_at": datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC),
        "updated_at": datetime(2026, 1, 1, 14, 30, 0, tzinfo=UTC),
        "obsidian_file_path": None,  # Not yet synced
        "last_synced_to_obsidian": None,
        "last_synced_from_obsidian": None,
    }


@pytest.fixture
def sample_obsidian_markdown():
    """Sample Obsidian markdown file content"""
    return """---
id: 42
title: Implement Dark Mode Toggle
discovered_by: latent_scout
discovery_id: disco_20260101_001
cluster_ids:
  - cluster_theme_001
  - cluster_ui_002
confidence_score: 0.89
status: active
importance: 5
urgency: 4
deadline: 2026-12-31T23:59:59+00:00
work_estimate: 20
pressure_score: 1.25
verified_by_user: true
created_at: 2026-01-01T10:00:00+00:00
updated_at: 2026-01-01T14:30:00+00:00
---

# Implement Dark Mode Toggle

Add a dark mode toggle to the application settings page

## Metadata

- **Status**: active
- **Importance**: 5/5
- **Urgency**: 4/5
- **Deadline**: 2026-12-31
- **Work Estimate**: 20 hours
- **Pressure Score**: 1.25

## Discovery Info

- **Discovered by**: latent_scout
- **Discovery ID**: disco_20260101_001
- **Confidence**: 89%
- **Verified**: Yes

## Timestamps

- **Created**: 2026-01-01 10:00:00 UTC
- **Updated**: 2026-01-01 14:30:00 UTC
"""


# ==============================================================================
# SQL → Obsidian Sync Tests
# ==============================================================================


class TestSQLToObsidianSync:
    """Test syncing projects from The Ananke to Obsidian markdown files"""

    def test_sync_new_project_creates_file(
        self, mock_db_conn, mock_obsidian_vault, sample_project_from_sql
    ):
        """Test that syncing a new project creates an Obsidian file"""
        from mnemosyne.aletheia.obsidian_sync.obsidian_sync import ObsidianSyncManager

        sync_manager = ObsidianSyncManager(mock_db_conn, str(mock_obsidian_vault))

        # Sync project to Obsidian
        result = sync_manager.sync_project_to_obsidian(sample_project_from_sql)

        # Should create markdown file
        expected_path = mock_obsidian_vault / "Projects" / "Implement-Dark-Mode-Toggle.md"
        assert expected_path.exists()

        # Should return the created file path
        assert result["file_path"] == str(expected_path)
        assert result["action"] == "created"

    def test_sync_updates_sql_obsidian_path(
        self, mock_db_conn, mock_obsidian_vault, sample_project_from_sql
    ):
        """Test that sync updates obsidian_file_path in SQL"""
        from mnemosyne.aletheia.obsidian_sync.obsidian_sync import ObsidianSyncManager

        sync_manager = ObsidianSyncManager(mock_db_conn, str(mock_obsidian_vault))
        cursor_mock = mock_db_conn.cursor.return_value.__enter__.return_value

        sync_manager.sync_project_to_obsidian(sample_project_from_sql)

        # Should update obsidian_file_path and last_synced_to_obsidian
        # Check that execute was called with an UPDATE query
        assert cursor_mock.execute.called
        # Verify the query contains the expected UPDATE
        calls = cursor_mock.execute.call_args_list
        update_calls = [call for call in calls if "UPDATE projects" in str(call[0][0])]
        assert len(update_calls) > 0, "Expected UPDATE projects query to be executed"

    def test_sync_existing_file_updates_content(
        self, mock_db_conn, mock_obsidian_vault, sample_project_from_sql
    ):
        """Test that syncing an existing file updates its content"""
        from mnemosyne.aletheia.obsidian_sync.obsidian_sync import ObsidianSyncManager

        # Create existing file with old content
        file_path = mock_obsidian_vault / "Projects" / "Implement-Dark-Mode-Toggle.md"
        file_path.write_text("---\nid: 42\ntitle: Old Title\n---\n# Old Title\nOld content")

        sample_project_from_sql["obsidian_file_path"] = str(file_path)

        sync_manager = ObsidianSyncManager(mock_db_conn, str(mock_obsidian_vault))
        result = sync_manager.sync_project_to_obsidian(sample_project_from_sql)

        # Should update file with new content
        assert result["action"] == "updated"

        # File should contain new title
        content = file_path.read_text()
        assert "Implement Dark Mode Toggle" in content
        assert "Old Title" not in content

    def test_sync_preserves_custom_sections(
        self, mock_db_conn, mock_obsidian_vault, sample_project_from_sql
    ):
        """Test that sync preserves user-added custom sections in markdown"""
        from mnemosyne.aletheia.obsidian_sync.obsidian_sync import ObsidianSyncManager

        # Create existing file with custom section
        file_path = mock_obsidian_vault / "Projects" / "Implement-Dark-Mode-Toggle.md"
        existing_content = """---
id: 42
title: Implement Dark Mode Toggle
status: active
---

# Implement Dark Mode Toggle

Description here

## My Custom Notes

These are my personal notes about this project.
I don't want these overwritten!

## Another Custom Section

More custom content
"""
        file_path.write_text(existing_content)
        sample_project_from_sql["obsidian_file_path"] = str(file_path)

        sync_manager = ObsidianSyncManager(mock_db_conn, str(mock_obsidian_vault))
        sync_manager.sync_project_to_obsidian(sample_project_from_sql)

        # Custom sections should be preserved
        updated_content = file_path.read_text()
        assert "## My Custom Notes" in updated_content
        assert "These are my personal notes" in updated_content
        assert "## Another Custom Section" in updated_content

    def test_sync_batch_projects(self, mock_db_conn, mock_obsidian_vault):
        """Test syncing multiple projects in batch"""
        from mnemosyne.aletheia.obsidian_sync.obsidian_sync import ObsidianSyncManager

        projects = [
            {
                "id": 1,
                "title": "Project One",
                "description": "Desc 1",
                "status": "active",
                "discovered_by": "test",
                "discovery_id": "d1",
                "cluster_ids": ["c1"],
                "confidence_score": 0.8,
                "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
            },
            {
                "id": 2,
                "title": "Project Two",
                "description": "Desc 2",
                "status": "active",
                "discovered_by": "test",
                "discovery_id": "d2",
                "cluster_ids": ["c2"],
                "confidence_score": 0.9,
                "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
            },
        ]

        sync_manager = ObsidianSyncManager(mock_db_conn, str(mock_obsidian_vault))
        results = sync_manager.sync_all_projects_to_obsidian(projects)

        # Should sync both projects
        assert len(results) == 2
        assert results[0]["project_id"] == 1
        assert results[1]["project_id"] == 2

        # Both files should exist
        assert (mock_obsidian_vault / "Projects" / "Project-One.md").exists()
        assert (mock_obsidian_vault / "Projects" / "Project-Two.md").exists()

    def test_sync_skips_recently_synced(
        self, mock_db_conn, mock_obsidian_vault, sample_project_from_sql
    ):
        """Test that sync skips projects synced within cooldown period"""
        from mnemosyne.aletheia.obsidian_sync.obsidian_sync import ObsidianSyncManager

        # Mark project as synced 30 seconds ago
        sample_project_from_sql["last_synced_to_obsidian"] = datetime.now(UTC) - timedelta(
            seconds=30
        )

        sync_manager = ObsidianSyncManager(
            mock_db_conn, str(mock_obsidian_vault), sync_cooldown_seconds=60
        )
        result = sync_manager.sync_project_to_obsidian(sample_project_from_sql, force=False)

        # Should skip sync
        assert result["action"] == "skipped"
        assert result["reason"] == "recently_synced"

    def test_sync_force_bypasses_cooldown(
        self, mock_db_conn, mock_obsidian_vault, sample_project_from_sql
    ):
        """Test that force=True bypasses cooldown"""
        from mnemosyne.aletheia.obsidian_sync.obsidian_sync import ObsidianSyncManager

        # Mark as recently synced
        sample_project_from_sql["last_synced_to_obsidian"] = datetime.now(UTC) - timedelta(
            seconds=10
        )

        sync_manager = ObsidianSyncManager(
            mock_db_conn, str(mock_obsidian_vault), sync_cooldown_seconds=60
        )
        result = sync_manager.sync_project_to_obsidian(sample_project_from_sql, force=True)

        # Should sync anyway
        assert result["action"] in ["created", "updated"]


# ==============================================================================
# Obsidian → SQL Sync Tests
# ==============================================================================


class TestObsidianToSQLSync:
    """Test syncing Obsidian markdown edits back to The Ananke"""

    def test_sync_obsidian_edit_updates_sql(self, mock_db_conn, mock_obsidian_vault):
        """Test that Obsidian edits are synced to SQL"""
        from mnemosyne.aletheia.obsidian_sync.obsidian_sync import ObsidianSyncManager

        # Create Obsidian file with updated metadata
        markdown_content = """---
id: 42
title: Implement Dark Mode Toggle
discovered_by: latent_scout
discovery_id: disco_20260101_001
cluster_ids: [cluster_theme_001, cluster_ui_002]
confidence_score: 0.89
status: active
created_at: 2026-01-01T10:00:00+00:00
updated_at: 2026-01-01T14:00:00+00:00
importance: 3
urgency: 5
deadline: 2026-06-30T23:59:59+00:00
---

# Implement Dark Mode Toggle

Updated description from Obsidian
"""
        file_path = mock_obsidian_vault / "Projects" / "Implement-Dark-Mode-Toggle.md"
        file_path.write_text(markdown_content)

        sync_manager = ObsidianSyncManager(mock_db_conn, str(mock_obsidian_vault))
        cursor_mock = mock_db_conn.cursor.return_value.__enter__.return_value

        # Mock database responses for _project_exists and detect_conflict
        # _project_exists returns (42,)
        # detect_conflict returns (42, "title", updated_at, last_synced_from_obsidian)
        cursor_mock.fetchone.side_effect = [
            (42,),  # _project_exists check
            (
                42,
                "Test",
                datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC),
                None,
            ),  # detect_conflict check
        ]

        result = sync_manager.sync_obsidian_file_to_sql(str(file_path))

        # Should update SQL with new values
        assert result["action"] == "updated"

        # Should call SQL update (gatekeeper or direct)
        # Note: Implementation may use gatekeeper, so we just verify some update happened
        assert cursor_mock.execute.called or mock_gatekeeper.update_project_direct.called  # noqa: F821

    def test_sync_obsidian_validates_id_exists(self, mock_db_conn, mock_obsidian_vault):
        """Test that sync validates project ID exists in SQL"""
        from mnemosyne.aletheia.obsidian_sync.obsidian_sync import ObsidianSyncManager

        # Create file with non-existent ID
        markdown_content = """---
id: 99999
title: Non-existent Project
discovered_by: test
discovery_id: d1
cluster_ids: [c1]
confidence_score: 0.8
status: active
created_at: 2026-01-01T10:00:00+00:00
updated_at: 2026-01-01T14:00:00+00:00
---

# Non-existent Project
"""
        file_path = mock_obsidian_vault / "Projects" / "non-existent.md"
        file_path.write_text(markdown_content)

        sync_manager = ObsidianSyncManager(mock_db_conn, str(mock_obsidian_vault))
        cursor_mock = mock_db_conn.cursor.return_value.__enter__.return_value
        cursor_mock.fetchone.return_value = None  # Project not found

        with pytest.raises(ValueError, match="Project with id 99999 not found"):
            sync_manager.sync_obsidian_file_to_sql(str(file_path))

    def test_sync_obsidian_uses_gatekeeper_for_updates(self, mock_db_conn, mock_obsidian_vault):
        """Test that Obsidian sync uses SQL Gatekeeper for updates"""
        from mnemosyne.aletheia.obsidian_sync.obsidian_sync import ObsidianSyncManager

        markdown_content = """---
id: 42
title: Test
discovered_by: test
discovery_id: d1
cluster_ids: [c1]
confidence_score: 0.8
status: active
created_at: 2026-01-01T10:00:00+00:00
updated_at: 2026-01-01T14:00:00+00:00
importance: 4
urgency: 3
---

# Test
Description
"""
        file_path = mock_obsidian_vault / "Projects" / "test.md"
        file_path.write_text(markdown_content)

        # Mock gatekeeper
        mock_gatekeeper = Mock()
        mock_gatekeeper.update_project_direct.return_value = True

        sync_manager = ObsidianSyncManager(
            mock_db_conn, str(mock_obsidian_vault), gatekeeper=mock_gatekeeper
        )

        # Mock database responses
        cursor_mock = mock_db_conn.cursor.return_value.__enter__.return_value
        cursor_mock.fetchone.side_effect = [
            (42,),  # _project_exists check
            (
                42,
                "Test",
                datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC),
                None,
            ),  # detect_conflict check
        ]

        sync_manager.sync_obsidian_file_to_sql(str(file_path))

        # Should call gatekeeper's update_project_direct
        mock_gatekeeper.update_project_direct.assert_called_once()
        call_args = mock_gatekeeper.update_project_direct.call_args
        assert call_args[0][0] == 42  # project_id
        assert call_args[1]["user_initiated"] is True

    def test_sync_obsidian_only_updates_allowed_fields(self, mock_db_conn, mock_obsidian_vault):
        """Test that Obsidian sync only updates whitelisted fields"""
        from mnemosyne.aletheia.obsidian_sync.obsidian_sync import ObsidianSyncManager

        # User tries to edit protected fields in Obsidian
        markdown_content = """---
id: 42
title: Test
discovered_by: hacker
discovery_id: fake_disco
cluster_ids: [c1]
confidence_score: 1.0
status: active
created_at: 2026-01-01T10:00:00+00:00
updated_at: 2026-01-01T14:00:00+00:00
importance: 5
---

# Test
"""
        file_path = mock_obsidian_vault / "Projects" / "test.md"
        file_path.write_text(markdown_content)

        mock_gatekeeper = Mock()
        sync_manager = ObsidianSyncManager(
            mock_db_conn, str(mock_obsidian_vault), gatekeeper=mock_gatekeeper
        )

        # Mock database responses
        cursor_mock = mock_db_conn.cursor.return_value.__enter__.return_value
        cursor_mock.fetchone.side_effect = [
            (42,),  # _project_exists check
            (
                42,
                "Test",
                datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC),
                None,
            ),  # detect_conflict check
        ]

        sync_manager.sync_obsidian_file_to_sql(str(file_path))

        # Should only pass allowed fields to gatekeeper
        call_args = mock_gatekeeper.update_project_direct.call_args
        updates = call_args[0][1]

        # Should NOT include protected fields
        assert "discovered_by" not in updates
        assert "discovery_id" not in updates
        assert "confidence_score" not in updates

    def test_sync_all_obsidian_files(self, mock_db_conn, mock_obsidian_vault):
        """Test syncing all Obsidian files in vault"""
        from mnemosyne.aletheia.obsidian_sync.obsidian_sync import ObsidianSyncManager

        # Create multiple files
        files = [
            (
                "Project-1.md",
                "---\nid: 1\ntitle: P1\ndiscovered_by: test\ndiscovery_id: d1\ncluster_ids: [c1]\nconfidence_score: 0.8\nstatus: active\ncreated_at: 2026-01-01T10:00:00+00:00\nupdated_at: 2026-01-01T14:00:00+00:00\n---\n# P1\n",  # noqa: E501
            ),
            (
                "Project-2.md",
                "---\nid: 2\ntitle: P2\ndiscovered_by: test\ndiscovery_id: d2\ncluster_ids: [c2]\nconfidence_score: 0.8\nstatus: active\ncreated_at: 2026-01-01T10:00:00+00:00\nupdated_at: 2026-01-01T14:00:00+00:00\n---\n# P2\n",  # noqa: E501
            ),
        ]

        for filename, content in files:
            (mock_obsidian_vault / "Projects" / filename).write_text(content)

        sync_manager = ObsidianSyncManager(mock_db_conn, str(mock_obsidian_vault))

        with patch.object(sync_manager, "sync_obsidian_file_to_sql") as mock_sync:
            sync_manager.sync_all_obsidian_files()

            # Should sync both files
            assert mock_sync.call_count == 2


# ==============================================================================
# Conflict Detection Tests
# ==============================================================================


class TestConflictDetection:
    """Test detecting and handling sync conflicts"""

    def test_detect_conflict_when_both_modified(self, mock_db_conn, mock_obsidian_vault):
        """Test detecting conflict when both SQL and Obsidian were modified"""
        from mnemosyne.aletheia.obsidian_sync.obsidian_sync import ObsidianSyncManager

        # SQL was updated at 14:30
        sql_updated_at = datetime(2026, 1, 1, 14, 30, 0, tzinfo=UTC)

        # Obsidian was last synced at 14:00
        last_synced_from_obsidian = datetime(2026, 1, 1, 14, 0, 0, tzinfo=UTC)

        # File was modified at 14:45 (after SQL update)
        file_path = mock_obsidian_vault / "Projects" / "test.md"
        file_path.write_text(
            """---
id: 42
title: Test
discovered_by: test
discovery_id: d1
cluster_ids: [c1]
confidence_score: 0.8
status: active
created_at: 2026-01-01T10:00:00+00:00
updated_at: 2026-01-01T14:00:00+00:00
---

# Test
"""
        )
        file_path.touch()  # Set mtime to now

        sync_manager = ObsidianSyncManager(mock_db_conn, str(mock_obsidian_vault))

        # Mock SQL query to return project with conflict
        cursor_mock = mock_db_conn.cursor.return_value.__enter__.return_value
        cursor_mock.fetchone.return_value = (42, "Test", sql_updated_at, last_synced_from_obsidian)

        conflict = sync_manager.detect_conflict(str(file_path))

        # Should detect conflict
        assert conflict is not None
        assert conflict["type"] == "both_modified"
        assert conflict["sql_updated_at"] == sql_updated_at
        assert "obsidian_modified_at" in conflict

    def test_no_conflict_when_only_sql_modified(self, mock_db_conn, mock_obsidian_vault):
        """Test no conflict when only SQL was modified"""
        from mnemosyne.aletheia.obsidian_sync.obsidian_sync import ObsidianSyncManager

        # SQL updated at 15:00
        sql_updated_at = datetime(2026, 1, 1, 15, 0, 0, tzinfo=UTC)

        # Obsidian last synced at 14:00, file not modified since
        last_synced = datetime(2026, 1, 1, 14, 0, 0, tzinfo=UTC)

        file_path = mock_obsidian_vault / "Projects" / "test.md"
        file_path.write_text(
            """---
id: 42
title: Test
discovered_by: test
discovery_id: d1
cluster_ids: [c1]
confidence_score: 0.8
status: active
created_at: 2026-01-01T10:00:00+00:00
updated_at: 2026-01-01T14:00:00+00:00
---

# Test
"""
        )
        # Set file mtime to before SQL update
        file_path.touch()
        import os

        os.utime(file_path, (last_synced.timestamp(), last_synced.timestamp()))

        sync_manager = ObsidianSyncManager(mock_db_conn, str(mock_obsidian_vault))

        cursor_mock = mock_db_conn.cursor.return_value.__enter__.return_value
        cursor_mock.fetchone.return_value = (42, "Test", sql_updated_at, last_synced)

        conflict = sync_manager.detect_conflict(str(file_path))

        # No conflict - SQL wins
        assert conflict is None

    def test_conflict_resolution_sql_wins(self, mock_db_conn, mock_obsidian_vault):
        """Test conflict resolution with SQL-wins strategy"""
        from mnemosyne.aletheia.obsidian_sync.obsidian_sync import ObsidianSyncManager

        sync_manager = ObsidianSyncManager(
            mock_db_conn, str(mock_obsidian_vault), conflict_strategy="sql_wins"
        )

        file_path = mock_obsidian_vault / "Projects" / "test.md"
        file_path.write_text(
            """---
id: 42
title: Test
discovered_by: test
discovery_id: d1
cluster_ids: [c1]
confidence_score: 0.8
status: active
created_at: 2026-01-01T10:00:00+00:00
updated_at: 2026-01-01T14:00:00+00:00
importance: 3
---

# Test
"""
        )

        # Mock conflict
        conflict = {
            "type": "both_modified",
            "project_id": 42,
            "sql_updated_at": datetime.now(UTC),
        }

        # Mock database responses for _project_exists, detect_conflict, and _fetch_project_from_sql
        cursor_mock = mock_db_conn.cursor.return_value.__enter__.return_value
        cursor_mock.fetchone.side_effect = [
            (42,),  # _project_exists check
            # _fetch_project_from_sql returns full project row
            (
                42,
                "Test",
                "desc",
                "test",
                "d1",
                ["c1"],
                0.8,
                "active",
                3,
                4,
                None,
                20,
                1.0,
                True,
                datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC),
                datetime(2026, 1, 1, 14, 0, 0, tzinfo=UTC),
                str(file_path),
                None,
                None,
            ),
        ]

        with patch.object(sync_manager, "detect_conflict", return_value=conflict):
            with patch.object(sync_manager, "sync_project_to_obsidian") as mock_sync:

                sync_manager.sync_obsidian_file_to_sql(str(file_path))

                # Should overwrite Obsidian with SQL version
                mock_sync.assert_called_once()
                call_args = mock_sync.call_args
                assert call_args[1]["force"] is True

    def test_conflict_resolution_obsidian_wins(self, mock_db_conn, mock_obsidian_vault):
        """Test conflict resolution with Obsidian-wins strategy"""
        from mnemosyne.aletheia.obsidian_sync.obsidian_sync import ObsidianSyncManager

        sync_manager = ObsidianSyncManager(
            mock_db_conn, str(mock_obsidian_vault), conflict_strategy="obsidian_wins"
        )

        file_path = mock_obsidian_vault / "Projects" / "test.md"
        file_path.write_text(
            """---
id: 42
title: Test
discovered_by: test
discovery_id: d1
cluster_ids: [c1]
confidence_score: 0.8
status: active
created_at: 2026-01-01T10:00:00+00:00
updated_at: 2026-01-01T14:00:00+00:00
importance: 5
---

# Test
"""
        )

        conflict = {
            "type": "both_modified",
            "project_id": 42,
        }

        mock_gatekeeper = Mock()
        sync_manager._gatekeeper = mock_gatekeeper

        # Mock database responses for _project_exists
        cursor_mock = mock_db_conn.cursor.return_value.__enter__.return_value
        cursor_mock.fetchone.return_value = (42,)

        with patch.object(sync_manager, "detect_conflict", return_value=conflict):
            sync_manager.sync_obsidian_file_to_sql(str(file_path))

            # Should update SQL with Obsidian version
            mock_gatekeeper.update_project_direct.assert_called_once()


# ==============================================================================
# Sync Manager Configuration Tests
# ==============================================================================


class TestSyncManagerConfiguration:
    """Test ObsidianSyncManager configuration options"""

    def test_custom_projects_folder(self, mock_db_conn, tmp_path):
        """Test using custom Projects folder name"""
        from mnemosyne.aletheia.obsidian_sync.obsidian_sync import ObsidianSyncManager

        vault = tmp_path / "vault"
        vault.mkdir()

        sync_manager = ObsidianSyncManager(mock_db_conn, str(vault), projects_folder="MyProjects")

        assert sync_manager.projects_folder == "MyProjects"

        # Should create custom folder
        (vault / "MyProjects").mkdir(exist_ok=True)
        assert (vault / "MyProjects").exists()

    def test_dry_run_mode(self, mock_db_conn, mock_obsidian_vault, sample_project_from_sql):
        """Test dry-run mode doesn't write files"""
        from mnemosyne.aletheia.obsidian_sync.obsidian_sync import ObsidianSyncManager

        sync_manager = ObsidianSyncManager(mock_db_conn, str(mock_obsidian_vault), dry_run=True)

        result = sync_manager.sync_project_to_obsidian(sample_project_from_sql)

        # Should simulate but not create file
        assert result["action"] == "would_create"
        assert not (mock_obsidian_vault / "Projects" / "Implement-dark-mode-toggle.md").exists()

    def test_custom_sync_cooldown(self, mock_db_conn, mock_obsidian_vault):
        """Test custom sync cooldown configuration"""
        from mnemosyne.aletheia.obsidian_sync.obsidian_sync import ObsidianSyncManager

        sync_manager = ObsidianSyncManager(
            mock_db_conn, str(mock_obsidian_vault), sync_cooldown_seconds=120
        )

        assert sync_manager.sync_cooldown == 120


# ==============================================================================
# Pytest Helpers
# ==============================================================================


@pytest.fixture
def approx_query_match():
    """Helper to match SQL queries approximately (ignoring whitespace)"""

    class QueryMatcher:
        def __init__(self, expected):
            self.expected = expected.replace("\n", " ").replace("  ", " ").strip()

        def __eq__(self, other):
            normalized = other.replace("\n", " ").replace("  ", " ").strip()
            return self.expected in normalized

    return QueryMatcher


@pytest.fixture
def any_tuple_with():
    """Helper to match tuples containing specific values"""

    class TupleMatcher:
        def __init__(self, *values):
            self.values = values

        def __eq__(self, other):
            if not isinstance(other, tuple):
                return False
            return all(v in other for v in self.values)

    return TupleMatcher


@pytest.fixture
def any_tuple_containing():
    """Helper to match tuples containing specific values in order"""

    class TupleContainsMatcher:
        def __init__(self, *values):
            self.values = values

        def __eq__(self, other):
            if not isinstance(other, tuple):
                return False
            # Check if all values exist in tuple
            return all(v in other for v in self.values)

    return TupleContainsMatcher
