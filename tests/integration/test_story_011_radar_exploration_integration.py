"""
Integration test for Story 011: radar exploration writes weak links with identity and checkpointing.
"""

from pathlib import Path

import pytest

from mnemosyne.argus.scout.radar import ClusterRepresentation


def _vec(ollama_client, text: str) -> list[float]:
    response = ollama_client.embeddings(model="qwen3-embedding:0.6b", prompt=text)
    return response["embedding"]


@pytest.mark.integration
@pytest.mark.weaviate
def test_radar_explorer_stores_weak_links_with_identity(
    tmp_path: Path, weaviate_client, ollama_client, clean_weaviate_collection
):
    from mnemosyne.argus.scout.radar_explorer import ExplorationSummary, RadarExplorer

    clusters = [
        ClusterRepresentation(
            cluster_id="cluster-a",
            text="Notes about renovating a house with milestones and budget.",
            embedding=_vec(ollama_client, "Renovate house milestones budget timeline."),
        ),
        ClusterRepresentation(
            cluster_id="cluster-b",
            text="Notes about home network project and docker lab.",
            embedding=_vec(ollama_client, "Home network project docker lab servers."),
        ),
        ClusterRepresentation(
            cluster_id="cluster-c",
            text="Garden journal and plant watering schedule (non-project).",
            embedding=_vec(ollama_client, "Gardening schedule and plant care diary."),
        ),
    ]

    checkpoint_path = tmp_path / "exploration_state.json"
    explorer = RadarExplorer(
        weaviate_client=weaviate_client,
        embedder=lambda text: _vec(ollama_client, text),
        strategy="curiosity",
        budget_seconds=30,
        checkpoint_path=checkpoint_path,
        discovery_job_key="latent-radar-job",
        max_pairs_per_cluster=2,
    )

    summary: ExplorationSummary = explorer.run(clusters)
    assert summary.pairs_explored > 0
    assert summary.new_discoveries >= 1
    assert summary.strategy == "curiosity"
    assert summary.run_metadata["discovery_job_key"] == "latent-radar-job"

    collection = weaviate_client.collections.get("Discoveries")
    response = collection.query.fetch_objects(limit=5)
    assert response.objects, "No weak links persisted to Discoveries"

    weak_link_props = response.objects[0].properties
    assert weak_link_props["discoveryJobKey"] == "latent-radar-job"
    assert weak_link_props["candidateKey"]
    assert weak_link_props["discoveryId"]
    assert weak_link_props["confidenceScore"] > 0
    assert weak_link_props["patternType"] == "weak_link"
    assert weak_link_props["explorerStrategy"] in ("curiosity", "breadth_first")

    # Run again to ensure checkpointing skips already explored pairs and avoids duplicates
    second_summary = explorer.run(clusters)
    assert second_summary.pairs_explored <= summary.pairs_explored
    assert second_summary.new_discoveries == 0

    after_count = collection.aggregate.over_all(total_count=True).total_count
    assert after_count == len(response.objects)
