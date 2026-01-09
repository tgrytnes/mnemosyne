"""Unit tests for ClusterManager vector handling."""

from __future__ import annotations

import numpy as np

from mnemosyne.cli.cluster import ClusterManager


class _FakeItem:
    def __init__(self, uuid: str, vector):
        self.uuid = uuid
        self.vector = vector


class _FakeCollection:
    def __init__(self, items):
        self._items = items

    def iterator(self, include_vector: bool = False):
        return iter(self._items)


class _FakeCollections:
    def __init__(self, collection):
        self._collection = collection

    def get(self, _name: str):
        return self._collection


class _FakeClient:
    def __init__(self, collection):
        self.collections = _FakeCollections(collection)


def test_fetch_all_vectors_skips_missing_default(caplog):
    items = [
        _FakeItem("uuid-1", {"default": [0.1, 0.2]}),
        _FakeItem("uuid-2", {}),
        _FakeItem("uuid-3", {"default": [0.3, 0.4]}),
    ]
    manager = ClusterManager(_FakeClient(_FakeCollection(items)))

    vectors, uuids = manager.fetch_all_vectors()

    assert uuids == ["uuid-1", "uuid-3"]
    assert np.allclose(vectors, np.array([[0.1, 0.2], [0.3, 0.4]]))
    assert any("skipped" in record.message.lower() for record in caplog.records)
