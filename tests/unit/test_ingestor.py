"""
Unit tests for Obsidian Vault Ingestor (Layer 1: Input Processing)
Tests Story 000: Obsidian Vault Ingestion
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock


@pytest.mark.unit
class TestMarkdownCleaning:
    """Test markdown cleaning functionality"""

    def test_remove_yaml_frontmatter(self, sample_markdown_file):
        """Test YAML frontmatter removal"""
        # This would test your actual ingestor implementation
        # Example structure:
        # from mnemosyne.aletheia.ingestor import ObsidianIngestor
        # ingestor = ObsidianIngestor(vault_path="/tmp")
        # content = ingestor.clean_markdown(sample_markdown_file)

        # Mock implementation for now
        content = sample_markdown_file.read_text()

        # Verify frontmatter exists
        assert "---" in content
        assert "tags:" in content

        # After cleaning (you would implement this):
        # assert "---" not in cleaned_content
        # assert "tags:" not in cleaned_content
        # assert "# Sample Project Document" in cleaned_content

    def test_remove_wiki_links(self, tmp_path):
        """Test wiki-link removal"""
        test_file = tmp_path / "wiki_links.md"
        test_file.write_text("This has [[wiki-link]] and [[another|alias]] link.")

        # After cleaning:
        # cleaned = ingestor.clean_markdown(test_file)
        # assert "[[" not in cleaned
        # assert "]]" not in cleaned
        # assert "wiki-link" in cleaned  # Text should remain

    def test_preserve_code_blocks(self, tmp_path):
        """Test that code blocks are preserved"""
        test_file = tmp_path / "code.md"
        test_file.write_text(
            """# Code Example

```python
def hello():
    print("Hello [[world]]")
```

Regular [[link]] here.
"""
        )

        # Code blocks should be preserved
        # cleaned = ingestor.clean_markdown(test_file)
        # assert '```python' in cleaned
        # assert 'def hello():' in cleaned


@pytest.mark.unit
class TestTextChunking:
    """Test text chunking functionality"""

    def test_chunk_size_respects_limit(self):
        """Test chunks don't exceed max size"""
        text = "a" * 1000
        chunk_size = 400
        overlap = 100

        # chunks = ingestor.chunk_text(text, chunk_size, overlap)
        # assert all(len(chunk.text) <= chunk_size for chunk in chunks)

    def test_chunk_overlap_preserved(self):
        """Test overlap between consecutive chunks"""
        text = "a" * 1000
        chunk_size = 400
        overlap = 100

        # chunks = ingestor.chunk_text(text, chunk_size, overlap)
        # Verify overlap
        # assert chunks[0].text[-overlap:] == chunks[1].text[:overlap]

    def test_chunking_handles_small_text(self):
        """Test chunking text smaller than chunk size"""
        text = "Small text"
        chunk_size = 400

        # chunks = ingestor.chunk_text(text, chunk_size, 100)
        # assert len(chunks) == 1
        # assert chunks[0].text == text


@pytest.mark.unit
class TestIngestionState:
    """Test ingestion state tracking"""

    def test_track_ingested_file(self, tmp_path):
        """Test file ingestion tracking"""
        # from Aletheia.ingestor import IngestionState

        db_path = tmp_path / "state.db"
        # state = IngestionState(str(db_path))

        file_path = "/vault/test.md"
        modified_time = 1234567890.0

        # state.mark_ingested(file_path, modified_time)
        # assert state.already_ingested(file_path, modified_time) is True

    def test_detect_modified_file(self, tmp_path):
        """Test detection of modified files"""
        db_path = tmp_path / "state.db"
        # state = IngestionState(str(db_path))

        file_path = "/vault/test.md"
        old_time = 1234567890.0
        new_time = 1234567900.0  # 10 seconds later

        # state.mark_ingested(file_path, old_time)
        # assert state.already_ingested(file_path, new_time) is False


@pytest.mark.unit
class TestEmbeddingGeneration:
    """Test embedding generation via Ollama"""

    def test_generate_embedding(self, mock_ollama_client):
        """Test embedding generation returns correct dimensions"""
        # from Aletheia.ingestor import ObsidianIngestor

        # ingestor = ObsidianIngestor(vault_path="/tmp", ollama_client=mock_ollama_client)
        # embedding = ingestor.get_embedding("Test text")

        # assert len(embedding) == 1024  # qwen3-embedding:0.6b dimension
        # assert all(isinstance(x, float) for x in embedding)

    def test_embedding_caching(self, mock_ollama_client):
        """Test embeddings are not regenerated for same text"""
        # If you implement caching
        # embedding1 = ingestor.get_embedding("Same text")
        # embedding2 = ingestor.get_embedding("Same text")

        # mock_ollama_client.embeddings.assert_called_once()


@pytest.mark.unit
def test_file_watching_detects_changes(tmp_path, temp_vault):
    """Test file watcher detects new and modified files"""
    # from Aletheia.ingestor import VaultWatcher

    # watcher = VaultWatcher(vault_path=str(temp_vault))

    # Create new file
    new_file = temp_vault / "new_note.md"
    new_file.write_text("# New Note")

    # watcher should detect this
    # changes = watcher.get_changes()
    # assert str(new_file) in changes['added']


@pytest.mark.unit
def test_ingestion_performance_target(temp_vault):
    """Test ingestion meets performance targets"""
    # Based on Story 000 requirements:
    # - 3-4 files/minute on Pi 5
    # - Incremental updates: <5 minutes for 10 files

    # This would be a benchmark test
    # import time
    # from Aletheia.ingestor import ObsidianIngestor

    # ingestor = ObsidianIngestor(vault_path=str(temp_vault))

    # start = time.time()
    # ingestor.ingest_vault()
    # duration = time.time() - start

    # file_count = len(list(temp_vault.glob("**/*.md")))
    # rate = file_count / (duration / 60)  # files per minute

    # assert rate >= 3.0, f"Ingestion too slow: {rate:.2f} files/min"
