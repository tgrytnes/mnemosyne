"""
E2E tests for Story 005 semantic routing.
"""

import tempfile
import time

import pytest

from mnemosyne.iris.semantic_router import QueryCacheStore, SemanticRouter


def simple_embedder(text: str) -> list[float]:
    return [float(len(text)), 1.0]


@pytest.mark.e2e
def test_story_005_end_to_end_routing_flow():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        cache = QueryCacheStore(tmp.name)
        router = SemanticRouter(embedder=simple_embedder, cache_store=cache)

        start = time.monotonic()
        first_decision = router.route(
            "What is semantic routing?", result={"answer": "Semantic routing"}
        )
        second_decision = router.route("What is semantic routing?")
        elapsed = time.monotonic() - start

        assert first_decision.cache_hit is False
        assert second_decision.cache_hit is True
        assert elapsed < 0.1
        cache.close()
