"""
Integration tests for query cache persistence.
"""

import json
import tempfile

import pytest

from mnemosyne.iris.semantic_router import QueryCacheStore


@pytest.mark.integration
def test_query_cache_persistence_roundtrip():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        store = QueryCacheStore(tmp.name)
        store.upsert("query", [0.1, 0.2], {"answer": "ok"}, source="weaviate")
        store.close()

        reopened = QueryCacheStore(tmp.name)
        rows = reopened.get_all()
        assert len(rows) == 1
        assert rows[0]["query_text"] == "query"
        reopened.close()


@pytest.mark.integration
def test_query_cache_indices_exist():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        store = QueryCacheStore(tmp.name)
        indexes = store._conn.execute("PRAGMA index_list('query_cache')").fetchall()
        index_names = {row[1] for row in indexes}

        assert "idx_query_hash" in index_names
        assert "idx_last_accessed" in index_names
        store.close()


@pytest.mark.integration
def test_query_cache_access_count_updates():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        store = QueryCacheStore(tmp.name)
        store.upsert("query", [0.1, 0.2], {"answer": "ok"}, source="weaviate")

        row = store.get_all()[0]
        assert row["access_count"] == 1

        store.update_access(row["id"])

        updated = store.get_all()[0]
        assert updated["access_count"] == 2
        assert updated["last_accessed"] is not None
        store.close()


@pytest.mark.integration
def test_query_cache_deletes_stale_entries():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        store = QueryCacheStore(tmp.name)
        store.upsert("query", [0.1, 0.2], {"answer": "ok"}, source="weaviate")

        store._conn.execute("UPDATE query_cache SET created_at = datetime('now', '-10 days')")
        store._conn.commit()

        removed = store.delete_stale(max_age_days=7)
        assert removed == 1
        store.close()


@pytest.mark.integration
def test_query_cache_serializes_embedding_and_result():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        store = QueryCacheStore(tmp.name)
        embedding = [0.3, 0.4]
        result = {"answer": "ok", "matches": [1, 2, 3]}

        store.upsert("query", embedding, result, source="weaviate")
        row = store.get_all()[0]

        assert json.loads(row["query_embedding"]) == embedding
        assert json.loads(row["result_json"]) == result
        assert row["created_at"] is not None
        assert row["last_accessed"] is not None
        store.close()
