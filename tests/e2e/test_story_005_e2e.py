"""
E2E tests for Story 005 semantic routing.

Precondition: Ollama is running with qwen3-embedding:0.6b available.
"""

import tempfile

import pytest

from mnemosyne.aletheia.ingestion_state import IngestionStateTracker
from mnemosyne.aletheia.obsidian_ingestor import ObsidianIngestor
from mnemosyne.iris.router_node import RouterNode
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

        node = RouterNode(router)
        first_state = node(
            {"query": "What is semantic routing?", "result": {"answer": "Semantic routing"}}
        )
        second_state = node({"query": "What is semantic routing?"})

        assert first_state["cache_hit"] is False
        assert second_state["cache_hit"] is True
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
    response = collection.query.near_vector(
        near_vector=query_embedding, limit=3, target_vector="default"
    )
    assert response.objects

    result_payload = {"matches": [obj.properties for obj in response.objects]}

    cache = QueryCacheStore(str(tmp_path / "router_cache.db"))
    router = SemanticRouter(
        embedder=lambda text: ollama_embedder(ollama_client, text),
        cache_store=cache,
    )

    node = RouterNode(router)
    decision_state = node({"query": query, "result": result_payload})
    assert decision_state["cache_hit"] is False
    assert decision_state["route"] == "weaviate"
    assert decision_state["result"]["matches"]

    cached_state = node({"query": query})
    assert cached_state["cache_hit"] is True
    assert cached_state["route_source"] == "cache"
    assert cached_state["result"]["matches"]

    cache.close()
    state_tracker.close()
