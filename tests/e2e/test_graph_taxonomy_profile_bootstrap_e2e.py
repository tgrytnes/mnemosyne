"""E2E tests for graph taxonomy profile bootstrap."""

from datetime import datetime

import pytest
from weaviate.classes.query import Filter

from mnemosyne.alexandria.cluster_profile_repository import ClusterProfileRepository
from mnemosyne.alexandria.weaviate_schema import (
    ClusterCentroidCollection,
    TheMuses,
    WeaviateSchemaManager,
)
from mnemosyne.argus.cluster_profile_bootstrap import ClusterProfileBootstrapper


@pytest.mark.e2e
@pytest.mark.weaviate
@pytest.mark.postgres
@pytest.mark.ollama
def test_bootstrap_creates_profiles_for_empty_source(
    weaviate_client,
    postgres_connection,
    ollama_client,
):
    schema = WeaviateSchemaManager(weaviate_client)
    schema.ensure_collection_exists(TheMuses.collection_name)
    schema.ensure_collection_exists(ClusterCentroidCollection.collection_name)

    muses = weaviate_client.collections.get(TheMuses.collection_name)
    centroids = weaviate_client.collections.get(ClusterCentroidCollection.collection_name)
    cluster_id = 91001

    base_vector = [0.0] * 1024
    base_vector[0] = 0.1
    base_vector[1] = 0.2
    vectors = [
        base_vector,
        [0.11, 0.19, 0.31, 0.39] + [0.0] * 1020,
    ]
    for idx, vector in enumerate(vectors):
        muses.data.insert(
            properties={
                "text": f"Bootstrap test note {idx}",
                "sourceFile": f"note{idx}.md",
                "chunkIndex": idx,
                "headingPath": "Bootstrap",
                "clusterId": cluster_id,
            },
            vector=vector,
        )

    centroids.data.insert(
        properties={
            "clusterId": cluster_id,
            "clusterSize": 2,
            "lastUpdated": datetime.utcnow().isoformat() + "Z",
        },
        vector=vectors[0],
    )

    repo = ClusterProfileRepository(postgres_connection)
    repo.ensure_table()
    cursor = postgres_connection.cursor()
    cursor.execute(
        "DELETE FROM cluster_profiles WHERE cluster_id = %s AND source = 'muses'",
        (str(cluster_id),),
    )
    postgres_connection.commit()

    bootstrapper = ClusterProfileBootstrapper(
        weaviate_client=weaviate_client,
        postgres_connection=postgres_connection,
        ollama_client=ollama_client,
        profile_source="muses",
        centroid_collection_name=ClusterCentroidCollection.collection_name,
        chunk_collection_name=TheMuses.collection_name,
        text_property="text",
        source_property="sourceFile",
        heading_property="headingPath",
        chunk_index_property="chunkIndex",
    )

    try:
        bootstrapper.ensure_profiles([str(cluster_id)])

        assert repo.get(str(cluster_id), source="muses") is not None
    finally:
        muses.data.delete_many(where=Filter.by_property("clusterId").equal(cluster_id))
        centroids.data.delete_many(where=Filter.by_property("clusterId").equal(cluster_id))
        cursor.execute(
            "DELETE FROM cluster_profiles WHERE cluster_id = %s AND source = 'muses'",
            (str(cluster_id),),
        )
        postgres_connection.commit()
