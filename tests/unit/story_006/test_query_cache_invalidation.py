"""Unit tests for query cache invalidation by cluster."""

from __future__ import annotations

from mnemosyne.iris.semantic_router import QueryCacheStore


def test_invalidate_by_cluster_ids(tmp_path) -> None:
    cache_path = tmp_path / "cache.db"
    store = QueryCacheStore(str(cache_path))

    store.upsert(
        "query-1",
        [0.1, 0.2],
        {"cluster_id": "alpha"},
        source="weaviate",
    )
    store.upsert(
        "query-2",
        [0.2, 0.3],
        {"cluster_ids": ["beta", "gamma"]},
        source="weaviate",
    )
    store.upsert(
        "query-3",
        [0.3, 0.4],
        {"topic": "unrelated"},
        source="weaviate",
    )

    removed = store.invalidate_by_cluster_ids(["alpha"])
    assert removed == 1
    remaining = [row["query_text"] for row in store.get_all()]
    assert "query-1" not in remaining

    removed = store.invalidate_by_cluster_ids(["gamma"])
    assert removed == 1
    remaining = [row["query_text"] for row in store.get_all()]
    assert "query-2" not in remaining
    assert "query-3" in remaining

    store.close()
