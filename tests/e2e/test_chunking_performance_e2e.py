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


@pytest.mark.e2e
@pytest.mark.weaviate
def test_semantic_chunking_detects_topic_shift(
    tmp_path, weaviate_client, clean_weaviate_collection, test_config
):
    """
    REAL E2E TEST: Semantic chunking should split at a clear topic shift.
    """
    note_path = tmp_path / "semantic_boundary.md"
    note_path.write_text(
        """Topic A is about machine learning and neural networks.
Deep learning has transformed AI research significantly.
This section focuses on technical aspects.

Topic B discusses project management and team collaboration.
Agile methodologies are important for software development.
This section shifts to organizational topics.
"""
    )

    ollama_client = ollama.Client(host=test_config["ollama_url"])
    state_tracker = IngestionStateTracker(str(tmp_path / "semantic_state.db"))

    ingestor = ObsidianIngestor(
        vault_path=str(tmp_path),
        weaviate_client=weaviate_client,
        ollama_client=ollama_client,
        state_tracker=state_tracker,
        chunking_strategy="semantic",
        semantic_min_chunk_size=1,
        semantic_max_chunk_size=1000,
    )

    ingestor.ingest_file(str(note_path))

    collection = weaviate_client.collections.get("TheMuses")
    results = collection.query.fetch_objects(limit=50)
    chunks = [
        obj.properties["text"]
        for obj in results.objects
        if obj.properties.get("sourceFile", "").endswith("/semantic_boundary.md")
    ]

    assert len(chunks) >= 2, f"Expected at least 2 chunks, got {len(chunks)}"

    chunk_texts = [text.lower() for text in chunks]
    topic_a_found = any("machine learning" in text for text in chunk_texts)
    topic_b_found = any("project management" in text for text in chunk_texts)

    assert topic_a_found, "Topic A (machine learning) should be present in chunks"
    assert topic_b_found, "Topic B (project management) should be present in chunks"
