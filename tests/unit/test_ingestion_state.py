"""
Unit tests for ingestion state tracking.

Tests the IngestionStateTracker class which uses SQLite to track
which files have been ingested and when they were last modified.
"""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.mnemosyne.aletheia.ingestion_state import IngestionStateTracker


class TestIngestionStateTracker:
    """Test SQLite-based ingestion state tracking"""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        # Cleanup
        Path(db_path).unlink(missing_ok=True)

    @pytest.fixture
    def tracker(self, temp_db):
        """Create state tracker with temp database"""
        return IngestionStateTracker(temp_db)

    def test_create_database(self, temp_db):
        """Should create database file on initialization"""
        # GIVEN/WHEN: Creating state tracker
        IngestionStateTracker(temp_db)

        # THEN: Database file exists
        assert Path(temp_db).exists()

    def test_create_table(self, tracker):
        """Should create ingested_files table"""
        # GIVEN/WHEN: Tracker initialized
        # THEN: Can query the table (won't raise error)
        results = tracker.get_all_files()
        assert results == []

    def test_mark_file_ingested(self, tracker):
        """Should record ingested file with metadata"""
        # GIVEN: File metadata
        file_path = "/vault/note.md"
        modified_time = datetime.now()
        chunk_count = 5

        # WHEN: Marking file as ingested
        tracker.mark_ingested(file_path, modified_time, chunk_count)

        # THEN: File is recorded
        assert tracker.is_ingested(file_path, modified_time)

    def test_not_ingested_returns_false(self, tracker):
        """Should return False for files not yet ingested"""
        # GIVEN: File not in database
        file_path = "/vault/new_note.md"
        modified_time = datetime.now()

        # WHEN/THEN: File is not ingested
        assert not tracker.is_ingested(file_path, modified_time)

    def test_detect_modified_file(self, tracker):
        """Should detect when file has been modified since ingestion"""
        # GIVEN: File ingested at an earlier time
        file_path = "/vault/note.md"
        old_modified_time = datetime.now() - timedelta(hours=2)
        new_modified_time = datetime.now()

        tracker.mark_ingested(file_path, old_modified_time, 5)

        # WHEN: Checking with newer modification time
        # THEN: File is NOT considered ingested (needs re-ingestion)
        assert not tracker.is_ingested(file_path, new_modified_time)

    def test_same_modification_time_is_ingested(self, tracker):
        """Should skip re-ingestion if modification time unchanged"""
        # GIVEN: File already ingested
        file_path = "/vault/note.md"
        modified_time = datetime.now()
        tracker.mark_ingested(file_path, modified_time, 5)

        # WHEN: Checking with same modification time
        # THEN: File is still considered ingested
        assert tracker.is_ingested(file_path, modified_time)

    def test_get_file_info(self, tracker):
        """Should retrieve ingestion metadata"""
        # GIVEN: Ingested file
        file_path = "/vault/note.md"
        modified_time = datetime.now()
        chunk_count = 10

        tracker.mark_ingested(file_path, modified_time, chunk_count)

        # WHEN: Getting file info
        info = tracker.get_file_info(file_path)

        # THEN: Returns correct metadata
        assert info is not None
        assert info["file_path"] == file_path
        assert info["chunk_count"] == chunk_count

    def test_get_file_info_missing_file(self, tracker):
        """Should return None for missing file"""
        # GIVEN: File not in database
        file_path = "/vault/missing.md"

        # WHEN: Getting file info
        info = tracker.get_file_info(file_path)

        # THEN: Returns None
        assert info is None

    def test_get_all_files(self, tracker):
        """Should list all ingested files"""
        # GIVEN: Multiple ingested files
        files = [
            ("/vault/note1.md", datetime.now(), 5),
            ("/vault/note2.md", datetime.now(), 8),
            ("/vault/note3.md", datetime.now(), 3),
        ]

        for file_path, mod_time, chunks in files:
            tracker.mark_ingested(file_path, mod_time, chunks)

        # WHEN: Getting all files
        all_files = tracker.get_all_files()

        # THEN: Returns all file paths
        assert len(all_files) == 3
        file_paths = [f["file_path"] for f in all_files]
        assert "/vault/note1.md" in file_paths
        assert "/vault/note2.md" in file_paths
        assert "/vault/note3.md" in file_paths

    def test_update_existing_file(self, tracker):
        """Should update record when file is re-ingested"""
        # GIVEN: File already ingested
        file_path = "/vault/note.md"
        old_time = datetime.now() - timedelta(hours=1)
        new_time = datetime.now()

        tracker.mark_ingested(file_path, old_time, 5)

        # WHEN: Re-ingesting with new modification time
        tracker.mark_ingested(file_path, new_time, 7)

        # THEN: Record is updated
        info = tracker.get_file_info(file_path)
        assert info["chunk_count"] == 7
        assert tracker.is_ingested(file_path, new_time)

    def test_count_total_chunks(self, tracker):
        """Should count total chunks across all files"""
        # GIVEN: Multiple files with different chunk counts
        tracker.mark_ingested("/vault/note1.md", datetime.now(), 5)
        tracker.mark_ingested("/vault/note2.md", datetime.now(), 8)
        tracker.mark_ingested("/vault/note3.md", datetime.now(), 3)

        # WHEN: Getting total chunk count
        total = tracker.get_total_chunk_count()

        # THEN: Returns sum of all chunks
        assert total == 16  # 5 + 8 + 3

    def test_get_files_needing_update(self, tracker):
        """Should identify files that need re-ingestion"""
        # GIVEN: Files with different modification times
        old_time = datetime.now() - timedelta(days=1)
        current_time = datetime.now()

        tracker.mark_ingested("/vault/old.md", old_time, 5)
        tracker.mark_ingested("/vault/current.md", current_time, 5)

        # WHEN: Checking which files need updates
        # File system shows "old.md" has been modified
        actual_files = {
            "/vault/old.md": current_time,  # Modified since ingestion
            "/vault/current.md": current_time,  # Same modification time
        }

        needs_update = [
            path
            for path, mod_time in actual_files.items()
            if not tracker.is_ingested(path, mod_time)
        ]

        # THEN: Only old.md needs update
        assert "/vault/old.md" in needs_update
        assert "/vault/current.md" not in needs_update

    def test_persistent_state(self, temp_db):
        """Should persist state across tracker instances"""
        # GIVEN: File ingested with first tracker
        tracker1 = IngestionStateTracker(temp_db)
        file_path = "/vault/note.md"
        modified_time = datetime.now()

        tracker1.mark_ingested(file_path, modified_time, 5)

        # WHEN: Creating new tracker with same database
        tracker2 = IngestionStateTracker(temp_db)

        # THEN: State is preserved
        assert tracker2.is_ingested(file_path, modified_time)

    def test_delete_file_record(self, tracker):
        """Should remove file from tracking"""
        # GIVEN: Ingested file
        file_path = "/vault/note.md"
        tracker.mark_ingested(file_path, datetime.now(), 5)

        # WHEN: Deleting the record
        tracker.delete_file(file_path)

        # THEN: File is no longer tracked
        assert tracker.get_file_info(file_path) is None

    def test_clear_all_state(self, tracker):
        """Should remove all ingestion records"""
        # GIVEN: Multiple ingested files
        tracker.mark_ingested("/vault/note1.md", datetime.now(), 5)
        tracker.mark_ingested("/vault/note2.md", datetime.now(), 8)

        # WHEN: Clearing all state
        tracker.clear_all()

        # THEN: No files tracked
        assert tracker.get_all_files() == []
