"""
E2E tests for Story 015 Monitor Agent (Discovery -> Proposal -> Escalation).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from weaviate.classes.query import Filter

from mnemosyne.aletheia.ingestion_state import IngestionStateTracker
from mnemosyne.aletheia.obsidian_ingestor import ObsidianIngestor
from mnemosyne.alexandria.weaviate_schema import Discoveries, TheMuses
from mnemosyne.argus.scout.monitor_agent import (
    MonitorAgent,
    MonitorConfig,
    MonitorStateStore,
    PostgresProjectRepository,
    ProposalQueue,
    WeaviateDiscoveryReader,
)
from mnemosyne.argus.scout.radar import ConceptPrototype
from mnemosyne.argus.scout.scout_runner import ScoutConfig, ScoutRunner
from mnemosyne.cli.cluster import run_clustering


class _InMemoryOutbox:
    def __init__(self):
        self.messages: list[dict[str, str]] = []

    def enqueue(self, message_type: str, payload: dict, message_id: str) -> None:
        self.messages.append(
            {
                "message_type": message_type,
                "message_id": message_id,
            }
        )


@pytest.mark.e2e
@pytest.mark.weaviate
def test_story_015_escalates_rejected_discovery(
    tmp_path,
    fake_vault_path,
    weaviate_client,
    ollama_client,
    postgres_connection,
    ananke_test_db,
    test_config,
):
    expected_project_files = {
        "project_house_renovation.md",
        "project_training_program.md",
        "project_docker_lab.md",
        "project_education_plan.md",
    }
    project_file_pool = expected_project_files

    if weaviate_client.collections.exists(Discoveries.collection_name):
        weaviate_client.collections.delete(Discoveries.collection_name)

    monitor_vault_path = fake_vault_path / "monitor_projects"
    if not monitor_vault_path.exists():
        pytest.fail("Monitor fake vault notes are missing")

    if weaviate_client.collections.exists(TheMuses.collection_name):
        weaviate_client.collections.delete(TheMuses.collection_name)

    state_tracker = IngestionStateTracker(str(tmp_path / "ingestion_state.db"))
    ingestor = ObsidianIngestor(
        vault_path=str(monitor_vault_path),
        weaviate_client=weaviate_client,
        ollama_client=ollama_client,
        state_tracker=state_tracker,
        chunking_strategy="recursive",
        chunk_size=400,
        chunk_overlap=100,
    )
    stats = ingestor.ingest_vault()
    assert stats["total_chunks"] > 0

    n_clusters = _count_markdown_files(monitor_vault_path)
    _run_clustering_with_env(test_config, n_clusters=n_clusters)

    project_concepts = [
        ConceptPrototype(
            key="private_projects",
            positive_texts=[
                "Renovate the house with a budget, timeline, and contractor plan.",
                "Design a training program with weekly sessions and milestones.",
                "Create a home lab docker project with services and deployment steps.",
                "Plan education goals with coursework, tuition, and deadlines.",
            ],
            negative_texts=[
                "Meeting notes with agenda and decisions.",
                "Historical summary and background notes.",
                "Glossary of database schema definitions.",
            ],
            threshold=0.0,
        )
    ]
    runner = ScoutRunner(
        weaviate_client,
        embedder=lambda text: _embed(ollama_client, text),
        config=ScoutConfig(project_concepts=project_concepts),
    )

    summary = runner.run(run_id="story-015-run", dry_run=False)
    assert summary.detections_by_type.get("project_candidate", 0) >= 1

    proposal_queue = ProposalQueue(tmp_path / "proposals.db")
    state_store = MonitorStateStore(tmp_path / "monitor_state.db")
    outbox = _InMemoryOutbox()

    reader = WeaviateDiscoveryReader(weaviate_client)
    projects = PostgresProjectRepository(postgres_connection)
    agent = MonitorAgent(
        discovery_reader=reader,
        project_repository=projects,
        proposal_queue=proposal_queue,
        state_store=state_store,
        outbox=outbox,
        config=MonitorConfig(confidence_threshold=0.0),
    )

    agent.run()
    proposals = proposal_queue.list_by_status("pending")
    assert proposals

    muses = weaviate_client.collections.get(TheMuses.collection_name)
    found_project_sources = set()
    for proposal in proposals:
        cluster_ids = json.loads(proposal["cluster_ids"])
        for cluster_id in cluster_ids:
            sources = _cluster_sources(muses, cluster_id)
            found_project_sources.update(sources & project_file_pool)

    assert expected_project_files.issubset(found_project_sources)

    discovery_id = proposals[0]["discovery_id"]
    proposal_queue.update_status(discovery_id, "rejected")
    agent.run()

    assert outbox.messages
    message = outbox.messages[0]
    assert message["message_type"] == "proposal_escalation"
    assert message["message_id"] == f"proposal_escalation:{discovery_id}"


def _embed(ollama_client, text: str) -> list[float]:
    response = ollama_client.embeddings(model="qwen3-embedding:0.6b", prompt=text)
    return response["embedding"]


def _cluster_sources(collection, cluster_id: str) -> set[str]:
    response = collection.query.fetch_objects(
        filters=Filter.by_property("clusterId").equal(int(cluster_id)),
        limit=1000,
    )
    sources = set()
    for obj in response.objects:
        source_file = obj.properties.get("sourceFile")
        if source_file:
            sources.add(Path(str(source_file)).name)
    return sources


def _run_clustering_with_env(test_config, n_clusters: int) -> None:
    env = {
        "WEAVIATE_HTTP_HOST": test_config["weaviate_http_host"],
        "WEAVIATE_HTTP_PORT": str(test_config["weaviate_http_port"]),
        "WEAVIATE_GRPC_PORT": str(test_config["weaviate_grpc_port"]),
    }
    original = {key: os.environ.get(key) for key in env}
    os.environ.update(env)
    try:
        run_clustering(n_clusters=n_clusters)
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _count_markdown_files(path: Path) -> int:
    return len(list(path.glob("*.md")))
