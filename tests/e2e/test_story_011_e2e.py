"""
E2E test for Story 011: radar exploration finds at least one weak link and persists it with identity.
"""

import pytest

from mnemosyne.argus.scout.radar import ClusterRepresentation


def _embed(ollama_client, text: str) -> list[float]:
    response = ollama_client.embeddings(model="qwen3-embedding:0.6b", prompt=text)
    return response["embedding"]


@pytest.mark.e2e
@pytest.mark.weaviate
def test_story_011_radar_exploration_end_to_end(
    tmp_path, weaviate_client, ollama_client, clean_weaviate_collection
):
    from mnemosyne.argus.scout.radar_explorer import ExplorationSummary, RadarExplorer

    clusters = [
        ClusterRepresentation(
            cluster_id="cluster-renovation",
            text="Renovation planning with tasks, budget, and contractor notes.",
            embedding=_embed(ollama_client, "Renovation planning tasks budget contractor"),
        ),
        ClusterRepresentation(
            cluster_id="cluster-lab",
            text="Home lab setup with docker-compose services and monitoring.",
            embedding=_embed(ollama_client, "Home lab docker compose services monitoring stack"),
        ),
        ClusterRepresentation(
            cluster_id="cluster-recipes",
            text="Recipes and cooking journal (noise).",
            embedding=_embed(ollama_client, "Recipes cooking journal with ingredients"),
        ),
    ]

    explorer = RadarExplorer(
        weaviate_client=weaviate_client,
        embedder=lambda text: _embed(ollama_client, text),
        strategy="breadth_first",
        budget_seconds=20,
        checkpoint_path=tmp_path / "radar_state.json",
        discovery_job_key="story-011-e2e",
        max_pairs_per_cluster=3,
    )

    summary: ExplorationSummary = explorer.run(clusters)
    assert summary.new_discoveries >= 1
    assert summary.pairs_explored > 0

    collection = weaviate_client.collections.get("Discoveries")
    result = collection.query.fetch_objects(limit=5)
    assert result.objects
    stored = result.objects[0].properties
    assert stored["discoveryJobKey"] == "story-011-e2e"
    assert stored["candidateKey"]
    assert stored["discoveryId"]
    assert stored["confidenceScore"] > 0
