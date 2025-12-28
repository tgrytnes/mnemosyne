"""
Unit tests for semantic routing logic.
"""

import tempfile

from mnemosyne.iris.semantic_router import QueryCacheStore, RoutingDecision, SemanticRouter


def dummy_embedder(text: str) -> list[float]:
    return [float(len(text)), 1.0]


class TestSemanticRouter:
    """Test routing decisions and cache behavior."""

    def test_cache_hit_returns_cached_result(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            cache = QueryCacheStore(tmp.name)
            cache.upsert(
                "What is LangGraph?",
                [10.0, 1.0],
                {"answer": "cached"},
                source="weaviate",
            )

            router = SemanticRouter(
                embedder=dummy_embedder, cache_store=cache, similarity_threshold=0.9
            )
            decision = router.route("What is LangGraph?")

            assert isinstance(decision, RoutingDecision)
            assert decision.cache_hit is True
            assert decision.source == "cache"
            assert decision.result == {"answer": "cached"}

            cache.close()

    def test_cache_miss_routes_by_classifier(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            cache = QueryCacheStore(tmp.name)
            router = SemanticRouter(embedder=dummy_embedder, cache_store=cache)

            decision = router.route("Project status update")

            assert decision.cache_hit is False
            assert decision.route == "ananke"

            cache.close()

    def test_invalidate_cache_removes_stale(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            cache = QueryCacheStore(tmp.name)
            cache.upsert("old query", [1.0, 1.0], {"answer": "old"}, source="cache")
            cache._conn.execute(
                "UPDATE query_cache SET created_at = datetime('now', '-10 days')"
            )
            cache._conn.commit()

            router = SemanticRouter(
                embedder=dummy_embedder, cache_store=cache, cache_ttl_days=7
            )
            removed = router.invalidate_cache()

            assert removed == 1
            cache.close()

    def test_cache_stats_track_hits_and_misses(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            cache = QueryCacheStore(tmp.name)
            router = SemanticRouter(embedder=dummy_embedder, cache_store=cache)

            router.route("Uncached query")
            stats = router.get_cache_stats()

            assert stats.misses == 1
            assert stats.hits == 0
            cache.close()
