"""
Integration performance test for hybrid chunking with REAL Ollama and Weaviate.
"""

import time

import pytest

from mnemosyne.aletheia.ingestion_state import IngestionStateTracker
from mnemosyne.aletheia.obsidian_ingestor import ObsidianIngestor
from mnemosyne.config.providers import ProviderConfig
from mnemosyne.providers.factory import create_embedding_provider, create_llm_provider


@pytest.mark.integration
@pytest.mark.performance
@pytest.mark.weaviate
def test_hybrid_ingestion_performance(
    tmp_path, weaviate_client, clean_weaviate_collection, test_config
):
    """
    REAL INTEGRATION TEST: Hybrid ingestion with actual Ollama LLM.
    Tests performance with 10 files (reduced from 100 for reasonable test time).
    """
    # Create 10 test files with realistic content
    for i in range(10):
        content = f"""# Note {i}

## Overview
This is test note {i} with semantic content for LLM boundary detection.

## Details
More information about topic {i} goes here.
"""
        (tmp_path / f"note-{i}.md").write_text(content)

    # Use provider system
    provider_config = ProviderConfig(
        llm_provider="ollama",
        embedding_provider="ollama",
        ollama_base_url=test_config["ollama_url"]
    )
    llm_provider = create_llm_provider(provider_config)
    embedding_provider = create_embedding_provider(provider_config)

    state_tracker = IngestionStateTracker(str(tmp_path / "ingestion_state.db"))

    ingestor = ObsidianIngestor(
        vault_path=str(tmp_path),
        weaviate_client=weaviate_client,
        llm_provider=llm_provider,
        embedding_provider=embedding_provider,
        state_tracker=state_tracker,
        chunking_strategy="hybrid",
        section_semantic_min_length=100,
        semantic_min_chunk_size=50,
    )

    start = time.monotonic()
    stats = ingestor.ingest_vault()
    elapsed = time.monotonic() - start

    assert stats["files_processed"] == 10
    assert stats["total_chunks"] >= 10
    # Real LLM calls are slower - allow extra time for larger semantic models.
    assert elapsed < 120.0, f"Took {elapsed:.2f}s, expected <120s"
