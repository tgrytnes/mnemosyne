"""Unit tests for chunking augmentations (late/contextual)."""

from __future__ import annotations

from unittest.mock import Mock, patch

from mnemosyne.aletheia.chunking_augmentation import compute_chunk_spans
from mnemosyne.aletheia.obsidian_ingestor import ObsidianIngestor
from mnemosyne.aletheia.text_chunker import TextChunk


class _DummyState:
    def is_ingested(self, *_args, **_kwargs):
        return False

    def mark_ingested(self, *_args, **_kwargs):
        return None

    def save(self):
        return None


def _ingestor(
    tmp_path,
    embedding_provider,
    llm_provider,
    chunking_augmentation="none",
    state_tracker=None,
):
    with (
        patch(
            "mnemosyne.aletheia.obsidian_ingestor.WeaviateSchemaManager.ensure_collection_exists"
        ),
        patch(
            "mnemosyne.aletheia.obsidian_ingestor.ChunkingStrategyFactory.create",
            return_value=Mock(),
        ),
    ):
        return ObsidianIngestor(
            vault_path=str(tmp_path),
            weaviate_client=Mock(),
            embedding_provider=embedding_provider,
            llm_provider=llm_provider,
            state_tracker=state_tracker or _DummyState(),
            chunking_augmentation=chunking_augmentation,
        )


def test_compute_chunk_spans_uses_cursor():
    text = "Intro\nIntro\n"
    chunks = [
        TextChunk(text="Intro\n", index=0, source_file="note.md"),
        TextChunk(text="Intro\n", index=1, source_file="note.md"),
    ]

    spans = compute_chunk_spans(text, chunks, chunk_overlap=0)

    assert spans == [(0, 6), (6, 12)]


def test_compute_chunk_spans_supports_overlap():
    text = "abcdefghij"
    chunks = [
        TextChunk(text="abcdef", index=0, source_file="note.md"),
        TextChunk(text="cdefgh", index=1, source_file="note.md"),
    ]

    spans = compute_chunk_spans(text, chunks, chunk_overlap=4)

    assert spans == [(0, 6), (2, 8)]


def test_late_chunking_calls_embed_late(tmp_path):
    embedding_provider = Mock()
    embedding_provider.embed_late.return_value = [[0.1], [0.2]]
    llm_provider = Mock()
    ingestor = _ingestor(
        tmp_path,
        embedding_provider,
        llm_provider,
        chunking_augmentation="late",
    )

    chunks = [
        TextChunk(text="Intro\n", index=0, source_file="note.md"),
        TextChunk(text="Intro\n", index=1, source_file="note.md"),
    ]

    results = ingestor._generate_embeddings_for_chunks("Intro\nIntro\n", chunks)

    assert [item["embedding"] for item in results] == [[0.1], [0.2]]
    embedding_provider.embed_late.assert_called_once()
    _, kwargs = embedding_provider.embed_late.call_args
    assert kwargs["chunk_spans"] == [(0, 6), (6, 12)]


def test_late_chunking_falls_back_when_spans_missing(tmp_path):
    embedding_provider = Mock()
    embedding_provider.embed.return_value = [0.5]
    embedding_provider.embed_late.return_value = [[0.1], [0.2]]
    llm_provider = Mock()
    ingestor = _ingestor(
        tmp_path,
        embedding_provider,
        llm_provider,
        chunking_augmentation="late",
    )

    chunks = [
        TextChunk(text="Missing\n", index=0, source_file="note.md"),
        TextChunk(text="Chunk\n", index=1, source_file="note.md"),
    ]

    results = ingestor._generate_embeddings_for_chunks("Intro\nIntro\n", chunks)

    assert [item["embedding"] for item in results] == [[0.5], [0.5]]
    embedding_provider.embed_late.assert_not_called()
    assert embedding_provider.embed.call_count == 2


def test_contextual_augmentation_prefixes_header(tmp_path):
    embedding_provider = Mock()
    embedding_provider.embed.return_value = [0.9]
    llm_provider = Mock()
    llm_provider.generate.return_value = {"response": "Context header"}
    ingestor = _ingestor(
        tmp_path,
        embedding_provider,
        llm_provider,
        chunking_augmentation="contextual",
    )

    chunks = [TextChunk(text="Chunk text", index=0, source_file="note.md")]

    results = ingestor._generate_embeddings_for_chunks("Doc text", chunks)

    assert results[0]["context_header"] == "Context header"
    embedding_provider.embed.assert_called_once_with(
        model="",
        text="Context header\n\nChunk text",
    )


def test_doc_summary_augmentation_prefixes_summary(tmp_path):
    embedding_provider = Mock()
    embedding_provider.embed.return_value = [0.8]
    llm_provider = Mock()
    llm_provider.generate.return_value = {"response": "Doc summary"}
    ingestor = _ingestor(
        tmp_path,
        embedding_provider,
        llm_provider,
        chunking_augmentation="doc_summary",
    )

    chunks = [
        TextChunk(text="Chunk one", index=0, source_file="note.md"),
        TextChunk(text="Chunk two", index=1, source_file="note.md"),
    ]

    results = ingestor._generate_embeddings_for_chunks("Doc text", chunks)

    assert [item["embedding"] for item in results] == [[0.8], [0.8]]
    llm_provider.generate.assert_called_once()
    assert embedding_provider.embed.call_count == 2
    embedding_provider.embed.assert_any_call(model="", text="Doc summary\n\nChunk one")
    embedding_provider.embed.assert_any_call(model="", text="Doc summary\n\nChunk two")


def test_doc_summary_augmentation_uses_cache(tmp_path):
    class _SummaryState(_DummyState):
        def __init__(self):
            self.cached = {"cache-key": "Cached summary"}

        def get_cached_doc_summary(self, cache_key):
            return self.cached.get(cache_key)

        def cache_doc_summary(self, cache_key, summary, model, max_chars, temperature):
            self.cached[cache_key] = summary

    embedding_provider = Mock()
    embedding_provider.embed.return_value = [0.7]
    llm_provider = Mock()
    ingestor = _ingestor(
        tmp_path,
        embedding_provider,
        llm_provider,
        chunking_augmentation="doc_summary",
        state_tracker=_SummaryState(),
    )

    chunks = [TextChunk(text="Chunk text", index=0, source_file="note.md")]

    with patch.object(ingestor, "_doc_summary_cache_key", return_value="cache-key"):
        ingestor._generate_embeddings_for_chunks("Doc text", chunks)

    llm_provider.generate.assert_not_called()
    embedding_provider.embed.assert_called_once_with(
        model="",
        text="Cached summary\n\nChunk text",
    )
