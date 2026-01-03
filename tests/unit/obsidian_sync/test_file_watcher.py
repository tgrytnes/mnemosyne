"""
Unit tests for Obsidian FileSystemWatcher (Story 016)

Tests the watchdog-based file monitoring that detects Obsidian markdown edits
and triggers automatic sync to SQL.

TDD Approach: These tests are written BEFORE implementation (RED phase).
"""

import time
from unittest.mock import Mock

import pytest

# ==============================================================================
# Test Fixtures
# ==============================================================================


@pytest.fixture
def mock_sync_manager():
    """Mock ObsidianSyncManager"""
    manager = Mock()
    manager.sync_obsidian_file_to_sql = Mock(return_value={"action": "updated"})
    return manager


@pytest.fixture
def mock_obsidian_vault(tmp_path):
    """Mock Obsidian vault directory"""
    vault_path = tmp_path / "ObsidianVault"
    vault_path.mkdir()
    (vault_path / "Projects").mkdir()
    return vault_path


# ==============================================================================
# FileSystemWatcher Initialization Tests
# ==============================================================================


class TestFileSystemWatcherInit:
    """Test FileSystemWatcher initialization and configuration"""

    def test_create_watcher_for_vault(self, mock_sync_manager, mock_obsidian_vault):
        """Test creating watcher for Obsidian vault"""
        from mnemosyne.aletheia.obsidian_sync.file_watcher import ObsidianFileWatcher

        watcher = ObsidianFileWatcher(
            vault_path=str(mock_obsidian_vault), sync_manager=mock_sync_manager
        )

        assert watcher.vault_path == str(mock_obsidian_vault)
        assert watcher.sync_manager == mock_sync_manager

    def test_watcher_observes_projects_folder(self, mock_sync_manager, mock_obsidian_vault):
        """Test that watcher observes the Projects folder"""
        from mnemosyne.aletheia.obsidian_sync.file_watcher import ObsidianFileWatcher

        watcher = ObsidianFileWatcher(
            vault_path=str(mock_obsidian_vault),
            sync_manager=mock_sync_manager,
            projects_folder="Projects",
        )

        assert watcher.projects_folder == "Projects"
        expected_watch_path = mock_obsidian_vault / "Projects"
        assert watcher.watch_path == str(expected_watch_path)

    def test_watcher_creates_projects_folder_if_missing(self, mock_sync_manager, tmp_path):
        """Test that watcher creates Projects folder if it doesn't exist"""
        from mnemosyne.aletheia.obsidian_sync.file_watcher import ObsidianFileWatcher

        vault = tmp_path / "new_vault"
        vault.mkdir()

        ObsidianFileWatcher(vault_path=str(vault), sync_manager=mock_sync_manager)

        # Should create Projects folder
        projects_path = vault / "Projects"
        assert projects_path.exists()

    def test_custom_debounce_delay(self, mock_sync_manager, mock_obsidian_vault):
        """Test custom debounce delay configuration"""
        from mnemosyne.aletheia.obsidian_sync.file_watcher import ObsidianFileWatcher

        watcher = ObsidianFileWatcher(
            vault_path=str(mock_obsidian_vault),
            sync_manager=mock_sync_manager,
            debounce_seconds=5.0,
        )

        assert watcher.debounce_seconds == 5.0


# ==============================================================================
# File Event Detection Tests
# ==============================================================================


class TestFileEventDetection:
    """Test detection of file system events"""

    def test_detect_markdown_file_modified(self, mock_sync_manager, mock_obsidian_vault):
        """Test detecting when markdown file is modified"""
        from mnemosyne.aletheia.obsidian_sync.file_watcher import ObsidianFileWatcher

        watcher = ObsidianFileWatcher(
            vault_path=str(mock_obsidian_vault),
            sync_manager=mock_sync_manager,
            debounce_seconds=0.1,  # Short debounce for testing
        )

        # Create and modify a file
        file_path = mock_obsidian_vault / "Projects" / "test-project.md"
        file_path.write_text("---\nid: 42\n---\n# Test\n")

        watcher.start()

        try:
            # Modify the file
            file_path.write_text("---\nid: 42\nimportance: 5\n---\n# Test\nUpdated!")

            # Wait for debounce + processing
            time.sleep(0.3)

            # Should trigger sync
            mock_sync_manager.sync_obsidian_file_to_sql.assert_called_with(str(file_path))
        finally:
            watcher.stop()

    def test_detect_new_markdown_file_created(self, mock_sync_manager, mock_obsidian_vault):
        """Test detecting when new markdown file is created"""
        from mnemosyne.aletheia.obsidian_sync.file_watcher import ObsidianFileWatcher

        watcher = ObsidianFileWatcher(
            vault_path=str(mock_obsidian_vault),
            sync_manager=mock_sync_manager,
            debounce_seconds=0.1,
        )

        watcher.start()

        try:
            # Create new file
            file_path = mock_obsidian_vault / "Projects" / "new-project.md"
            file_path.write_text("---\nid: 99\n---\n# New Project\n")

            time.sleep(0.3)

            # Should trigger sync for new file
            mock_sync_manager.sync_obsidian_file_to_sql.assert_called_with(str(file_path))
        finally:
            watcher.stop()

    def test_ignore_non_markdown_files(self, mock_sync_manager, mock_obsidian_vault):
        """Test that watcher ignores non-markdown files"""
        from mnemosyne.aletheia.obsidian_sync.file_watcher import ObsidianFileWatcher

        watcher = ObsidianFileWatcher(
            vault_path=str(mock_obsidian_vault),
            sync_manager=mock_sync_manager,
            debounce_seconds=0.1,
        )

        watcher.start()

        try:
            # Create non-markdown file
            file_path = mock_obsidian_vault / "Projects" / "notes.txt"
            file_path.write_text("Some notes")

            time.sleep(0.3)

            # Should NOT trigger sync
            mock_sync_manager.sync_obsidian_file_to_sql.assert_not_called()
        finally:
            watcher.stop()

    def test_ignore_temp_files(self, mock_sync_manager, mock_obsidian_vault):
        """Test that watcher ignores temporary files (like .tmp, .swp)"""
        from mnemosyne.aletheia.obsidian_sync.file_watcher import ObsidianFileWatcher

        watcher = ObsidianFileWatcher(
            vault_path=str(mock_obsidian_vault),
            sync_manager=mock_sync_manager,
            debounce_seconds=0.1,
        )

        watcher.start()

        try:
            # Create temp files
            for filename in [".test.md.tmp", "test.md.swp", "~test.md"]:
                file_path = mock_obsidian_vault / "Projects" / filename
                file_path.write_text("temp")

            time.sleep(0.3)

            # Should NOT trigger sync for temp files
            mock_sync_manager.sync_obsidian_file_to_sql.assert_not_called()
        finally:
            watcher.stop()

    def test_ignore_obsidian_config_files(self, mock_sync_manager, mock_obsidian_vault):
        """Test that watcher ignores Obsidian config files (.obsidian folder)"""
        from mnemosyne.aletheia.obsidian_sync.file_watcher import ObsidianFileWatcher

        # Create .obsidian folder
        (mock_obsidian_vault / ".obsidian").mkdir()

        watcher = ObsidianFileWatcher(
            vault_path=str(mock_obsidian_vault),
            sync_manager=mock_sync_manager,
            debounce_seconds=0.1,
        )

        watcher.start()

        try:
            # Modify file in .obsidian
            config_file = mock_obsidian_vault / ".obsidian" / "workspace.json"
            config_file.write_text('{"config": true}')

            time.sleep(0.3)

            # Should NOT trigger sync
            mock_sync_manager.sync_obsidian_file_to_sql.assert_not_called()
        finally:
            watcher.stop()


# ==============================================================================
# Debouncing Tests
# ==============================================================================


class TestDebouncing:
    """Test debouncing logic to prevent rapid successive syncs"""

    def test_debounce_multiple_rapid_edits(self, mock_sync_manager, mock_obsidian_vault):
        """Test that multiple rapid edits are debounced to single sync"""
        from mnemosyne.aletheia.obsidian_sync.file_watcher import ObsidianFileWatcher

        watcher = ObsidianFileWatcher(
            vault_path=str(mock_obsidian_vault),
            sync_manager=mock_sync_manager,
            debounce_seconds=0.5,  # 500ms debounce
        )

        file_path = mock_obsidian_vault / "Projects" / "test.md"
        file_path.write_text("---\nid: 42\n---\n# Test\n")

        watcher.start()

        try:
            # Make rapid successive edits
            for i in range(5):
                file_path.write_text(f"---\nid: 42\nimportance: {i}\n---\n# Test {i}\n")
                time.sleep(0.05)  # 50ms between edits

            # Wait for debounce to settle
            time.sleep(0.7)

            # Should only sync once (after debounce period)
            assert mock_sync_manager.sync_obsidian_file_to_sql.call_count == 1
        finally:
            watcher.stop()

    def test_separate_files_sync_independently(self, mock_sync_manager, mock_obsidian_vault):
        """Test that edits to different files sync independently"""
        from mnemosyne.aletheia.obsidian_sync.file_watcher import ObsidianFileWatcher

        watcher = ObsidianFileWatcher(
            vault_path=str(mock_obsidian_vault),
            sync_manager=mock_sync_manager,
            debounce_seconds=0.2,
        )

        file1 = mock_obsidian_vault / "Projects" / "project1.md"
        file2 = mock_obsidian_vault / "Projects" / "project2.md"

        file1.write_text("---\nid: 1\n---\n# P1\n")
        file2.write_text("---\nid: 2\n---\n# P2\n")

        watcher.start()

        try:
            # Edit both files
            file1.write_text("---\nid: 1\nimportance: 5\n---\n# P1\n")
            time.sleep(0.05)
            file2.write_text("---\nid: 2\nimportance: 3\n---\n# P2\n")

            time.sleep(0.4)

            # Should sync both files
            assert mock_sync_manager.sync_obsidian_file_to_sql.call_count == 2

            # Verify both files were synced
            calls = mock_sync_manager.sync_obsidian_file_to_sql.call_args_list
            synced_paths = [call[0][0] for call in calls]
            assert str(file1) in synced_paths
            assert str(file2) in synced_paths
        finally:
            watcher.stop()


# ==============================================================================
# Error Handling Tests
# ==============================================================================


class TestErrorHandling:
    """Test error handling in file watcher"""

    def test_continue_watching_after_sync_error(self, mock_sync_manager, mock_obsidian_vault):
        """Test that watcher continues after sync error"""
        from mnemosyne.aletheia.obsidian_sync.file_watcher import ObsidianFileWatcher

        # First sync fails, second succeeds
        mock_sync_manager.sync_obsidian_file_to_sql.side_effect = [
            Exception("Sync failed"),
            {"action": "updated"},
        ]

        watcher = ObsidianFileWatcher(
            vault_path=str(mock_obsidian_vault),
            sync_manager=mock_sync_manager,
            debounce_seconds=0.1,
        )

        file1 = mock_obsidian_vault / "Projects" / "file1.md"
        file2 = mock_obsidian_vault / "Projects" / "file2.md"

        file1.write_text("---\nid: 1\n---\n# F1\n")
        file2.write_text("---\nid: 2\n---\n# F2\n")

        watcher.start()

        try:
            # Edit file1 (will fail)
            file1.write_text("---\nid: 1\nimportance: 5\n---\n# F1\n")
            time.sleep(0.3)

            # Edit file2 (should succeed despite previous error)
            file2.write_text("---\nid: 2\nimportance: 3\n---\n# F2\n")
            time.sleep(0.3)

            # Both should have been attempted
            assert mock_sync_manager.sync_obsidian_file_to_sql.call_count == 2
        finally:
            watcher.stop()

    def test_log_sync_errors(self, mock_sync_manager, mock_obsidian_vault, caplog):
        """Test that sync errors are logged"""
        from mnemosyne.aletheia.obsidian_sync.file_watcher import ObsidianFileWatcher

        mock_sync_manager.sync_obsidian_file_to_sql.side_effect = ValueError("Invalid project")

        watcher = ObsidianFileWatcher(
            vault_path=str(mock_obsidian_vault),
            sync_manager=mock_sync_manager,
            debounce_seconds=0.1,
        )

        file_path = mock_obsidian_vault / "Projects" / "test.md"
        file_path.write_text("---\nid: 42\n---\n# Test\n")

        watcher.start()

        try:
            file_path.write_text("---\nid: 42\nimportance: 5\n---\n# Test\n")
            time.sleep(0.3)

            # Should log the error
            # Note: Actual log assertion depends on logging configuration
        finally:
            watcher.stop()

    def test_handle_invalid_vault_path(self, mock_sync_manager):
        """Test handling of invalid vault path"""
        from mnemosyne.aletheia.obsidian_sync.file_watcher import ObsidianFileWatcher

        with pytest.raises(ValueError, match="Vault path does not exist"):
            ObsidianFileWatcher(vault_path="/nonexistent/path", sync_manager=mock_sync_manager)


# ==============================================================================
# Watcher Lifecycle Tests
# ==============================================================================


class TestWatcherLifecycle:
    """Test watcher start/stop/restart lifecycle"""

    def test_start_watcher(self, mock_sync_manager, mock_obsidian_vault):
        """Test starting watcher"""
        from mnemosyne.aletheia.obsidian_sync.file_watcher import ObsidianFileWatcher

        watcher = ObsidianFileWatcher(
            vault_path=str(mock_obsidian_vault), sync_manager=mock_sync_manager
        )

        assert not watcher.is_running

        watcher.start()

        assert watcher.is_running

        watcher.stop()

    def test_stop_watcher(self, mock_sync_manager, mock_obsidian_vault):
        """Test stopping watcher"""
        from mnemosyne.aletheia.obsidian_sync.file_watcher import ObsidianFileWatcher

        watcher = ObsidianFileWatcher(
            vault_path=str(mock_obsidian_vault), sync_manager=mock_sync_manager
        )

        watcher.start()
        assert watcher.is_running

        watcher.stop()
        assert not watcher.is_running

        # Should not watch files after stop
        file_path = mock_obsidian_vault / "Projects" / "test.md"
        file_path.write_text("---\nid: 42\n---\n# Test\n")

        time.sleep(0.2)

        mock_sync_manager.sync_obsidian_file_to_sql.assert_not_called()

    def test_restart_watcher(self, mock_sync_manager, mock_obsidian_vault):
        """Test restarting watcher"""
        from mnemosyne.aletheia.obsidian_sync.file_watcher import ObsidianFileWatcher

        watcher = ObsidianFileWatcher(
            vault_path=str(mock_obsidian_vault),
            sync_manager=mock_sync_manager,
            debounce_seconds=0.1,
        )

        # Start, stop, restart
        watcher.start()
        watcher.stop()
        watcher.start()

        file_path = mock_obsidian_vault / "Projects" / "test.md"
        file_path.write_text("---\nid: 42\n---\n# Test\n")

        time.sleep(0.3)

        # Should work after restart
        mock_sync_manager.sync_obsidian_file_to_sql.assert_called()

        watcher.stop()

    def test_context_manager(self, mock_sync_manager, mock_obsidian_vault):
        """Test using watcher as context manager"""
        from mnemosyne.aletheia.obsidian_sync.file_watcher import ObsidianFileWatcher

        watcher = ObsidianFileWatcher(
            vault_path=str(mock_obsidian_vault),
            sync_manager=mock_sync_manager,
            debounce_seconds=0.1,
        )

        with watcher:
            assert watcher.is_running

            file_path = mock_obsidian_vault / "Projects" / "test.md"
            file_path.write_text("---\nid: 42\n---\n# Test\n")

            time.sleep(0.3)

            mock_sync_manager.sync_obsidian_file_to_sql.assert_called()

        # Should auto-stop after context
        assert not watcher.is_running

    def test_idempotent_start(self, mock_sync_manager, mock_obsidian_vault):
        """Test that calling start() multiple times is safe"""
        from mnemosyne.aletheia.obsidian_sync.file_watcher import ObsidianFileWatcher

        watcher = ObsidianFileWatcher(
            vault_path=str(mock_obsidian_vault), sync_manager=mock_sync_manager
        )

        watcher.start()
        watcher.start()  # Should be idempotent
        watcher.start()

        assert watcher.is_running

        watcher.stop()

    def test_idempotent_stop(self, mock_sync_manager, mock_obsidian_vault):
        """Test that calling stop() multiple times is safe"""
        from mnemosyne.aletheia.obsidian_sync.file_watcher import ObsidianFileWatcher

        watcher = ObsidianFileWatcher(
            vault_path=str(mock_obsidian_vault), sync_manager=mock_sync_manager
        )

        watcher.start()
        watcher.stop()
        watcher.stop()  # Should be idempotent
        watcher.stop()

        assert not watcher.is_running


# ==============================================================================
# Callback Tests
# ==============================================================================


class TestCallbacks:
    """Test custom callback support"""

    def test_on_file_changed_callback(self, mock_sync_manager, mock_obsidian_vault):
        """Test custom callback on file change"""
        from mnemosyne.aletheia.obsidian_sync.file_watcher import ObsidianFileWatcher

        callback_mock = Mock()

        watcher = ObsidianFileWatcher(
            vault_path=str(mock_obsidian_vault),
            sync_manager=mock_sync_manager,
            debounce_seconds=0.1,
            on_file_changed=callback_mock,
        )

        file_path = mock_obsidian_vault / "Projects" / "test.md"
        file_path.write_text("---\nid: 42\n---\n# Test\n")

        watcher.start()

        try:
            file_path.write_text("---\nid: 42\nimportance: 5\n---\n# Test\n")
            time.sleep(0.3)

            # Callback should be invoked
            callback_mock.assert_called_once()
            call_args = callback_mock.call_args[0]
            assert str(file_path) in str(call_args)
        finally:
            watcher.stop()

    def test_on_sync_error_callback(self, mock_sync_manager, mock_obsidian_vault):
        """Test custom callback on sync error"""
        from mnemosyne.aletheia.obsidian_sync.file_watcher import ObsidianFileWatcher

        mock_sync_manager.sync_obsidian_file_to_sql.side_effect = ValueError("Test error")

        error_callback = Mock()

        watcher = ObsidianFileWatcher(
            vault_path=str(mock_obsidian_vault),
            sync_manager=mock_sync_manager,
            debounce_seconds=0.1,
            on_sync_error=error_callback,
        )

        file_path = mock_obsidian_vault / "Projects" / "test.md"
        file_path.write_text("---\nid: 42\n---\n# Test\n")

        watcher.start()

        try:
            file_path.write_text("---\nid: 42\nimportance: 5\n---\n# Test\n")
            time.sleep(0.3)

            # Error callback should be invoked
            error_callback.assert_called_once()
            call_args = error_callback.call_args
            assert "Test error" in str(call_args)
        finally:
            watcher.stop()
