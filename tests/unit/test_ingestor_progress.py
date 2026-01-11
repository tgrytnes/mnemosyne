"""
Unit tests for ingestion progress logging.
"""

import logging
from datetime import datetime

from mnemosyne.aletheia.obsidian_ingestor import ObsidianIngestor
from mnemosyne.aletheia.text_chunker import TextChunk


def test_ingest_vault_logs_progress(mocker, caplog):
    mocker.patch(
        "mnemosyne.aletheia.obsidian_ingestor.WeaviateSchemaManager.ensure_collection_exists",
        lambda *args, **kwargs: None,
    )
    weaviate_client = mocker.MagicMock()
    llm_provider = mocker.MagicMock()
    embedding_provider = mocker.MagicMock()

    ingestor = ObsidianIngestor(
        vault_path="/tmp",
        weaviate_client=weaviate_client,
        embedding_provider=embedding_provider,
        llm_provider=llm_provider,
        chunking_strategy="recursive",
        progress_every=1,
    )

    ingestor.scan_vault = mocker.MagicMock(return_value=["a.md", "b.md"])
    ingestor.needs_ingestion = mocker.MagicMock(return_value=True)
    mod_time = datetime(2025, 1, 1)
    chunk = TextChunk(text="hello", index=0, source_file="a.md")
    ingestor._prepare_chunks_for_file = mocker.MagicMock(
        side_effect=[([chunk], mod_time), ([chunk], mod_time)]
    )
    ingestor._delete_existing_chunks = mocker.MagicMock()
    ingestor._generate_embedding = mocker.MagicMock(return_value=[0.0, 0.1])
    ingestor._store_chunk = mocker.MagicMock()

    caplog.set_level(logging.INFO)
    ingestor.ingest_vault()

    assert "Ingestion progress:" in caplog.text
