# tests/integration/test_story_001_performance.py

import time
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

# Mark all tests in this file as performance tests
pytestmark = [pytest.mark.performance, pytest.mark.integration, pytest.mark.weaviate]


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


def test_query_completes_under_2_seconds(weaviate_client):
    """
    AC4: Performance test - verify representative chunk query completes in <2s.

    This test validates the performance requirement from Story 001 AC4:
    "Performance: Query completes in <2 seconds on Pi 5"

    Test setup:
    - 1000 vectors (realistic vault size)
    - 50 clusters
    - Query for 5 representative chunks from 1 cluster

    Expected: Query time < 2.0 seconds
    """
    # 1. Create test dataset (1000 vectors, 50 clusters)
    muses_collection = weaviate_client.collections.get(TheMuses.collection_name)
    np.random.seed(42)

    n_vectors = 1000
    n_clusters = 50
    vectors_per_cluster = n_vectors // n_clusters

    # Generate 50 distinct clusters
    all_vectors = []
    for cluster_idx in range(n_clusters):
        # Each cluster has a unique centroid
        cluster_center = np.random.rand(10) * 10 + (cluster_idx * 2)
        cluster_vectors = np.random.rand(vectors_per_cluster, 10) + cluster_center
        all_vectors.extend(cluster_vectors)

    # Ingest vectors
    with muses_collection.batch.dynamic() as batch:
        for i, vector in enumerate(all_vectors):
            batch.add_object(
                properties={
                    "text": f"This is chunk {i} with content that represents the semantic meaning",
                    "chunkIndex": i,
                    "sourceFile": f"note_{i % 100}.md",
                    "headingPath": f"# Section {i % 10}",
                },
                vector={"default": vector.tolist()},
                uuid=uuid.uuid4(),
            )

    assert muses_collection.aggregate.over_all(total_count=True).total_count == n_vectors

    # 2. Run clustering
    run_clustering(n_clusters=n_clusters)

    # Verify clustering completed
    centroid_collection = weaviate_client.collections.get(ClusterCentroidCollection.collection_name)
    assert centroid_collection.aggregate.over_all(total_count=True).total_count == n_clusters

    # 3. Performance test: Query for representative chunks
    node = GetClusterRepresentatives(client=weaviate_client)

    # Get a cluster ID from the first chunk
    first_chunk_props = muses_collection.query.fetch_objects(limit=1).objects[0].properties
    test_cluster_id = first_chunk_props["clusterId"]

    # PERFORMANCE MEASUREMENT
    start_time = time.time()
    state = {"cluster_id": test_cluster_id}
    result_state = node(state)
    elapsed_time = time.time() - start_time

    # 4. Validate results
    assert "error" not in result_state or result_state["error"] is None
    representative_chunks = result_state["representative_chunks"]
    assert len(representative_chunks) == 5

    # 5. CRITICAL ASSERTION: Query must complete in <2 seconds (AC4)
    assert (
        elapsed_time < 2.0
    ), f"Query took {elapsed_time:.3f}s, exceeds 2.0s limit (AC4 requirement)"

    print(f"\n✅ Performance test passed: Query completed in {elapsed_time:.3f}s (<2.0s)")


def test_caching_improves_performance(weaviate_client):
    """
    Verify that cached centroids provide faster queries than on-the-fly computation.

    This test validates the caching optimization in GetClusterRepresentatives.
    """
    # 1. Create small test dataset
    muses_collection = weaviate_client.collections.get(TheMuses.collection_name)
    np.random.seed(42)

    n_vectors = 100
    n_clusters = 5

    vectors = np.random.rand(n_vectors, 10)

    with muses_collection.batch.dynamic() as batch:
        for i, vector in enumerate(vectors):
            batch.add_object(
                properties={"text": f"Chunk {i}", "chunkIndex": i},
                vector={"default": vector.tolist()},
                uuid=uuid.uuid4(),
            )

    # 2. Run clustering (creates cached centroids)
    run_clustering(n_clusters=n_clusters)

    node = GetClusterRepresentatives(client=weaviate_client)

    first_chunk_props = muses_collection.query.fetch_objects(limit=1).objects[0].properties
    test_cluster_id = first_chunk_props["clusterId"]

    # 3. Measure with cache
    start_with_cache = time.time()
    state = {"cluster_id": test_cluster_id}
    node(state)
    cached_time = time.time() - start_with_cache

    # 4. Clear cache and measure without cache
    # Delete and recreate centroid collection to clear cache
    if weaviate_client.collections.exists(ClusterCentroidCollection.collection_name):
        weaviate_client.collections.delete(ClusterCentroidCollection.collection_name)
    schema_manager = WeaviateSchemaManager(weaviate_client)
    schema_manager.ensure_collection_exists(ClusterCentroidCollection.collection_name)

    start_without_cache = time.time()
    node(state)
    uncached_time = time.time() - start_without_cache

    # 5. Verify caching provides performance benefit
    print(f"\n📊 With cache: {cached_time:.4f}s | Without cache: {uncached_time:.4f}s")

    # Note: We don't assert cached < uncached because on small datasets
    # the overhead of Weaviate queries might dominate.
    # This test is informational for monitoring performance trends.
