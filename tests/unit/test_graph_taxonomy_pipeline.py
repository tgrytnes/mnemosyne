"""
Unit tests for GraphTaxonomyPipeline source filtering.
"""

from datetime import datetime

from mnemosyne.alexandria.the_gates import ClusterProfile
from mnemosyne.argus.graph_taxonomy import GraphTaxonomyConfig
from mnemosyne.argus.graph_taxonomy_pipeline import GraphTaxonomyPipeline


def test_graph_taxonomy_pipeline_uses_profile_source(mocker):
    weaviate_client = mocker.MagicMock()
    weaviate_client.collections.exists.return_value = True

    centroid_obj = mocker.MagicMock()
    centroid_obj.properties = {"clusterId": 1}
    centroid_obj.vector = {"default": [0.1, 0.2]}
    weaviate_client.collections.get.return_value.query.fetch_objects.return_value.objects = [
        centroid_obj
    ]

    profile = ClusterProfile(
        cluster_id="1",
        theme_summary="Lethe profile",
        key_entities=["alpha"],
        dominant_topics=["beta"],
        tags=["lethe"],
        confidence_score=0.7,
        representative_note_ids=["chunk-1"],
        created_at=datetime(2025, 1, 1),
        metadata={"source": "lethe"},
    )

    profile_repo = mocker.MagicMock()
    profile_repo.get.return_value = profile
    mocker.patch(
        "mnemosyne.argus.graph_taxonomy_pipeline.ClusterProfileRepository",
        return_value=profile_repo,
    )

    graph_repo = mocker.MagicMock()
    mocker.patch(
        "mnemosyne.argus.graph_taxonomy_pipeline.Neo4jGraphRepository",
        return_value=graph_repo,
    )

    pipeline = GraphTaxonomyPipeline(
        weaviate_client=weaviate_client,
        postgres_connection=mocker.MagicMock(),
        neo4j_driver=mocker.MagicMock(),
        config=GraphTaxonomyConfig(),
        profile_source="lethe",
    )

    result = pipeline.build_graph()

    profile_repo.ensure_table.assert_called_once()
    profile_repo.get.assert_called_with("1", source="lethe")
    graph_repo.upsert_clusters.assert_called_once()
    assert result["nodes"]


def test_graph_taxonomy_pipeline_bootstraps_when_profiles_missing(mocker):
    weaviate_client = mocker.MagicMock()
    weaviate_client.collections.exists.return_value = True

    centroid_obj = mocker.MagicMock()
    centroid_obj.properties = {"clusterId": 1}
    centroid_obj.vector = {"default": [0.1, 0.2]}
    weaviate_client.collections.get.return_value.query.fetch_objects.return_value.objects = [
        centroid_obj
    ]

    profile_repo = mocker.MagicMock()
    profile_repo.get.return_value = None
    mocker.patch(
        "mnemosyne.argus.graph_taxonomy_pipeline.ClusterProfileRepository",
        return_value=profile_repo,
    )

    graph_repo = mocker.MagicMock()
    mocker.patch(
        "mnemosyne.argus.graph_taxonomy_pipeline.Neo4jGraphRepository",
        return_value=graph_repo,
    )

    bootstrapper = mocker.MagicMock()

    pipeline = GraphTaxonomyPipeline(
        weaviate_client=weaviate_client,
        postgres_connection=mocker.MagicMock(),
        neo4j_driver=mocker.MagicMock(),
        config=GraphTaxonomyConfig(),
        profile_source="lethe",
        profile_bootstrapper=bootstrapper,
    )

    pipeline.build_graph()

    profile_repo.ensure_table.assert_called_once()
    bootstrapper.ensure_profiles.assert_called_once_with(["1"])


def test_graph_taxonomy_pipeline_skips_bootstrap_when_no_clusters(mocker):
    weaviate_client = mocker.MagicMock()
    weaviate_client.collections.exists.return_value = True
    weaviate_client.collections.get.return_value.query.fetch_objects.return_value.objects = []

    profile_repo = mocker.MagicMock()
    mocker.patch(
        "mnemosyne.argus.graph_taxonomy_pipeline.ClusterProfileRepository",
        return_value=profile_repo,
    )

    graph_repo = mocker.MagicMock()
    mocker.patch(
        "mnemosyne.argus.graph_taxonomy_pipeline.Neo4jGraphRepository",
        return_value=graph_repo,
    )

    bootstrapper = mocker.MagicMock()

    pipeline = GraphTaxonomyPipeline(
        weaviate_client=weaviate_client,
        postgres_connection=mocker.MagicMock(),
        neo4j_driver=mocker.MagicMock(),
        config=GraphTaxonomyConfig(),
        profile_bootstrapper=bootstrapper,
    )

    result = pipeline.build_graph()

    bootstrapper.ensure_profiles.assert_not_called()
    assert result["nodes"] == []
