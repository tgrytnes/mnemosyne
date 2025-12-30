"""
Unit tests for RouterNode.
"""

import tempfile

from mnemosyne.iris.router_node import RouterNode
from mnemosyne.iris.semantic_router import QueryCacheStore, SemanticRouter


def dummy_embedder(text: str) -> list[float]:
    return [float(len(text)), 1.0]


class TestRouterNode:
    def test_returns_error_when_query_missing(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            cache = QueryCacheStore(tmp.name)
            router = SemanticRouter(embedder=dummy_embedder, cache_store=cache)
            node = RouterNode(router)

            result = node({})

            assert result["error"] == "query not provided"
            cache.close()

    def test_populates_cached_result(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            cache = QueryCacheStore(tmp.name)
            cache.upsert(
                "What is routing?",
                [20.0, 1.0],
                {"answer": "cached"},
                source="weaviate",
            )
            router = SemanticRouter(
                embedder=dummy_embedder, cache_store=cache, similarity_threshold=0.9
            )
            node = RouterNode(router)

            result = node({"query": "What is routing?"})

            assert result["cache_hit"] is True
            assert result["route"] == "weaviate"
            assert result["route_source"] == "cache"
            assert result["result"] == {"answer": "cached"}
            cache.close()

    def test_caches_result_when_provided(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            cache = QueryCacheStore(tmp.name)
            router = SemanticRouter(embedder=dummy_embedder, cache_store=cache)
            node = RouterNode(router)

            first = node({"query": "Project status update", "result": {"answer": "done"}})
            assert first["cache_hit"] is False
            assert first["route"] == "ananke"

            second = node({"query": "Project status update"})
            assert second["cache_hit"] is True
            assert second["result"] == {"answer": "done"}
            cache.close()
