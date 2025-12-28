# tests/e2e/test_story_001_e2e.py

import os
import pytest
from langgraph.graph import StateGraph, END

from mnemosyne.cli.ingest import ingest_once
from mnemosyne.cli.cluster import run_clustering
from mnemosyne.argus.nodes.cluster_representatives import (
    GetClusterRepresentatives,
    ClusterRepresentativesState,
)
from mnemosyne.alexandria.weaviate_schema import TheMuses, ClusterCentroidCollection

# Mark all tests in this file as E2E tests
pytestmark = [pytest.mark.e2e, pytest.mark.weaviate]


@pytest.fixture(scope="module")
def weaviate_collections(weaviate_client):
    """Ensure Weaviate collections are created and cleaned up for the module."""
    yield
    if weaviate_client.collections.exists(TheMuses.collection_name):
        weaviate_client.collections.delete(TheMuses.collection_name)
    if weaviate_client.collections.exists(ClusterCentroidCollection.collection_name):
        weaviate_client.collections.delete(ClusterCentroidCollection.collection_name)


@pytest.fixture(autouse=True)
def clean_collections_before_test(weaviate_client, weaviate_collections):
    """Clean data from collections before each test."""
    if weaviate_client.collections.exists(TheMuses.collection_name):
        weaviate_client.collections.delete(TheMuses.collection_name)
    if weaviate_client.collections.exists(ClusterCentroidCollection.collection_name):
        weaviate_client.collections.delete(ClusterCentroidCollection.collection_name)


def test_story_001_full_pipeline(weaviate_client, temp_vault):
    """
    Tests the full E2E pipeline for Story 001:
    1. Ingest a vault.
    2. Cluster the chunks.
    3. Use a LangGraph to get representative chunks.
    """
    os.environ["OBSIDIAN_VAULT_PATH"] = str(temp_vault)

    ingest_once()

    muses_collection = weaviate_client.collections.get(TheMuses.collection_name)
    assert muses_collection.aggregate.total_count()["total_count"] > 0

    n_clusters = 2
    run_clustering(n_clusters=n_clusters)

    centroid_collection = weaviate_client.collections.get(ClusterCentroidCollection.collection_name)
    assert centroid_collection.aggregate.total_count()["total_count"] == n_clusters

    workflow = StateGraph(ClusterRepresentativesState)
    get_representatives_node = GetClusterRepresentatives(client=weaviate_client)
    workflow.add_node("get_representatives", get_representatives_node)
    workflow.set_entry_point("get_representatives")
    workflow.add_edge("get_representatives", END)
    app = workflow.compile()

    first_centroid = centroid_collection.query.fetch_objects(limit=1).objects[0]
    test_cluster_id = first_centroid.properties["clusterId"]

    inputs = {"cluster_id": test_cluster_id}
    final_state = None
    for s in app.stream(inputs):
        final_state = s

    final_state_data = final_state[list(final_state.keys())[0]]

    assert "error" not in final_state_data or final_state_data["error"] is None

    representative_chunks = final_state_data.get("representative_chunks")
    assert representative_chunks is not None
    assert isinstance(representative_chunks, list)
    assert len(representative_chunks) > 0
    assert len(representative_chunks) <= 5
