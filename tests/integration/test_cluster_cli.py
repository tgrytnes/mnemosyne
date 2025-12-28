# tests/integration/test_cluster_cli.py

import subprocess
import sys
import uuid

import numpy as np
import pytest

from mnemosyne.alexandria.weaviate_schema import (
    ClusterCentroidCollection,
    TheMuses,
    WeaviateSchemaManager,
)
from mnemosyne.cli.cluster import ClusterManager, run_clustering

# Mark all tests in this file as integration tests
pytestmark = [pytest.mark.integration, pytest.mark.weaviate]


@pytest.fixture(scope="module")
def weaviate_collections(weaviate_client):
    """Ensure Weaviate collections are created and cleaned up for the module."""
    schema_manager = WeaviateSchemaManager(weaviate_client)

    # Ensure collections exist
    schema_manager.ensure_collection_exists(TheMuses.collection_name)
    schema_manager.ensure_collection_exists(ClusterCentroidCollection.collection_name)

    yield

    # Teardown: delete collections
    if weaviate_client.collections.exists(TheMuses.collection_name):
        weaviate_client.collections.delete(TheMuses.collection_name)
    if weaviate_client.collections.exists(ClusterCentroidCollection.collection_name):
        weaviate_client.collections.delete(ClusterCentroidCollection.collection_name)


@pytest.fixture(autouse=True)
def clean_collections_before_test(weaviate_client, weaviate_collections):
    """Clean data from collections before each test."""
    # Delete and recreate collections to ensure clean state
    if weaviate_client.collections.exists(TheMuses.collection_name):
        weaviate_client.collections.delete(TheMuses.collection_name)
    if weaviate_client.collections.exists(ClusterCentroidCollection.collection_name):
        weaviate_client.collections.delete(ClusterCentroidCollection.collection_name)

    # Recreate collections
    schema_manager = WeaviateSchemaManager(weaviate_client)
    schema_manager.ensure_collection_exists(TheMuses.collection_name)
    schema_manager.ensure_collection_exists(ClusterCentroidCollection.collection_name)


def test_fetch_all_vectors(weaviate_client):
    """Test fetching all vectors from Weaviate with real data."""
    # Setup: Add test vectors
    muses = weaviate_client.collections.get(TheMuses.collection_name)
    test_vectors = [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]

    with muses.batch.dynamic() as batch:
        for i, vec in enumerate(test_vectors):
            batch.add_object(
                properties={"text": f"chunk {i}", "chunkIndex": i}, vector=vec, uuid=uuid.uuid4()
            )

    # Test
    manager = ClusterManager(weaviate_client)
    vectors, uuids = manager.fetch_all_vectors()

    # Assertions
    assert isinstance(vectors, np.ndarray)
    assert vectors.shape == (3, 2)
    assert len(uuids) == 3
    # Verify vectors match (order may vary)
    assert np.allclose(np.sort(vectors.flatten()), np.sort(np.array(test_vectors).flatten()))


def test_run_kmeans_clustering(weaviate_client):
    """Test K-Means clustering logic with real vectors."""
    # Setup: Add test vectors (2 clear clusters)
    muses = weaviate_client.collections.get(TheMuses.collection_name)
    cluster1 = [[0.1, 0.1], [0.2, 0.2]]
    cluster2 = [[0.8, 0.8], [0.9, 0.9]]
    all_vectors = cluster1 + cluster2

    with muses.batch.dynamic() as batch:
        for i, vec in enumerate(all_vectors):
            batch.add_object(
                properties={"text": f"chunk {i}", "chunkIndex": i}, vector=vec, uuid=uuid.uuid4()
            )

    # Test
    manager = ClusterManager(weaviate_client)
    vectors, uuids = manager.fetch_all_vectors()
    labels, centroids = manager.run_kmeans_clustering(vectors, n_clusters=2)

    # Assertions
    assert labels.shape == (4,)
    assert centroids.shape == (2, 2)

    # Verify clustering quality: vectors should form 2 distinct groups
    # Count how many unique labels exist
    unique_labels = set(labels)
    assert len(unique_labels) == 2, "Should have exactly 2 clusters"

    # Verify each cluster has 2 members (since we have 4 vectors and 2 clusters)
    label_counts = {label: np.sum(labels == label) for label in unique_labels}
    assert all(count == 2 for count in label_counts.values()), "Each cluster should have 2 vectors"


def test_update_chunk_cluster_ids(weaviate_client):
    """Test updating chunks with their cluster IDs."""
    # Setup: Add test chunks
    muses = weaviate_client.collections.get(TheMuses.collection_name)
    test_uuids = [uuid.uuid4() for _ in range(3)]

    with muses.batch.dynamic() as batch:
        for i, uid in enumerate(test_uuids):
            batch.add_object(
                properties={"text": f"chunk {i}", "chunkIndex": i},
                vector=[0.1 * i, 0.2 * i],
                uuid=uid,
            )

    # Test
    manager = ClusterManager(weaviate_client)
    labels = np.array([0, 1, 0])
    manager.update_chunk_cluster_ids([str(uid) for uid in test_uuids], labels)

    # Verify cluster IDs were assigned
    for i, uid in enumerate(test_uuids):
        obj = muses.query.fetch_object_by_id(uid)
        assert obj.properties["clusterId"] == int(labels[i])


def test_update_centroids(weaviate_client):
    """Test storing the calculated centroids."""
    # Setup
    manager = ClusterManager(weaviate_client)
    centroids = np.array([[0.1, 0.2], [0.8, 0.9]])
    labels = np.array([0, 1, 0, 1, 0])

    # Test
    manager.update_centroids(centroids, labels)

    # Verify centroids were stored
    centroid_collection = weaviate_client.collections.get(ClusterCentroidCollection.collection_name)
    stored_centroids = centroid_collection.query.fetch_objects(
        limit=10, include_vector=True
    ).objects

    assert len(stored_centroids) == 2

    # Verify cluster 0 (3 items)
    cluster0 = [c for c in stored_centroids if c.properties["clusterId"] == 0][0]
    assert cluster0.properties["clusterSize"] == 3
    assert np.allclose(cluster0.vector["default"], [0.1, 0.2])

    # Verify cluster 1 (2 items)
    cluster1 = [c for c in stored_centroids if c.properties["clusterId"] == 1][0]
    assert cluster1.properties["clusterSize"] == 2
    assert np.allclose(cluster1.vector["default"], [0.8, 0.9])


def test_run_clustering_orchestration(weaviate_client):
    """Test that run_clustering correctly orchestrates the clustering process."""
    # Setup: Add test data (10 vectors, 2 clusters)
    muses = weaviate_client.collections.get(TheMuses.collection_name)
    cluster1_vecs = [[0.1 + i * 0.01, 0.1 + i * 0.01] for i in range(5)]
    cluster2_vecs = [[0.8 + i * 0.01, 0.8 + i * 0.01] for i in range(5)]
    all_vecs = cluster1_vecs + cluster2_vecs

    with muses.batch.dynamic() as batch:
        for i, vec in enumerate(all_vecs):
            batch.add_object(
                properties={"text": f"chunk {i}", "chunkIndex": i}, vector=vec, uuid=uuid.uuid4()
            )

    # Test
    run_clustering(n_clusters=2)

    # Verify: All chunks have cluster IDs
    chunks_with_clusters = muses.query.fetch_objects(limit=20).objects
    for chunk in chunks_with_clusters:
        assert "clusterId" in chunk.properties
        assert chunk.properties["clusterId"] in [0, 1]

    # Verify: Centroids were stored
    centroids = weaviate_client.collections.get(
        ClusterCentroidCollection.collection_name
    ).query.fetch_objects(limit=10)
    assert centroids.objects  # Should have centroids
    assert len(centroids.objects) == 2


def test_cli_validation_rejects_invalid_n_clusters():
    """Test CLI validation for invalid n_clusters parameter."""
    # Test: n_clusters = 0 (should fail)
    result = subprocess.run(
        [sys.executable, "-m", "mnemosyne.cli.cluster", "run", "--n-clusters", "0"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "Invalid n_clusters" in result.stderr or "Must be >= 1" in result.stderr

    # Test: n_clusters = -1 (should fail)
    result = subprocess.run(
        [sys.executable, "-m", "mnemosyne.cli.cluster", "run", "--n-clusters", "-1"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0


def test_cli_help_displays_correctly():
    """Test that CLI help message displays correctly."""
    # Test main help
    result = subprocess.run(
        [sys.executable, "-m", "mnemosyne.cli.cluster", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Mnemosyne - Chunk Clustering" in result.stdout
    assert "run" in result.stdout

    # Test subcommand help to verify --n-clusters argument
    result = subprocess.run(
        [sys.executable, "-m", "mnemosyne.cli.cluster", "run", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--n-clusters" in result.stdout
