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
from mnemosyne.llm.strict_json import StrictJsonError


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
        llm_provider = mocker.MagicMock()
        llm_provider.generate.return_value = {"response": json.dumps({"boundaries": [1]})}

        chunker = SemanticChunker(llm_provider=llm_provider, min_chunk_size=1)
        text = "hello\n\nworld"

        chunks = chunker.chunk(text, source_file="note.md")

        assert len(chunks) == 2
        assert "".join(chunk.text for chunk in chunks) == text
        assert chunks[0].source_file == "note.md"

    def test_uses_cached_boundaries_when_available(self, mocker, temp_db):
        """Should skip LLM call when cached boundaries exist"""
        llm_provider = mocker.MagicMock()
        state_tracker = IngestionStateTracker(temp_db)

        chunker = SemanticChunker(
            llm_provider=llm_provider, state_tracker=state_tracker, min_chunk_size=1
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
        llm_provider.generate.assert_not_called()

    def test_falls_back_to_recursive_on_llm_error(self, mocker):
        """Should fall back to recursive chunker if LLM fails"""
        llm_provider = mocker.MagicMock()
        llm_provider.generate.side_effect = RuntimeError("LLM failure")

        fallback_chunker = mocker.MagicMock()
        fallback_chunker.chunk.return_value = [
            TextChunk(text="fallback", index=0, source_file="note.md")
        ]

        chunker = SemanticChunker(
            llm_provider=llm_provider,
            fallback_chunker=fallback_chunker,
            min_chunk_size=1,
        )
        chunks = chunker.chunk("content\n\nmore", source_file="note.md")

        assert len(chunks) == 1
        assert chunks[0].text == "fallback"
        fallback_chunker.chunk.assert_called_once_with("content\n\nmore", "note.md")

    def test_preserves_topic_boundaries(self, mocker):
        """Should split at topic change to avoid mixing topics"""
        llm_provider = mocker.MagicMock()
        text = "Topic A: Alpha details.\nTopic A: More alpha.\n\nTopic B: Beta details."
        llm_provider.generate.return_value = {"response": json.dumps({"boundaries": [1]})}
        chunker = SemanticChunker(llm_provider=llm_provider, min_chunk_size=1)

        chunks = chunker.chunk(text, source_file="note.md")

        assert len(chunks) == 2
        assert "Topic A" in chunks[0].text
        assert "Topic B" not in chunks[0].text
        assert "Topic B" in chunks[1].text

    def test_strict_json_requires_schema(self, mocker, monkeypatch):
        monkeypatch.setenv("STRICT_JSON_STEPS", "semantic_chunking")
        monkeypatch.setenv("ALLOW_JSON_FALLBACK", "false")

        llm_provider = mocker.MagicMock()
        llm_provider.supports_structured_output.return_value = True
        llm_provider.generate.return_value = {"response": json.dumps({"boundaries": [5]})}

        chunker = SemanticChunker(llm_provider=llm_provider, min_chunk_size=1)
        chunker.chunk("hello\n\nworld", source_file="note.md")

        _, kwargs = llm_provider.generate.call_args
        assert kwargs["format"] == "json"
        assert "json_schema" in kwargs["options"]

    def test_strict_json_rejects_invalid_payload(self, mocker, monkeypatch):
        monkeypatch.setenv("STRICT_JSON_STEPS", "semantic_chunking")
        monkeypatch.setenv("ALLOW_JSON_FALLBACK", "false")

        llm_provider = mocker.MagicMock()
        llm_provider.supports_structured_output.return_value = True
        llm_provider.generate.return_value = {"response": "not-json"}

        chunker = SemanticChunker(llm_provider=llm_provider, min_chunk_size=1)
        with pytest.raises(StrictJsonError):
            chunker.chunk("hello\n\nworld", source_file="note.md")
            chunker.chunk("hello\n\nworld", source_file="note.md")

    def test_strict_json_chunks_when_text_exceeds_max_chars(self, mocker, monkeypatch):
        monkeypatch.setenv("STRICT_JSON_STEPS", "semantic_chunking")

        llm_provider = mocker.MagicMock()
        llm_provider.supports_structured_output.return_value = True
        llm_provider.generate.return_value = {"response": json.dumps({"boundaries": [1]})}

        chunker = SemanticChunker(llm_provider=llm_provider, min_chunk_size=1, json_max_chars=10)
        text = "Alpha\n\nBeta\n\nGamma"

        chunks = chunker.chunk(text, source_file="note.md")

        assert chunks
        _, kwargs = llm_provider.generate.call_args
        assert kwargs["format"] == "json"
        assert "json_schema" in kwargs["options"]

    def test_strict_json_includes_max_tokens_option(self, mocker, monkeypatch):
        monkeypatch.setenv("STRICT_JSON_STEPS", "semantic_chunking")
        monkeypatch.setenv("ALLOW_JSON_FALLBACK", "false")

        llm_provider = mocker.MagicMock()
        llm_provider.supports_structured_output.return_value = True
        llm_provider.generate.return_value = {"response": json.dumps({"boundaries": []})}

        chunker = SemanticChunker(llm_provider=llm_provider, min_chunk_size=1, json_max_tokens=64)
        chunker.chunk("hello\n\nworld\n\nagain", source_file="note.md")

        _, kwargs = llm_provider.generate.call_args
        assert kwargs["options"]["max_tokens"] <= 64
