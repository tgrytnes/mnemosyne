# tests/unit/test_cluster_representatives_node.py

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# from mnemosyne.argus.nodes.cluster_representatives import GetClusterRepresentatives
# from mnemosyne.alexandria.the_gates.chunk_representation import ChunkRepresentation

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_weaviate_client():
    """Fixture for a mocked Weaviate client."""
    return MagicMock()


@pytest.fixture
def node(mock_weaviate_client):
    """Fixture for the GetClusterRepresentatives node."""
    from mnemosyne.argus.nodes.cluster_representatives import GetClusterRepresentatives

    return GetClusterRepresentatives(client=mock_weaviate_client)


def test_state_missing_cluster_id(node):
    """Test that the node returns an error if cluster_id is missing from the state."""
    state = {}
    result_state = node(state)
    assert result_state["error"] == "cluster_id not found in state"
    assert result_state["representative_chunks"] == []


def test_get_cached_centroid(node, mock_weaviate_client):
    """Test that the node uses a cached centroid if available."""
    state = {"cluster_id": 1}

    mock_centroid_obj = MagicMock()
    mock_centroid_obj.vector = {"default": [0.1, 0.2, 0.3]}
    mock_weaviate_client.collections.get.return_value.query.fetch_objects.return_value.objects = [
        mock_centroid_obj
    ]

    # Mock the near_vector query result
    mock_weaviate_client.collections.get.return_value.query.near_vector.return_value.objects = []

    node(state)

    # Verify that it queried the centroid collection
    mock_weaviate_client.collections.get.return_value.query.fetch_objects.assert_called_once()

    # Verify it used the cached vector in the near_vector query
    mock_weaviate_client.collections.get.return_value.query.near_vector.assert_called_once_with(
        near_vector=[0.1, 0.2, 0.3],
        limit=5,
        return_metadata=["distance"],
    )


def test_compute_centroid_on_the_fly(node, mock_weaviate_client):
    """Test that the node computes a centroid if one is not cached."""
    state = {"cluster_id": 1}

    # No cached centroid
    mock_weaviate_client.collections.get.return_value.query.fetch_objects.return_value.objects = []

    # Mock the iterator for on-the-fly calculation
    mock_item1 = MagicMock()
    mock_item1.vector = {"default": [0.1, 0.2]}
    mock_item2 = MagicMock()
    mock_item2.vector = {"default": [0.3, 0.4]}
    iterator_mock = mock_weaviate_client.collections.get.return_value.iterator
    iterator_mock.return_value = [mock_item1, mock_item2]

    # Mock the near_vector query result
    mock_weaviate_client.collections.get.return_value.query.near_vector.return_value.objects = []

    node(state)

    # Verify it tried to get a cached centroid
    mock_weaviate_client.collections.get.return_value.query.fetch_objects.assert_called_once()

    # Verify it iterated over the muses collection to compute the centroid
    iterator_mock.assert_called_once()

    # Verify it used the computed centroid in the near_vector query (mean of vectors)
    computed_centroid = np.mean([[0.1, 0.2], [0.3, 0.4]], axis=0).tolist()
    mock_weaviate_client.collections.get.return_value.query.near_vector.assert_called_once_with(
        near_vector=computed_centroid,
        limit=5,
        return_metadata=["distance"],
    )


def test_maps_and_sorts_results(node, mock_weaviate_client):
    """Test that the node correctly maps Weaviate objects to ChunkRepresentation and sorts them."""
    from mnemosyne.alexandria.the_gates.chunk_representation import ChunkRepresentation

    state = {"cluster_id": 1}

    # Mock centroid
    mock_centroid_obj = MagicMock()
    mock_centroid_obj.vector = {"default": [0.1, 0.2]}
    mock_weaviate_client.collections.get.return_value.query.fetch_objects.return_value.objects = [
        mock_centroid_obj
    ]

    # Mock near_vector results
    obj1 = MagicMock()
    obj1.uuid = "uuid1"
    obj1.properties = {
        "sourceFile": "file1.md",
        "text": "text1",
        "headingPath": "/h1",
        "chunkIndex": 1,
    }
    obj1.metadata.distance = 0.5

    obj2 = MagicMock()
    obj2.uuid = "uuid2"
    obj2.properties = {
        "sourceFile": "file2.md",
        "text": "text2",
        "headingPath": "/h2",
        "chunkIndex": 0,
    }
    obj2.metadata.distance = 0.5  # Same distance

    obj3 = MagicMock()
    obj3.uuid = "uuid3"
    obj3.properties = {
        "sourceFile": "file3.md",
        "text": "text3",
        "headingPath": "/h3",
        "chunkIndex": 2,
    }
    obj3.metadata.distance = 0.4  # Lower distance

    mock_weaviate_client.collections.get.return_value.query.near_vector.return_value.objects = [
        obj1,
        obj2,
        obj3,
    ]

    result_state = node(state)

    chunks = result_state["representative_chunks"]
    assert len(chunks) == 3
    assert isinstance(chunks[0], ChunkRepresentation)

    # Check that text is truncated
    assert chunks[0].text == "text3"[:200]

    # Check sorting: obj3 should be first (lower distance), then obj2 (lower chunk_index), then obj1
    assert chunks[0].chunk_id == "uuid3"
    assert chunks[1].chunk_id == "uuid2"
    assert chunks[2].chunk_id == "uuid1"


def test_empty_cluster_returns_empty_list(node, mock_weaviate_client):
    """Test that an empty cluster (no vectors) returns empty representative_chunks."""
    state = {"cluster_id": 999}

    # No cached centroid
    mock_weaviate_client.collections.get.return_value.query.fetch_objects.return_value.objects = []

    # Iterator returns empty list (no chunks in cluster)
    mock_weaviate_client.collections.get.return_value.iterator.return_value = []

    result_state = node(state)

    # Should return empty list, not error
    assert result_state["representative_chunks"] == []
    assert "error" not in result_state or result_state["error"] is None


def test_cluster_with_fewer_than_5_chunks(node, mock_weaviate_client):
    """Test behavior when cluster has only 3 chunks (< 5 requested)."""
    from mnemosyne.alexandria.the_gates.chunk_representation import ChunkRepresentation

    state = {"cluster_id": 1}

    # Mock centroid
    mock_centroid_obj = MagicMock()
    mock_centroid_obj.vector = {"default": [0.1, 0.2]}
    mock_weaviate_client.collections.get.return_value.query.fetch_objects.return_value.objects = [
        mock_centroid_obj
    ]

    # Mock near_vector results with only 3 chunks
    obj1 = MagicMock()
    obj1.uuid = "uuid1"
    obj1.properties = {
        "sourceFile": "file1.md",
        "text": "text1",
        "headingPath": "/h1",
        "chunkIndex": 0,
    }
    obj1.metadata.distance = 0.1

    obj2 = MagicMock()
    obj2.uuid = "uuid2"
    obj2.properties = {
        "sourceFile": "file2.md",
        "text": "text2",
        "headingPath": "/h2",
        "chunkIndex": 1,
    }
    obj2.metadata.distance = 0.2

    obj3 = MagicMock()
    obj3.uuid = "uuid3"
    obj3.properties = {
        "sourceFile": "file3.md",
        "text": "text3",
        "headingPath": "/h3",
        "chunkIndex": 2,
    }
    obj3.metadata.distance = 0.3

    mock_weaviate_client.collections.get.return_value.query.near_vector.return_value.objects = [
        obj1,
        obj2,
        obj3,
    ]

    result_state = node(state)

    # Should return 3 chunks (not error)
    chunks = result_state["representative_chunks"]
    assert len(chunks) == 3
    assert isinstance(chunks[0], ChunkRepresentation)
    assert chunks[0].chunk_id == "uuid1"  # Closest to centroid
