"""
E2E tests for Story 005 semantic routing.

Precondition: Ollama is running with qwen3-embedding:0.6b available.
"""

import tempfile
import time

import pytest

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

        start = time.monotonic()
        first_decision = router.route(
            "What is semantic routing?", result={"answer": "Semantic routing"}
        )
        second_decision = router.route("What is semantic routing?")
        elapsed = time.monotonic() - start

        assert first_decision.cache_hit is False
        assert second_decision.cache_hit is True
        assert elapsed < 2.0
        cache.close()
