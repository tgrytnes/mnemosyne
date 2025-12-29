"""
E2E performance benchmark for hybrid chunking with REAL Ollama and Weaviate.
"""

import time

import ollama
import pytest

from mnemosyne.aletheia.ingestion_state import IngestionStateTracker
from mnemosyne.aletheia.obsidian_ingestor import ObsidianIngestor


@pytest.mark.e2e
@pytest.mark.weaviate
def test_hybrid_ingestion_under_time_limit(
    tmp_path, weaviate_client, clean_weaviate_collection, test_config
):
    """
    REAL E2E TEST: Hybrid ingestion with actual Ollama LLM calls.
    Should complete under 30 minutes for 100 files.
    """
    # Create 100 test files with meaningful content for semantic chunking
    for i in range(100):
        content = f"""# Note {i}

## Introduction
This is test note number {i} with multiple sections to test semantic chunking.
The content is meaningful enough for the LLM to detect topic boundaries.

## Main Topic
Here we discuss the main topic of note {i}.
This section contains the primary information.

## Conclusion
Final thoughts on note {i}.
"""
        (tmp_path / f"note-{i}.md").write_text(content)

    # Use REAL Ollama client
    ollama_client = ollama.Client(host=test_config["ollama_url"])

    # Use REAL Weaviate client
    state_tracker = IngestionStateTracker(str(tmp_path / "ingestion_state.db"))

    ingestor = ObsidianIngestor(
        vault_path=str(tmp_path),
        weaviate_client=weaviate_client,
        ollama_client=ollama_client,
        state_tracker=state_tracker,
        chunking_strategy="hybrid",
        section_semantic_min_length=100,  # Realistic threshold
        semantic_min_chunk_size=50,
    )

    start = time.monotonic()
    stats = ingestor.ingest_vault()
    elapsed = time.monotonic() - start

    assert stats["files_processed"] == 100
    assert stats["total_chunks"] >= 100  # Should create at least one chunk per file
    assert elapsed < 30 * 60  # 30 minutes max
