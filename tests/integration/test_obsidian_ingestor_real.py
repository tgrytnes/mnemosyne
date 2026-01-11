"""
Integration tests for ObsidianIngestor using real Ollama and Weaviate.

Precondition: Use a fresh TheMuses collection for ingestion-focused checks.
"""

import pytest

from mnemosyne.aletheia.ingestion_state import IngestionStateTracker
from mnemosyne.aletheia.obsidian_ingestor import ObsidianIngestor
from mnemosyne.alexandria.weaviate_schema import WeaviateSchemaManager
from mnemosyne.config.providers import ProviderConfig
from mnemosyne.providers.factory import create_embedding_provider, create_llm_provider


def _reset_themuses(weaviate_client):
    if weaviate_client.collections.exists("TheMuses"):
        weaviate_client.collections.delete("TheMuses")
    WeaviateSchemaManager(weaviate_client).ensure_collection_exists("TheMuses")


@pytest.mark.integration
def test_ingestor_ingests_single_file(weaviate_client, test_config, tmp_path):
    _reset_themuses(weaviate_client)
    vault = tmp_path / "vault"
    vault.mkdir()

    file_path = vault / "note.md"
    file_path.write_text(
        """---
title: Test Note
---

# Test Note

This note references [[alpha_notes]] and includes ![[image.png]].
"""
    )

    # Use provider system
    provider_config = ProviderConfig(
        llm_provider="ollama",
        embedding_provider="ollama",
        ollama_base_url=test_config["ollama_url"]
    )
    llm_provider = create_llm_provider(provider_config)
    embedding_provider = create_embedding_provider(provider_config)

    state_tracker = IngestionStateTracker(str(tmp_path / "state.db"))
    ingestor = ObsidianIngestor(
        vault_path=str(vault),
        weaviate_client=weaviate_client,
        llm_provider=llm_provider,
        embedding_provider=embedding_provider,
        state_tracker=state_tracker,
    )

    chunk_count = ingestor.ingest_file(str(file_path))
    assert chunk_count > 0

    collection = weaviate_client.collections.get("TheMuses")
    result = collection.query.fetch_objects(include_vector=True, limit=5)
    assert len(result.objects) > 0

    vector = result.objects[0].vector
    vector = vector["default"] if isinstance(vector, dict) else vector
    assert len(vector) == 1024

    state_tracker.close()


@pytest.mark.integration
def test_ingestor_respects_incremental_state(weaviate_client, test_config, tmp_path):
    _reset_themuses(weaviate_client)
    vault = tmp_path / "vault"
    vault.mkdir()

    file_path = vault / "note.md"
    file_path.write_text("# Original content")

    # Use provider system
    provider_config = ProviderConfig(
        llm_provider="ollama",
        embedding_provider="ollama",
        ollama_base_url=test_config["ollama_url"]
    )
    llm_provider = create_llm_provider(provider_config)
    embedding_provider = create_embedding_provider(provider_config)

    state_path = tmp_path / "state.db"
    tracker = IngestionStateTracker(str(state_path))
    ingestor = ObsidianIngestor(
        vault_path=str(vault),
        weaviate_client=weaviate_client,
        llm_provider=llm_provider,
        embedding_provider=embedding_provider,
        state_tracker=tracker,
    )

    first_stats = ingestor.ingest_vault()
    assert first_stats["files_processed"] == 1

    second_stats = ingestor.ingest_vault()
    assert second_stats["files_processed"] == 0
    assert second_stats["files_skipped"] == 1

    file_path.write_text("# Modified content")
    third_stats = ingestor.ingest_vault()
    assert third_stats["files_processed"] == 1

    tracker.close()
