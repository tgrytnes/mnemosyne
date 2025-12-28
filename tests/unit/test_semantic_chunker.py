"""
Unit tests for semantic chunking with LLM boundaries.
"""

import json
import tempfile
from pathlib import Path

import pytest

from mnemosyne.aletheia.ingestion_state import IngestionStateTracker
from mnemosyne.aletheia.semantic_chunker import SemanticChunker
from mnemosyne.aletheia.text_chunker import TextChunk


class TestSemanticChunker:
    """Test semantic chunking behavior"""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        Path(db_path).unlink(missing_ok=True)

    def test_splits_text_at_llm_boundaries(self, mocker):
        """Should split text using boundaries returned by the LLM"""
        ollama_client = mocker.MagicMock()
        ollama_client.generate.return_value = {"response": json.dumps({"boundaries": [5]})}

        chunker = SemanticChunker(ollama_client=ollama_client, min_chunk_size=1)
        text = "hello world"

        chunks = chunker.chunk(text, source_file="note.md")

        assert len(chunks) == 2
        assert "".join(chunk.text for chunk in chunks) == text
        assert chunks[0].source_file == "note.md"

    def test_uses_cached_boundaries_when_available(self, mocker, temp_db):
        """Should skip LLM call when cached boundaries exist"""
        ollama_client = mocker.MagicMock()
        state_tracker = IngestionStateTracker(temp_db)

        chunker = SemanticChunker(
            ollama_client=ollama_client, state_tracker=state_tracker, min_chunk_size=1
        )
        text = "alpha beta gamma"

        cache_key = chunker._cache_key(text)
        state_tracker.cache_semantic_boundaries(
            cache_key=cache_key,
            boundaries=[5],
            model=chunker.model,
            min_chunk_size=chunker.min_chunk_size,
            max_chunk_size=chunker.max_chunk_size,
        )

        chunks = chunker.chunk(text, source_file="note.md")

        assert len(chunks) == 2
        ollama_client.generate.assert_not_called()

    def test_falls_back_to_recursive_on_llm_error(self, mocker):
        """Should fall back to recursive chunker if LLM fails"""
        ollama_client = mocker.MagicMock()
        ollama_client.generate.side_effect = RuntimeError("LLM failure")

        fallback_chunker = mocker.MagicMock()
        fallback_chunker.chunk.return_value = [
            TextChunk(text="fallback", index=0, source_file="note.md")
        ]

        chunker = SemanticChunker(
            ollama_client=ollama_client,
            fallback_chunker=fallback_chunker,
            min_chunk_size=1,
        )
        chunks = chunker.chunk("content", source_file="note.md")

        assert len(chunks) == 1
        assert chunks[0].text == "fallback"
        fallback_chunker.chunk.assert_called_once_with("content", "note.md")

    def test_preserves_topic_boundaries(self, mocker):
        """Should split at topic change to avoid mixing topics"""
        ollama_client = mocker.MagicMock()
        text = "Topic A: Alpha details.\nTopic A: More alpha.\n\nTopic B: Beta details."
        boundary_index = text.index("Topic B")
        ollama_client.generate.return_value = {
            "response": json.dumps({"boundaries": [boundary_index]})
        }
        chunker = SemanticChunker(ollama_client=ollama_client, min_chunk_size=1)

        chunks = chunker.chunk(text, source_file="note.md")

        assert len(chunks) == 2
        assert "Topic A" in chunks[0].text
        assert "Topic B" not in chunks[0].text
        assert "Topic B" in chunks[1].text
