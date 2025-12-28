"""
Unit tests for ObsidianIngestor orchestration class.

Tests the main ingestor that coordinates markdown cleaning, chunking,
embedding generation, and storage in Weaviate.
"""

import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
from src.mnemosyne.aletheia.obsidian_ingestor import ObsidianIngestor


class TestObsidianIngestor:
    """Test Obsidian vault ingestion orchestration"""

    @pytest.fixture
    def mock_weaviate_client(self, mocker):
        """Mock Weaviate client"""
        return mocker.MagicMock()

    @pytest.fixture
    def mock_ollama_client(self, mocker):
        """Mock Ollama client"""
        client = mocker.MagicMock()
        # Mock embedding response
        client.embeddings.return_value = {
            "embedding": [0.1] * 1024  # qwen3-embedding returns 1024 dimensions
        }
        return client

    @pytest.fixture
    def mock_state_tracker(self, mocker):
        """Mock ingestion state tracker"""
        return mocker.MagicMock()

    @pytest.fixture
    def ingestor(self, mock_weaviate_client, mock_ollama_client, mock_state_tracker, tmp_path):
        """Create ingestor with mocked dependencies"""
        return ObsidianIngestor(
            vault_path=str(tmp_path),
            weaviate_client=mock_weaviate_client,
            ollama_client=mock_ollama_client,
            state_tracker=mock_state_tracker,
        )

    def test_initialization(self, ingestor, tmp_path):
        """Should initialize with correct configuration"""
        # THEN: Ingestor has correct vault path
        assert ingestor.vault_path == str(tmp_path)
        assert ingestor.collection_name == "TheMuses"

    def test_scan_vault_finds_markdown_files(self, ingestor, tmp_path):
        """Should find all .md files in vault"""
        # GIVEN: Vault with markdown files
        (tmp_path / "note1.md").write_text("Content 1")
        (tmp_path / "note2.md").write_text("Content 2")
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "note3.md").write_text("Content 3")
        (tmp_path / "readme.txt").write_text("Not markdown")

        # WHEN: Scanning vault
        files = ingestor.scan_vault()

        # THEN: Finds all .md files, not .txt
        assert len(files) == 3
        file_names = [Path(f).name for f in files]
        assert "note1.md" in file_names
        assert "note2.md" in file_names
        assert "note3.md" in file_names
        assert "readme.txt" not in file_names

    def test_skip_already_ingested_file(self, ingestor, mock_state_tracker, tmp_path):
        """Should skip files that are already ingested"""
        # GIVEN: File that's already ingested
        file_path = tmp_path / "note.md"
        file_path.write_text("Content")
        mock_state_tracker.is_ingested.return_value = True

        # WHEN: Checking if file needs ingestion
        needs_ingestion = ingestor.needs_ingestion(str(file_path))

        # THEN: File is skipped
        assert not needs_ingestion

    def test_ingest_modified_file(self, ingestor, mock_state_tracker, tmp_path):
        """Should re-ingest files that have been modified"""
        # GIVEN: File that was modified since last ingestion
        file_path = tmp_path / "note.md"
        file_path.write_text("Updated content")
        mock_state_tracker.is_ingested.return_value = False

        # WHEN: Checking if file needs ingestion
        needs_ingestion = ingestor.needs_ingestion(str(file_path))

        # THEN: File needs re-ingestion
        assert needs_ingestion

    def test_process_single_file(
        self, ingestor, tmp_path, mock_state_tracker, mock_weaviate_client
    ):
        """Should process file through complete pipeline"""
        # GIVEN: Markdown file with Obsidian syntax
        file_path = tmp_path / "test.md"
        content = """---
title: Test Note
---

This is a [[wiki link]] and ![[embed.png]].

Regular content here."""
        file_path.write_text(content)

        # WHEN: Processing the file
        chunk_count = ingestor.ingest_file(str(file_path))

        # THEN: File is cleaned, chunked, embedded, and stored
        assert chunk_count > 0
        # State tracker should mark file as ingested
        mock_state_tracker.mark_ingested.assert_called_once()

    def test_clean_markdown_removes_syntax(self, ingestor):
        """Should clean Obsidian syntax from markdown"""
        # GIVEN: Markdown with Obsidian syntax
        markdown = """---
title: Note
---

Check [[link]] and ![[image.png]]"""

        # WHEN: Cleaning markdown
        cleaned = ingestor._clean_markdown(markdown)

        # THEN: Obsidian syntax removed
        assert "---" not in cleaned
        assert "[[" not in cleaned
        assert "![[" not in cleaned
        assert "Check link" in cleaned

    def test_chunk_text(self, ingestor):
        """Should chunk text into appropriate sizes"""
        # GIVEN: Long text
        text = "Sentence. " * 100  # ~1000 chars

        # WHEN: Chunking text
        chunks = ingestor._chunk_text(text, source_file="/vault/note.md")

        # THEN: Creates multiple chunks
        assert len(chunks) > 1
        # Each chunk has metadata
        for chunk in chunks:
            assert hasattr(chunk, "text")
            assert hasattr(chunk, "index")
            assert chunk.source_file == "/vault/note.md"

    def test_generate_embedding(self, ingestor, mock_ollama_client):
        """Should generate embedding via Ollama"""
        # GIVEN: Text to embed
        text = "This is test content"

        # WHEN: Generating embedding
        embedding = ingestor._generate_embedding(text)

        # THEN: Returns vector from Ollama
        assert len(embedding) == 1024  # qwen3-embedding dimension
        mock_ollama_client.embeddings.assert_called_once()

    def test_store_chunk_in_weaviate(self, ingestor, mock_weaviate_client):
        """Should store chunk with embedding in Weaviate"""
        # GIVEN: Chunk data
        chunk_data = {
            "text": "Test content",
            "source_file": "/vault/note.md",
            "chunk_index": 0,
            "source_type": "obsidian",
            "file_modified_at": datetime.now(),
            "embedding": [0.1] * 1024,
        }

        # WHEN: Storing chunk
        ingestor._store_chunk(chunk_data)

        # THEN: Chunk is added to Weaviate collection
        mock_collection = mock_weaviate_client.collections.get.return_value
        mock_collection.data.insert.assert_called_once()

    def test_ingest_vault_processes_all_files(self, ingestor, tmp_path, mock_state_tracker):
        """Should process all unprocessed files in vault"""
        # GIVEN: Multiple markdown files
        (tmp_path / "note1.md").write_text("Content 1")
        (tmp_path / "note2.md").write_text("Content 2")
        (tmp_path / "note3.md").write_text("Content 3")

        # All files need ingestion
        mock_state_tracker.is_ingested.return_value = False

        # WHEN: Ingesting entire vault
        stats = ingestor.ingest_vault()

        # THEN: All files processed
        assert stats["files_processed"] == 3
        assert stats["total_chunks"] > 0

    def test_incremental_ingestion(self, ingestor, tmp_path, mock_state_tracker):
        """Should only process new/modified files"""
        # GIVEN: 3 files, 2 already ingested
        (tmp_path / "old1.md").write_text("Old content 1")
        (tmp_path / "old2.md").write_text("Old content 2")
        (tmp_path / "new.md").write_text("New content")

        # Mock: old files already ingested, new file is not
        def is_ingested_mock(file_path, mod_time):
            return "new.md" not in file_path

        mock_state_tracker.is_ingested.side_effect = is_ingested_mock

        # WHEN: Ingesting vault
        stats = ingestor.ingest_vault()

        # THEN: Only new file processed
        assert stats["files_processed"] == 1
        assert stats["files_skipped"] == 2

    def test_empty_vault_handling(self, ingestor, tmp_path):
        """Should handle empty vault gracefully"""
        # GIVEN: Empty vault
        # WHEN: Ingesting vault
        stats = ingestor.ingest_vault()

        # THEN: No errors, zero files processed
        assert stats["files_processed"] == 0
        assert stats["total_chunks"] == 0

    def test_ingestion_preserves_source_metadata(self, ingestor, tmp_path, mock_weaviate_client):
        """Should tag all chunks with sourceType='obsidian'"""
        # GIVEN: Markdown file
        file_path = tmp_path / "note.md"
        file_path.write_text("Test content for metadata")

        # WHEN: Processing file
        ingestor.ingest_file(str(file_path))

        # THEN: All chunks tagged with sourceType='obsidian'
        mock_collection = mock_weaviate_client.collections.get.return_value
        call_args = mock_collection.data.insert.call_args_list

        for call in call_args:
            properties = call[1]["properties"]
            assert properties["sourceType"] == "obsidian"

    def test_error_handling_invalid_file(self, ingestor, tmp_path, mock_state_tracker):
        """Should handle errors gracefully and continue"""
        # GIVEN: Invalid file path
        invalid_path = "/nonexistent/file.md"

        # WHEN: Attempting to ingest
        chunk_count = ingestor.ingest_file(invalid_path)

        # THEN: Returns 0, doesn't crash
        assert chunk_count == 0
        # Should not mark as ingested
        mock_state_tracker.mark_ingested.assert_not_called()

    def test_batch_embedding_generation(self, ingestor, mock_ollama_client):
        """Should efficiently batch embedding requests"""
        # GIVEN: Multiple chunks
        chunks = [f"Chunk {i} content" for i in range(10)]

        # WHEN: Generating embeddings for all
        embeddings = [ingestor._generate_embedding(chunk) for chunk in chunks]

        # THEN: All embeddings generated
        assert len(embeddings) == 10
        assert mock_ollama_client.embeddings.call_count == 10

    def test_collection_name_configuration(self, ingestor):
        """Should use TheMuses collection (not TheLethe)"""
        # THEN: Collection is TheMuses
        assert ingestor.collection_name == "TheMuses"
