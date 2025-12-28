"""
Unit tests for VaultWatcher.

Tests vault monitoring, file event handling, and debouncing.
"""

import tempfile
import time
from pathlib import Path

import pytest
from watchdog.events import DirCreatedEvent, FileCreatedEvent, FileModifiedEvent

from src.mnemosyne.aletheia.vault_watcher import VaultEventHandler, VaultWatcher


@pytest.mark.unit
class TestVaultEventHandler:
    """Test vault event handler"""

    @pytest.fixture
    def callback_recorder(self):
        """Collect callback invocations for assertions."""
        calls = []

        def on_change(path):
            calls.append(path)

        return calls, on_change

    @pytest.fixture
    def event_handler(self, callback_recorder):
        """Create event handler with real callback"""
        _, on_change = callback_recorder
        return VaultEventHandler(on_file_change=on_change, debounce_seconds=0.1)

    def test_initialization(self, event_handler, callback_recorder):
        """Should initialize with callback and debounce settings"""
        # THEN: Handler has correct configuration
        _, on_change = callback_recorder
        assert event_handler.on_file_change == on_change
        assert event_handler.debounce_seconds == 0.1
        assert event_handler._last_processed == {}

    def test_is_markdown_file(self, event_handler):
        """Should correctly identify markdown files"""
        # THEN: Identifies .md files
        assert event_handler._is_markdown_file("test.md")
        assert event_handler._is_markdown_file("/path/to/note.md")
        assert not event_handler._is_markdown_file("test.txt")
        assert not event_handler._is_markdown_file("test.pdf")

    def test_is_temp_file(self, event_handler):
        """Should correctly identify temporary files"""
        # THEN: Identifies temp files
        assert event_handler._is_temp_file(".hidden.md")
        assert event_handler._is_temp_file("test.tmp")
        assert event_handler._is_temp_file("test~")
        assert event_handler._is_temp_file("/vault/.obsidian/workspace")
        assert not event_handler._is_temp_file("normal.md")

    def test_on_created_markdown_file(self, event_handler, callback_recorder):
        """Should trigger callback for new markdown files"""
        # GIVEN: File created event
        event = FileCreatedEvent("/vault/new_note.md")

        # WHEN: Processing event
        event_handler.on_created(event)

        # THEN: Callback invoked
        calls, _ = callback_recorder
        assert calls == ["/vault/new_note.md"]

    def test_on_created_ignores_non_markdown(self, event_handler, callback_recorder):
        """Should ignore non-markdown files"""
        # GIVEN: Non-markdown file event
        event = FileCreatedEvent("/vault/file.txt")

        # WHEN: Processing event
        event_handler.on_created(event)

        # THEN: Callback not invoked
        calls, _ = callback_recorder
        assert calls == []

    def test_on_created_ignores_directories(self, event_handler, callback_recorder):
        """Should ignore directory events"""
        # GIVEN: Directory event
        event = DirCreatedEvent("/vault/folder")

        # WHEN: Processing event
        event_handler.on_created(event)

        # THEN: Callback not invoked
        calls, _ = callback_recorder
        assert calls == []

    def test_on_created_ignores_temp_files(self, event_handler, callback_recorder):
        """Should ignore temporary files"""
        # GIVEN: Temp file event
        event = FileCreatedEvent("/vault/.hidden.md")

        # WHEN: Processing event
        event_handler.on_created(event)

        # THEN: Callback not invoked
        calls, _ = callback_recorder
        assert calls == []

    def test_on_modified_markdown_file(self, event_handler, callback_recorder):
        """Should trigger callback for modified markdown files"""
        # GIVEN: File modified event
        event = FileModifiedEvent("/vault/note.md")

        # WHEN: Processing event
        event_handler.on_modified(event)

        # THEN: Callback invoked
        calls, _ = callback_recorder
        assert calls == ["/vault/note.md"]

    def test_debouncing_prevents_duplicate_events(self, event_handler, callback_recorder):
        """Should debounce rapid duplicate events"""
        # GIVEN: Same file modified twice in quick succession
        event = FileModifiedEvent("/vault/note.md")

        # WHEN: Processing first event
        event_handler.on_modified(event)

        # WHEN: Processing second event immediately
        event_handler.on_modified(event)

        # THEN: Callback called only once (second event debounced)
        calls, _ = callback_recorder
        assert len(calls) == 1

    def test_debouncing_allows_after_delay(self, event_handler, callback_recorder):
        """Should allow processing after debounce period"""
        # GIVEN: Same file modified twice with delay
        event = FileModifiedEvent("/vault/note.md")

        # WHEN: Processing first event
        event_handler.on_modified(event)

        # WHEN: Waiting for debounce period
        time.sleep(0.15)  # Longer than 0.1s debounce

        # WHEN: Processing second event
        event_handler.on_modified(event)

        # THEN: Callback called twice
        calls, _ = callback_recorder
        assert len(calls) == 2

    def test_error_handling_in_callback(self, event_handler):
        """Should handle errors in callback gracefully"""

        # GIVEN: Callback that raises error
        def failing_callback(path):
            raise ValueError("Test error")

        event_handler.on_file_change = failing_callback

        event = FileCreatedEvent("/vault/note.md")

        # WHEN/THEN: Processing event should not crash
        event_handler.on_created(event)  # Should log error but not raise


@pytest.mark.unit
class TestVaultWatcher:
    """Test vault watcher"""

    @pytest.fixture
    def temp_vault(self):
        """Create temporary vault directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def callback_recorder(self):
        """Collect callback invocations for assertions."""
        calls = []

        def on_change(path):
            calls.append(path)

        return calls, on_change

    def test_initialization(self, temp_vault, callback_recorder):
        """Should initialize with valid vault path"""
        # WHEN: Creating watcher
        _, on_change = callback_recorder
        watcher = VaultWatcher(vault_path=temp_vault, on_file_change=on_change)

        # THEN: Watcher configured correctly
        assert watcher.vault_path == Path(temp_vault)
        assert watcher.on_file_change == on_change
        assert watcher.debounce_seconds == 2.0
        assert not watcher.is_running()

    def test_initialization_with_invalid_path(self, callback_recorder):
        """Should raise error for nonexistent vault path"""
        _, on_change = callback_recorder
        # WHEN/THEN: Creating watcher with invalid path
        with pytest.raises(ValueError, match="does not exist"):
            VaultWatcher(vault_path="/nonexistent/path", on_file_change=on_change)

    def test_initialization_with_file_path(self, temp_vault, callback_recorder):
        """Should raise error if vault path is a file"""
        _, on_change = callback_recorder
        # GIVEN: File instead of directory
        file_path = Path(temp_vault) / "test.md"
        file_path.write_text("test")

        # WHEN/THEN: Creating watcher with file path
        with pytest.raises(ValueError, match="not a directory"):
            VaultWatcher(vault_path=str(file_path), on_file_change=on_change)

    def test_start_watcher(self, temp_vault, callback_recorder):
        """Should start monitoring vault"""
        # GIVEN: Watcher
        _, on_change = callback_recorder
        watcher = VaultWatcher(temp_vault, on_change)

        # WHEN: Starting watcher
        watcher.start()

        try:
            # THEN: Watcher is running
            assert watcher.is_running()
            assert watcher.observer is not None

        finally:
            watcher.stop()

    def test_stop_watcher(self, temp_vault, callback_recorder):
        """Should stop monitoring vault"""
        # GIVEN: Running watcher
        _, on_change = callback_recorder
        watcher = VaultWatcher(temp_vault, on_change)
        watcher.start()

        # WHEN: Stopping watcher
        watcher.stop()

        # THEN: Watcher stopped
        assert not watcher.is_running()

    def test_start_already_running(self, temp_vault, callback_recorder):
        """Should handle starting already running watcher"""
        # GIVEN: Running watcher
        _, on_change = callback_recorder
        watcher = VaultWatcher(temp_vault, on_change)
        watcher.start()

        try:
            # WHEN: Starting again
            watcher.start()  # Should not crash

            # THEN: Still running
            assert watcher.is_running()

        finally:
            watcher.stop()

    def test_stop_not_running(self, temp_vault, callback_recorder):
        """Should handle stopping non-running watcher"""
        # GIVEN: Non-running watcher
        _, on_change = callback_recorder
        watcher = VaultWatcher(temp_vault, on_change)

        # WHEN: Stopping
        watcher.stop()  # Should not crash

        # THEN: Still not running
        assert not watcher.is_running()

    def test_detects_new_file(self, temp_vault, callback_recorder):
        """Should detect newly created markdown files"""
        # GIVEN: Running watcher
        calls, on_change = callback_recorder
        watcher = VaultWatcher(temp_vault, on_change, debounce_seconds=0.1)
        watcher.start()

        try:
            # WHEN: Creating new markdown file
            test_file = Path(temp_vault) / "new_note.md"
            test_file.write_text("# Test Note")

            # Wait for event to be processed
            time.sleep(0.5)

            # THEN: Callback was invoked with file path
            assert len(calls) >= 1
            # Check if our file path is in any of the calls
            called_paths = list(calls)
            assert str(test_file) in called_paths

        finally:
            watcher.stop()

    def test_detects_modified_file(self, temp_vault, callback_recorder):
        """Should detect modified markdown files"""
        # GIVEN: Existing file
        test_file = Path(temp_vault) / "note.md"
        test_file.write_text("# Original")

        # GIVEN: Running watcher
        calls, on_change = callback_recorder
        watcher = VaultWatcher(temp_vault, on_change, debounce_seconds=0.1)
        watcher.start()

        try:
            # Wait a bit to ensure watcher is ready
            time.sleep(0.2)

            # Reset calls to ignore any initial events
            calls.clear()

            # WHEN: Modifying file
            test_file.write_text("# Modified")

            # Wait for event to be processed
            time.sleep(0.5)

            # THEN: Callback was invoked
            assert len(calls) >= 1

        finally:
            watcher.stop()

    def test_ignores_non_markdown_files(self, temp_vault, callback_recorder):
        """Should ignore non-markdown files"""
        # GIVEN: Running watcher
        calls, on_change = callback_recorder
        watcher = VaultWatcher(temp_vault, on_change, debounce_seconds=0.1)
        watcher.start()

        try:
            # Reset recorded calls
            calls.clear()

            # WHEN: Creating non-markdown file
            test_file = Path(temp_vault) / "test.txt"
            test_file.write_text("Not markdown")

            # Wait
            time.sleep(0.5)

            # THEN: Callback not invoked for .txt file
            # Note: There might be other events, so we check the paths
            if calls:
                called_paths = list(calls)
                assert str(test_file) not in called_paths

        finally:
            watcher.stop()

    def test_custom_debounce_time(self, temp_vault, callback_recorder):
        """Should respect custom debounce time"""
        # GIVEN: Watcher with custom debounce
        _, on_change = callback_recorder
        watcher = VaultWatcher(temp_vault, on_change, debounce_seconds=5.0)

        # THEN: Debounce time set correctly
        assert watcher.debounce_seconds == 5.0
        assert watcher.event_handler.debounce_seconds == 5.0
