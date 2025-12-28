"""
Integration-style performance test for hybrid chunking ingestion.
"""

import time

import pytest

from mnemosyne.aletheia.obsidian_ingestor import ObsidianIngestor


@pytest.mark.performance
def test_hybrid_ingestion_performance(tmp_path, mocker):
    """Hybrid ingestion should handle 100 small files quickly with mocked LLM."""
    for i in range(100):
        (tmp_path / f"note-{i}.md").write_text(f"# Note {i}\n\nContent {i}.")

    mock_weaviate = mocker.MagicMock()
    mock_collection = mock_weaviate.collections.get.return_value
    mock_collection.data.insert.return_value = None
    mock_ollama = mocker.MagicMock()
    mock_ollama.generate.return_value = {"response": '{"boundaries": [10]}'}
    mock_ollama.embeddings.return_value = {"embedding": [0.1] * 1024}

    mocker.patch(
        "mnemosyne.aletheia.obsidian_ingestor.WeaviateSchemaManager.ensure_collection_exists",
        return_value=None,
    )

    ingestor = ObsidianIngestor(
        vault_path=str(tmp_path),
        weaviate_client=mock_weaviate,
        ollama_client=mock_ollama,
        chunking_strategy="hybrid",
        section_semantic_min_length=0,
        semantic_min_chunk_size=1,
    )

    start = time.monotonic()
    stats = ingestor.ingest_vault()
    elapsed = time.monotonic() - start

    assert stats["files_processed"] == 100
    assert elapsed < 5.0
