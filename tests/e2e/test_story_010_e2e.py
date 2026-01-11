"""
E2E tests for Story 010 autonomous pattern detection (Scout).
"""

import json
import os
from pathlib import Path

import pytest

from mnemosyne.aletheia.ingestion_state import IngestionStateTracker
from mnemosyne.aletheia.obsidian_ingestor import ObsidianIngestor
from mnemosyne.argus.scout.discovery_store import DiscoveryStore, RunMetadata
from mnemosyne.argus.scout.radar import (
    ClusterRepresentation,
    ConceptPrototype,
    LatentRadar,
)
from mnemosyne.argus.scout.scout_runner import ScoutConfig, ScoutRunner
from mnemosyne.cli.cluster import run_clustering
from mnemosyne.config.providers import ProviderConfig
from mnemosyne.providers.factory import create_embedding_provider, create_llm_provider


@pytest.mark.e2e
@pytest.mark.weaviate
def test_story_010_discovers_and_stores_projectness(
    weaviate_client, test_config, clean_weaviate_collection
):
    provider_config = ProviderConfig(
        embedding_provider="ollama", ollama_base_url=test_config["ollama_url"]
    )
    embedding_provider = create_embedding_provider(provider_config)

    positives = [
        "Renovate the house: budget, timeline, contractors, materials.",
        "Plan education goals: coursework, tuition, schedule, deadlines.",
        "Design a training program with weekly sessions and milestones.",
        "Create a home lab docker project: services, deploy, test.",
    ]
    negatives = [
        "Historical summary and background notes.",
        "Glossary of database schema definitions.",
        "Recipe notes and cooking techniques.",
    ]

    clusters = [
        ClusterRepresentation(
            cluster_id="project_renovation",
            text="Renovate the kitchen with a timeline, budget, and materials list.",
            embedding=embedding_provider.embed(
                model="",
                text="Renovate the kitchen with a timeline, budget, and materials list.",
            ),
        ),
        ClusterRepresentation(
            cluster_id="project_training",
            text="Draft a 12-week training program with milestones and weekly goals.",
            embedding=embedding_provider.embed(
                model="",
                text="Draft a 12-week training program with milestones and weekly goals.",
            ),
        ),
        ClusterRepresentation(
            cluster_id="non_project_history",
            text="Notes on Roman empire politics and historical events.",
            embedding=embedding_provider.embed(
                model="",
                text="Notes on Roman empire politics and historical events.",
            ),
        ),
    ]

    radar = LatentRadar(lambda text: embedding_provider.embed(model="", text=text))
    base_concept = ConceptPrototype(
        key="project_private",
        positive_texts=positives,
        negative_texts=negatives,
        threshold=0.0,
    )
    pos_vecs, neg_vecs = radar.embed_prototypes(base_concept)
    scores = {
        cluster.cluster_id: radar.score(cluster.embedding, pos_vecs, neg_vecs)[0]
        for cluster in clusters
    }
    threshold = max(scores["non_project_history"], 0.0) + 0.05

    concept = ConceptPrototype(
        key="project_private",
        positive_texts=positives,
        negative_texts=negatives,
        threshold=threshold,
    )
    detections = radar.detect(concept, clusters, pattern_type="project_candidate")

    store = DiscoveryStore(weaviate_client, dedup_similarity_threshold=0.8)
    run_metadata = RunMetadata(
        run_id="run-010",
        clusters_analyzed=len(clusters),
        errors=[],
        dry_run=False,
    )
    result = store.store_detections(detections, run_metadata)
    assert len(result.stored_ids) == len(detections)

    collection = weaviate_client.collections.get("Discoveries")
    response = collection.query.fetch_objects(limit=10)
    assert len(response.objects) == len(detections)

    sample = response.objects[0].properties
    assert sample["patternType"] == "project_candidate"
    assert sample["clusterIds"]
    assert sample["confidenceScore"] > 0
    assert sample["runId"] == "run-010"
    assert sample["dryRun"] is False
    signals = json.loads(sample["signals"])
    assert signals["concept_key"] == "project_private"

    deduped = store.store_detections(detections, run_metadata)
    assert deduped.skipped_duplicates == len(detections)
    after_count = collection.aggregate.over_all(total_count=True).total_count
    assert after_count == len(detections)

    dry_run = RunMetadata(
        run_id="run-010-dry",
        clusters_analyzed=len(clusters),
        errors=[],
        dry_run=True,
    )
    dry_result = store.store_detections(detections, dry_run)
    assert dry_result.stored_ids == []
    final_count = collection.aggregate.over_all(total_count=True).total_count
    assert final_count == len(detections)


@pytest.mark.e2e
@pytest.mark.weaviate
def test_story_010_full_pipeline_detects_new_project_topic(
    tmp_path, weaviate_client, clean_weaviate_collection, test_config
):
    provider_config = ProviderConfig(
        embedding_provider="ollama",
        llm_provider="ollama",
        ollama_base_url=test_config["ollama_url"],
    )
    embedding_provider = create_embedding_provider(provider_config)
    llm_provider = create_llm_provider(provider_config)

    vault = tmp_path / "vault"
    vault.mkdir()
    _write_note(vault / "history.md", "Notes on Roman history and governance.")
    _write_note(vault / "recipes.md", "Pasta recipe with tomatoes and basil.")

    state_tracker = IngestionStateTracker(str(tmp_path / "ingestion_state.db"))
    ingestor = ObsidianIngestor(
        vault_path=str(vault),
        weaviate_client=weaviate_client,
        embedding_provider=embedding_provider,
        llm_provider=llm_provider,
        state_tracker=state_tracker,
        chunking_strategy="recursive",
        chunk_size=400,
        chunk_overlap=100,
    )
    stats = ingestor.ingest_vault()
    assert stats["total_chunks"] > 0

    _run_clustering_with_env(test_config)

    project_concepts = [
        ConceptPrototype(
            key="project_private",
            positive_texts=[
                "Renovate the house: budget, timeline, contractors, materials.",
                "Plan education goals: coursework, tuition, schedule, deadlines.",
                "Design a training program with weekly sessions and milestones.",
                "Create a home lab docker project: services, deploy, test.",
            ],
            negative_texts=[
                "Historical summary and background notes.",
                "Glossary of database schema definitions.",
                "Recipe notes and cooking techniques.",
            ],
            threshold=0.15,
        )
    ]
    runner = ScoutRunner(
        weaviate_client,
        embedder=lambda text: embedding_provider.embed(model="", text=text),
        config=ScoutConfig(project_concepts=project_concepts),
    )

    initial_summary = runner.run(run_id="story-010-initial", dry_run=False)
    assert initial_summary.clusters_analyzed > 0

    collection = weaviate_client.collections.get("Discoveries")
    initial_count = collection.aggregate.over_all(total_count=True).total_count

    _write_note(
        vault / "renovation.md",
        "Renovate the house with a timeline, budget, and contractor list.",
    )
    ingestor.ingest_vault()
    _run_clustering_with_env(test_config)

    followup_summary = runner.run(run_id="story-010-followup", dry_run=False)
    assert followup_summary.detections_by_type.get("project_candidate", 0) >= 1

    final_count = collection.aggregate.over_all(total_count=True).total_count
    assert final_count >= initial_count + 1

    state_tracker.close()


def _write_note(path: Path, content: str) -> None:
    path.write_text(content)


def _run_clustering_with_env(test_config) -> None:
    env = {
        "WEAVIATE_HTTP_HOST": test_config["weaviate_http_host"],
        "WEAVIATE_HTTP_PORT": str(test_config["weaviate_http_port"]),
        "WEAVIATE_GRPC_PORT": str(test_config["weaviate_grpc_port"]),
    }
    original = {key: os.environ.get(key) for key in env}
    os.environ.update(env)
    try:
        run_clustering(n_clusters=2)
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
