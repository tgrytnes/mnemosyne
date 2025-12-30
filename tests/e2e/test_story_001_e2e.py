# tests/e2e/test_story_001_e2e.py

import os

import pytest
from langgraph.graph import END, StateGraph

from mnemosyne.alexandria.weaviate_schema import ClusterCentroidCollection, TheMuses
from mnemosyne.argus.nodes.cluster_representatives import (
    ClusterRepresentativesState,
    GetClusterRepresentatives,
)
from mnemosyne.cli.cluster import run_clustering
from mnemosyne.cli.ingest import ingest_once

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


def test_story_001_full_pipeline(weaviate_client, fake_vault_path, tmp_path):
    """
    Tests the full E2E pipeline for Story 001:
    1. Ingest a vault.
    2. Cluster the chunks.
    3. Use a LangGraph to get representative chunks.
    """
    os.environ["OBSIDIAN_VAULT_PATH"] = str(fake_vault_path)
    state_db_path = tmp_path / "ingestion_state_story_001.db"
    original_state_db = os.environ.get("INGESTION_STATE_DB")
    os.environ["INGESTION_STATE_DB"] = str(state_db_path)

    try:
        ingest_once()
    finally:
        if original_state_db is None:
            os.environ.pop("INGESTION_STATE_DB", None)
        else:
            os.environ["INGESTION_STATE_DB"] = original_state_db

    muses_collection = weaviate_client.collections.get(TheMuses.collection_name)
    total_chunks = muses_collection.aggregate.over_all(total_count=True).total_count
    assert total_chunks > 0

    n_clusters = 2
    run_clustering(n_clusters=n_clusters)

    centroid_collection = weaviate_client.collections.get(ClusterCentroidCollection.collection_name)
    total_centroids = centroid_collection.aggregate.over_all(total_count=True).total_count
    assert total_centroids == n_clusters

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


def test_story_001_cluster_quality_with_fake_vault(weaviate_client, fake_vault_path, tmp_path):
    """
    Validate clustering quality on the realistic fake vault and access reps via LangGraph.
    """
    os.environ["OBSIDIAN_VAULT_PATH"] = str(fake_vault_path)
    state_db_path = tmp_path / "ingestion_state_story_001_quality.db"
    original_state_db = os.environ.get("INGESTION_STATE_DB")
    os.environ["INGESTION_STATE_DB"] = str(state_db_path)

    try:
        ingest_once()
    finally:
        if original_state_db is None:
            os.environ.pop("INGESTION_STATE_DB", None)
        else:
            os.environ["INGESTION_STATE_DB"] = original_state_db

    n_clusters = 3
    run_clustering(n_clusters=n_clusters)

    workflow = StateGraph(ClusterRepresentativesState)
    get_representatives_node = GetClusterRepresentatives(client=weaviate_client)
    workflow.add_node("get_representatives", get_representatives_node)
    workflow.set_entry_point("get_representatives")
    workflow.add_edge("get_representatives", END)
    app = workflow.compile()

    def classify_rep(rep) -> str:
        source = rep.source_file.lower()
        if "projects" in source:
            return "projects"
        if "journal" in source:
            return "journal"
        if "knowledge" in source:
            return "knowledge"

        text = rep.text.lower()
        keyword_sets = {
            "projects": ["project", "milestone", "plan", "scope", "risk"],
            "journal": ["meeting", "standup", "experiment", "agenda", "decisions"],
            "knowledge": ["embedding", "weaviate", "chunking", "retrieval", "router", "vector"],
        }
        scores = {
            category: sum(1 for keyword in keywords if keyword in text)
            for category, keywords in keyword_sets.items()
        }
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else "other"

    dominant_domains = []
    for cluster_id in range(n_clusters):
        final_state = None
        for s in app.stream({"cluster_id": cluster_id}):
            final_state = s

        final_state_data = final_state[list(final_state.keys())[0]]
        assert "error" not in final_state_data or final_state_data["error"] is None

        reps = final_state_data.get("representative_chunks", [])
        assert reps, f"Cluster {cluster_id} should have representatives"

        domain_counts = {}
        for rep in reps:
            domain = classify_rep(rep)
            domain_counts[domain] = domain_counts.get(domain, 0) + 1

        dominant_domain, dominant_count = max(domain_counts.items(), key=lambda item: item[1])
        assert dominant_domain != "other", f"Cluster {cluster_id} reps look incoherent"
        assert dominant_count >= 2, f"Cluster {cluster_id} reps should share a domain"
        dominant_domains.append(dominant_domain)

    assert len(set(dominant_domains)) >= 2, (
        "Expected at least two distinct domains across clusters " f"(got {set(dominant_domains)})"
    )
