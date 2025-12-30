"""
E2E tests for Story 005 semantic routing.

Precondition: Ollama is running with qwen3-embedding:0.6b available.
"""

import tempfile
import time

import pytest

from mnemosyne.aletheia.ingestion_state import IngestionStateTracker
from mnemosyne.aletheia.obsidian_ingestor import ObsidianIngestor
from mnemosyne.iris.semantic_router import QueryCacheStore, SemanticRouter


def ollama_embedder(ollama_client, text: str) -> list[float]:
    response = ollama_client.embeddings(model="qwen3-embedding:0.6b", prompt=text)
    return response["embedding"]


@pytest.mark.e2e
def test_story_005_end_to_end_routing_flow(ollama_client):
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        cache = QueryCacheStore(tmp.name)
        router = SemanticRouter(
            embedder=lambda text: ollama_embedder(ollama_client, text),
            cache_store=cache,
        )

        first_decision = router.route(
            "What is semantic routing?", result={"answer": "Semantic routing"}
        )
        second_decision = router.route("What is semantic routing?")

        assert first_decision.cache_hit is False
        assert second_decision.cache_hit is True
        cache.close()


@pytest.mark.e2e
@pytest.mark.weaviate
def test_story_005_system_routing_with_real_services(
    tmp_path,
    weaviate_client,
    ollama_client,
    fake_vault_path,
    clean_weaviate_collection,
):
    """
    REAL E2E TEST: Ingest vault, query Weaviate, cache result, then route from cache.
    """
    state_tracker = IngestionStateTracker(str(tmp_path / "ingestion_state.db"))
    ingestor = ObsidianIngestor(
        vault_path=str(fake_vault_path),
        weaviate_client=weaviate_client,
        ollama_client=ollama_client,
        state_tracker=state_tracker,
        chunking_strategy="recursive",
        chunk_size=400,
        chunk_overlap=100,
    )

    stats = ingestor.ingest_vault()
    assert stats["total_chunks"] > 0

    query = "semantic search for knowledge graph notes"
    query_embedding = ollama_embedder(ollama_client, query)

    collection = weaviate_client.collections.get("TheMuses")
    response = collection.query.near_vector(near_vector=query_embedding, limit=3)
    assert response.objects

    result_payload = {"matches": [obj.properties for obj in response.objects]}

    cache = QueryCacheStore(str(tmp_path / "router_cache.db"))
    router = SemanticRouter(
        embedder=lambda text: ollama_embedder(ollama_client, text),
        cache_store=cache,
    )

    decision = router.route(query, result=result_payload)
    assert decision.cache_hit is False
    assert decision.route == "weaviate"
    assert decision.result["matches"]

    cached_decision = router.route(query)
    assert cached_decision.cache_hit is True
    assert cached_decision.source == "cache"
    assert cached_decision.result["matches"]

    cache.close()
    state_tracker.close()
