"""
Unit tests for semantic routing logic.
"""

import tempfile
import time

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

    def test_cache_miss_routes_to_web(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            cache = QueryCacheStore(tmp.name)
            router = SemanticRouter(embedder=dummy_embedder, cache_store=cache)

            decision = router.route("latest news on semantic routing")

            assert decision.cache_hit is False
            assert decision.route == "web"

            cache.close()

    def test_cache_miss_defaults_to_weaviate(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            cache = QueryCacheStore(tmp.name)
            router = SemanticRouter(embedder=dummy_embedder, cache_store=cache)

            decision = router.route("semantic search for knowledge graphs")

            assert decision.cache_hit is False
            assert decision.route == "weaviate"

            cache.close()

    def test_similarity_threshold_blocks_cache_hit(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            cache = QueryCacheStore(tmp.name)
            cache.upsert("query", [1.0, 0.0], {"answer": "cached"}, source="weaviate")

            def orthogonal_embedder(_: str) -> list[float]:
                return [0.0, 1.0]

            router = SemanticRouter(
                embedder=orthogonal_embedder,
                cache_store=cache,
                similarity_threshold=0.95,
            )

            decision = router.route("query")

            assert decision.cache_hit is False
            assert decision.route == "weaviate"

            cache.close()

    def test_default_similarity_threshold(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            cache = QueryCacheStore(tmp.name)
            router = SemanticRouter(embedder=dummy_embedder, cache_store=cache)

            assert router.similarity_threshold == 0.95
            cache.close()

    def test_invalidate_cache_removes_stale(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            cache = QueryCacheStore(tmp.name)
            cache.upsert("old query", [1.0, 1.0], {"answer": "old"}, source="cache")
            cache._conn.execute("UPDATE query_cache SET created_at = datetime('now', '-10 days')")
            cache._conn.commit()

            router = SemanticRouter(embedder=dummy_embedder, cache_store=cache, cache_ttl_days=7)
            removed = router.invalidate_cache()

            assert removed == 1
            cache.close()

    def test_invalidation_forces_weaviate_route(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            cache = QueryCacheStore(tmp.name)
            cache.upsert("stale query", [1.0, 1.0], {"answer": "old"}, source="cache")
            cache._conn.execute("UPDATE query_cache SET created_at = datetime('now', '-10 days')")
            cache._conn.commit()

            router = SemanticRouter(embedder=dummy_embedder, cache_store=cache, cache_ttl_days=7)
            router.invalidate_cache()
            decision = router.route("stale query")

            assert decision.cache_hit is False
            assert decision.route == "weaviate"
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

    def test_cache_hit_rate_updates(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            cache = QueryCacheStore(tmp.name)
            cache.upsert("cached query", [1.0, 0.0], {"answer": "cached"}, source="weaviate")

            def selective_embedder(text: str) -> list[float]:
                return [1.0, 0.0] if text == "cached query" else [0.0, 1.0]

            router = SemanticRouter(
                embedder=selective_embedder,
                cache_store=cache,
                similarity_threshold=0.9,
            )
            router.route("cached query")
            router.route("fresh query")

            stats = router.get_cache_stats()
            assert stats.hits == 1
            assert stats.misses == 1
            assert stats.hit_rate == 0.5
            cache.close()

    def test_routing_decision_performance(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            cache = QueryCacheStore(tmp.name)
            router = SemanticRouter(embedder=dummy_embedder, cache_store=cache)

            start = time.monotonic()
            router.route("performance check")
            elapsed = time.monotonic() - start

            assert elapsed < 0.1
            cache.close()
