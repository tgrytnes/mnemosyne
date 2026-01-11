"""
Integration tests for chunking strategies with REAL Ollama and Weaviate.
"""

import pytest

from mnemosyne.aletheia.ingestion_state import IngestionStateTracker
from mnemosyne.aletheia.obsidian_ingestor import ObsidianIngestor
from mnemosyne.config.providers import ProviderConfig
from mnemosyne.providers.factory import create_embedding_provider, create_llm_provider


def _make_vault(tmp_path):
    """Create a test vault with content designed for semantic boundary detection."""
    note = """# Title

Topic A is about machine learning and neural networks. Deep learning has transformed AI.
This section focuses on technical aspects of ML algorithms and their applications.

## Section

Topic B discusses project management and team collaboration. Agile methodologies are important.
This section shifts to organizational topics completely different from the technical content above.
"""
    (tmp_path / "note.md").write_text(note)
    return note


def _collect_chunks_from_weaviate(weaviate_client, collection_name="TheMuses"):
    """Fetch all chunks from Weaviate collection."""
    collection = weaviate_client.collections.get(collection_name)
    results = collection.query.fetch_objects(limit=100)
    return [obj.properties for obj in results.objects]


@pytest.mark.integration
@pytest.mark.weaviate
def test_end_to_end_chunking_pipeline_strategies(
    tmp_path, weaviate_client, clean_weaviate_collection, test_config
):
    """
    REAL INTEGRATION TEST: Ingest same vault with all strategies using actual Ollama LLM.
    Compares how different strategies handle topic boundaries and metadata.
    """
    _make_vault(tmp_path)

    # Use provider system
    provider_config = ProviderConfig(
        llm_provider="ollama",
        embedding_provider="ollama",
        ollama_base_url=test_config["ollama_url"]
    )
    llm_provider = create_llm_provider(provider_config)
    embedding_provider = create_embedding_provider(provider_config)

    results = {}
    for strategy in ("recursive", "semantic", "hybrid"):
        # Clean Weaviate before each strategy
        if weaviate_client.collections.exists("TheMuses"):
            weaviate_client.collections.delete("TheMuses")

        state_tracker = IngestionStateTracker(str(tmp_path / f"{strategy}.db"))
        ingestor = ObsidianIngestor(
            vault_path=str(tmp_path),
            weaviate_client=weaviate_client,
            llm_provider=llm_provider,
            embedding_provider=embedding_provider,
            state_tracker=state_tracker,
            chunking_strategy=strategy,
            chunk_size=1000,
            chunk_overlap=0,
            semantic_min_chunk_size=50,
            section_semantic_min_length=50,
        )
        stats = ingestor.ingest_vault()

        # Collect chunks from Weaviate
        results[strategy] = _collect_chunks_from_weaviate(weaviate_client)

        assert stats["files_processed"] == 1, f"{strategy} should process 1 file"

    # Semantic chunks should not carry heading metadata (pure LLM boundaries)
    assert all(prop.get("headingPath", "") == "" for prop in results["semantic"])

    # Recursive and hybrid should include heading metadata (structure-aware)
    assert any(prop.get("headingPath") for prop in results["recursive"])
    assert all(prop.get("headingPath") for prop in results["hybrid"])

    # Semantic and hybrid should detect topic boundary and create multiple chunks
    # Recursive with large chunk_size might create just 1 chunk
    assert len(results["recursive"]) >= 1
    assert len(results["semantic"]) >= 2, "Semantic should split at topic boundary"
    assert len(results["hybrid"]) >= 2, "Hybrid should split at heading + topic boundaries"
