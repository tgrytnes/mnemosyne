"""Unit tests for ingestors when embeddings fail."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from unittest.mock import Mock, patch

from mnemosyne.aletheia.email_ingest import EmailIngestConfig, EmailIngestor
from mnemosyne.aletheia.models import Email
from mnemosyne.aletheia.obsidian_ingestor import ObsidianIngestor
from mnemosyne.aletheia.pdf_ingestor import PDFIngestor
from mnemosyne.aletheia.text_chunker import TextChunk


class _DummyState:
    def is_ingested(self, *_args, **_kwargs):
        return False

    def mark_ingested(self, *_args, **_kwargs):
        return None

    def save(self):
        return None


def _fake_collection():
    collection = Mock()
    collection.data.insert = Mock()
    return collection


def _fake_client(collection):
    client = Mock()
    client.collections.get.return_value = collection
    return client


def test_pdf_ingestor_skips_insert_when_embedding_raises(tmp_path, caplog):
    collection = _fake_collection()
    client = _fake_client(collection)
    embedding_provider = Mock()
    embedding_provider.embed.side_effect = ValueError("boom")

    with patch("mnemosyne.aletheia.pdf_ingestor.WeaviateSchemaManager.ensure_collection_exists"):
        ingestor = PDFIngestor(
            input_dir=str(tmp_path),
            weaviate_client=client,
            embedding_provider=embedding_provider,
        )

    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_text("stub")

    with (
        patch.object(ingestor, "_extract_text", return_value="hello"),
        patch.object(ingestor, "clean_text", return_value="hello"),
        patch.object(ingestor, "chunk_text", return_value=["chunk"]),
    ):
        caplog.set_level(logging.ERROR)
        ingestor.ingest_file(pdf_path)

    assert collection.data.insert.call_count == 0
    assert any("embedding" in record.message.lower() for record in caplog.records)


def test_email_ingestor_skips_insert_when_embedding_empty(tmp_path, caplog):
    collection = _fake_collection()
    client = _fake_client(collection)
    embedding_provider = Mock()
    embedding_provider.embed.return_value = []
    config = EmailIngestConfig(
        source_dir=tmp_path,
        chunking_strategy="recursive",
        min_body_chars=1,
    )

    with patch("mnemosyne.aletheia.email_ingest.WeaviateSchemaManager.ensure_collection_exists"):
        ingestor = EmailIngestor(config, client, embedding_provider=embedding_provider)

    ingestor.chunker = Mock()
    ingestor.chunker.chunk.return_value = [
        TextChunk(text="body", index=0, source_file="source.eml")
    ]
    ingestor.state = _DummyState()

    email = Email(
        subject="Test",
        body="Body that is long enough for ingestion.",
        sender="sender@example.com",
        date="2025-01-01",
        message_id="msg-1",
        source_path="source.eml",
        unique_id="unique-1",
    )

    caplog.set_level(logging.ERROR, logger="mnemosyne.aletheia.email_ingest")
    summary = ingestor._ingest_emails([email])

    assert collection.data.insert.call_count == 0
    assert summary.total_stored == 0
    assert any("embedding" in record.message.lower() for record in caplog.records)


def test_obsidian_ingestor_skips_insert_when_embedding_none(tmp_path, caplog):
    collection = _fake_collection()
    client = _fake_client(collection)
    embedding_provider = Mock()

    with (
        patch(
            "mnemosyne.aletheia.obsidian_ingestor.WeaviateSchemaManager.ensure_collection_exists"
        ),
        patch(
            "mnemosyne.aletheia.obsidian_ingestor.ChunkingStrategyFactory.create",
            return_value=Mock(),
        ),
    ):
        ingestor = ObsidianIngestor(
            vault_path=str(tmp_path),
            weaviate_client=client,
            embedding_provider=embedding_provider,
            llm_provider=Mock(),
            state_tracker=_DummyState(),
        )

    chunk = TextChunk(text="note", index=0, source_file="note.md")
    mod_time = datetime.now(UTC)

    with (
        patch.object(
            ingestor,
            "_prepare_chunks_for_file",
            return_value=([chunk], mod_time, "note"),
        ),
        patch.object(ingestor, "_delete_existing_chunks"),
    ):
        ingestor._generate_embedding = Mock(return_value=None)
        ingestor._store_chunk = Mock()
        caplog.set_level(logging.ERROR)
        ingestor.ingest_file(str(tmp_path / "note.md"))

    assert ingestor._store_chunk.call_count == 0
    assert any("embedding" in record.message.lower() for record in caplog.records)
