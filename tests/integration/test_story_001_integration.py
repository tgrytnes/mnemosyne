# tests/integration/test_story_001_integration.py
import uuid

import numpy as np
import pytest

from mnemosyne.alexandria.weaviate_schema import (
    ClusterCentroidCollection,
    TheMuses,
    WeaviateSchemaManager,
)
from mnemosyne.argus.nodes.cluster_representatives import GetClusterRepresentatives
from mnemosyne.cli.cluster import run_clustering

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


def test_clustering_and_representation_pipeline(weaviate_client):
    """
    Tests the full pipeline:
    1. Ingest data into Weaviate.
    2. Run clustering.
    3. Verify clustering results.
    4. Get representative chunks for a cluster.
    """
    # 1. Ingest test data
    muses_collection = weaviate_client.collections.get(TheMuses.collection_name)
    np.random.seed(42)

    cluster1_vectors = np.random.rand(5, 10) + np.array([0, 1, 0, 1, 0, 1, 0, 1, 0, 1])
    cluster2_vectors = np.random.rand(5, 10) + np.array([1, 0, 1, 0, 1, 0, 1, 0, 1, 0])
    all_vectors = np.vstack([cluster1_vectors, cluster2_vectors])

    with muses_collection.batch.dynamic() as batch:
        for i, vector in enumerate(all_vectors):
            batch.add_object(
                properties={"text": f"This is chunk {i}", "chunkIndex": i},
                vector=vector.tolist(),
                uuid=uuid.uuid4(),
            )

    assert muses_collection.aggregate.over_all(total_count=True).total_count == 10

    # 2. Run clustering
    run_clustering(n_clusters=2)

    # 3. Verify clustering results
    centroid_collection = weaviate_client.collections.get(ClusterCentroidCollection.collection_name)
    assert centroid_collection.aggregate.over_all(total_count=True).total_count == 2

    # 4. Get representative chunks for a cluster
    node = GetClusterRepresentatives(client=weaviate_client)

    first_chunk_props = muses_collection.query.fetch_objects(limit=1).objects[0].properties
    cluster1_id = first_chunk_props["clusterId"]

    state = {"cluster_id": cluster1_id}
    result_state = node(state)

    assert "error" not in result_state or result_state["error"] is None
    representative_chunks = result_state["representative_chunks"]

    assert len(representative_chunks) == 5
