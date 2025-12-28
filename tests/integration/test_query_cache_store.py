"""
Integration tests for query cache persistence.
"""

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
