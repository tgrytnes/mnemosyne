"""
Integration test for Story 006: delta sync node.
Uses real services: Weaviate, Ollama, Postgres (and Neo4j if available).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from mnemosyne.aletheia.ingestion_state import IngestionStateTracker
from mnemosyne.aletheia.obsidian_ingestor import ObsidianIngestor
from mnemosyne.alexandria.cluster_profile_repository import ClusterProfileRepository
from mnemosyne.alexandria.cluster_sync_state_repository import ClusterSyncStateRepository
from mnemosyne.alexandria.weaviate_schema import ClusterCentroidCollection, WeaviateSchemaManager
from mnemosyne.argus.delta_sync import DeltaSyncConfig, DeltaSyncNode
from mnemosyne.argus.graph_taxonomy import GraphTaxonomyConfig
from mnemosyne.argus.graph_taxonomy_pipeline import GraphTaxonomyPipeline
from mnemosyne.cli.cluster import ClusterManager
from mnemosyne.config.providers import ProviderConfig
from mnemosyne.iris.semantic_router import QueryCacheStore
from mnemosyne.providers.factory import create_embedding_provider, create_llm_provider


@pytest.mark.integration
@pytest.mark.weaviate
@pytest.mark.postgres
def test_delta_sync_updates_profiles_and_state(
    weaviate_client,
    clean_weaviate_collection,
    postgres_connection,
    neo4j_driver,
    test_config,
    tmp_path,
):
    config = ProviderConfig(
        llm_provider="ollama",
        llm_model="qwen3:0.6b",
        embedding_provider="ollama",
        embedding_model="nomic-embed-text:latest",
        ollama_base_url=test_config["ollama_url"],
    )
    llm_provider = create_llm_provider(config)
    embedding_provider = create_embedding_provider(config)

    with tempfile.TemporaryDirectory() as tmp_dir:
        vault_path = Path(tmp_dir) / "vault"
        vault_path.mkdir()

        (vault_path / "project.md").write_text(
            "# Home Renovation\nPlan to paint the house and replace flooring.\n"
        )
        (vault_path / "recipe.md").write_text("# Pasta\nIngredients for dinner.\n")

        state_tracker = IngestionStateTracker(str(vault_path / "state.db"))
        ingestor = ObsidianIngestor(
            vault_path=str(vault_path),
            weaviate_client=weaviate_client,
            llm_provider=llm_provider,
            embedding_provider=embedding_provider,
            state_tracker=state_tracker,
        )
        stats = ingestor.ingest_vault()
        assert stats["files_processed"] == 2

        schema = WeaviateSchemaManager(weaviate_client)
        schema.ensure_collection_exists(ClusterCentroidCollection.collection_name)

        manager = ClusterManager(weaviate_client)
        vectors, uuids = manager.fetch_all_vectors()
        labels, centroids = manager.run_kmeans_clustering(vectors, n_clusters=1)
        manager.update_chunk_cluster_ids(uuids, labels)
        manager.update_centroids(centroids, labels)

        profile_repo = ClusterProfileRepository(postgres_connection)
        profile_repo.ensure_table()
        sync_repo = ClusterSyncStateRepository(postgres_connection)
        sync_repo.ensure_table()

        cache_path = tmp_path / "query_cache.db"
        cache_store = QueryCacheStore(str(cache_path))
        cache_store.upsert(
            "project idea",
            [0.1, 0.2],
            {"cluster_id": "0"},
            source="weaviate",
        )

        graph_pipeline = GraphTaxonomyPipeline(
            weaviate_client=weaviate_client,
            postgres_connection=postgres_connection,
            neo4j_driver=neo4j_driver,
            config=GraphTaxonomyConfig(),
        )

        node = DeltaSyncNode(
            weaviate_client=weaviate_client,
            postgres_connection=postgres_connection,
            llm_provider=llm_provider,
            graph_pipeline=graph_pipeline,
            cache_store=cache_store,
            config=DeltaSyncConfig(max_retries=0, retry_backoff_seconds=0.0),
        )

        stats = node.run_once()
        assert stats.changed_clusters >= 1
        assert profile_repo.get("0") is not None
        assert sync_repo.get("0") is not None
        assert len(cache_store.get_all()) == 0

        (vault_path / "project_addendum.md").write_text(
            "# Home Renovation\nAdd a new bathroom and update fixtures.\n"
        )
        stats = ingestor.ingest_vault()
        assert stats["files_processed"] == 1

        vectors, uuids = manager.fetch_all_vectors()
        labels, centroids = manager.run_kmeans_clustering(vectors, n_clusters=1)
        manager.update_chunk_cluster_ids(uuids, labels)
        manager.update_centroids(centroids, labels)

        stats = node.run_once()
        state = sync_repo.get("0")
        assert state is not None
        assert state.vector_count_at_sync >= 3
