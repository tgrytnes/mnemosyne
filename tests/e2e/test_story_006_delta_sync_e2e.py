"""
E2E test for Story 006: delta sync node across the full pipeline.
Uses real services: Weaviate, Ollama, Postgres (and Neo4j if available).
"""

from __future__ import annotations

import shutil

import pytest
from mnemosyne.config.provider_config import ProviderConfig

from mnemosyne.aletheia.ingestion_state import IngestionStateTracker
from mnemosyne.aletheia.obsidian_ingestor import ObsidianIngestor
from mnemosyne.alexandria.cluster_profile_repository import ClusterProfileRepository
from mnemosyne.alexandria.cluster_sync_state_repository import ClusterSyncStateRepository
from mnemosyne.alexandria.weaviate_schema import ClusterCentroidCollection, WeaviateSchemaManager
from mnemosyne.argus.delta_sync import DeltaSyncConfig, DeltaSyncNode
from mnemosyne.argus.graph_taxonomy import GraphTaxonomyConfig
from mnemosyne.argus.graph_taxonomy_pipeline import GraphTaxonomyPipeline
from mnemosyne.cli.cluster import ClusterManager
from mnemosyne.iris.semantic_router import QueryCacheStore
from mnemosyne.providers.factory import create_embedding_provider, create_llm_provider


@pytest.mark.e2e
@pytest.mark.weaviate
@pytest.mark.postgres
def test_delta_sync_end_to_end(
    weaviate_client,
    clean_weaviate_collection,
    postgres_connection,
    neo4j_driver,
    test_config,
    fake_vault_path,
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

    vault_path = tmp_path / "vault"
    shutil.copytree(fake_vault_path, vault_path)

    state_tracker = IngestionStateTracker(str(vault_path / "state.db"))
    ingestor = ObsidianIngestor(
        vault_path=str(vault_path),
        weaviate_client=weaviate_client,
        llm_provider=llm_provider,
        embedding_provider=embedding_provider,
        state_tracker=state_tracker,
    )
    stats = ingestor.ingest_vault()
    assert stats["files_processed"] > 0

    schema = WeaviateSchemaManager(weaviate_client)
    schema.ensure_collection_exists(ClusterCentroidCollection.collection_name)

    manager = ClusterManager(weaviate_client)
    vectors, uuids = manager.fetch_all_vectors()
    labels, centroids = manager.run_kmeans_clustering(vectors, n_clusters=2)
    manager.update_chunk_cluster_ids(uuids, labels)
    manager.update_centroids(centroids, labels)

    profile_repo = ClusterProfileRepository(postgres_connection)
    profile_repo.ensure_table()
    sync_repo = ClusterSyncStateRepository(postgres_connection)
    sync_repo.ensure_table()

    cache_store = QueryCacheStore(str(tmp_path / "query_cache.db"))
    cache_store.upsert(
        "project backlog",
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
    assert stats.changed_clusters > 0
    assert sync_repo.list_all()

    new_note = vault_path / "new_project.md"
    new_note.write_text("# New Project\nPlan a solar installation and budget estimates.\n")
    stats = ingestor.ingest_vault()
    assert stats["files_processed"] == 1

    vectors, uuids = manager.fetch_all_vectors()
    labels, centroids = manager.run_kmeans_clustering(vectors, n_clusters=2)
    manager.update_chunk_cluster_ids(uuids, labels)
    manager.update_centroids(centroids, labels)

    stats = node.run_once()
    assert stats.changed_clusters > 0
