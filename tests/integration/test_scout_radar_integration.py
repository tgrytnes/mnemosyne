"""
Integration test for Scout latent radar scoring with real embeddings.
"""

import pytest

from mnemosyne.argus.scout.radar import (
    ClusterRepresentation,
    ConceptPrototype,
    LatentRadar,
)


def _embed(ollama_client, text: str) -> list[float]:
    response = ollama_client.embeddings(model="qwen3-embedding:0.6b", prompt=text)
    return response["embedding"]


@pytest.mark.integration
def test_latent_radar_detects_private_projectness(ollama_client):
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
            embedding=_embed(
                ollama_client,
                "Renovate the kitchen with a timeline, budget, and materials list.",
            ),
        ),
        ClusterRepresentation(
            cluster_id="project_training",
            text="Draft a 12-week training program with milestones and weekly goals.",
            embedding=_embed(
                ollama_client,
                "Draft a 12-week training program with milestones and weekly goals.",
            ),
        ),
        ClusterRepresentation(
            cluster_id="non_project_history",
            text="Notes on Roman empire politics and historical events.",
            embedding=_embed(
                ollama_client,
                "Notes on Roman empire politics and historical events.",
            ),
        ),
    ]

    radar = LatentRadar(lambda text: _embed(ollama_client, text))
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
    detected_ids = {detection.cluster_ids[0] for detection in detections}

    assert "project_renovation" in detected_ids
    assert "project_training" in detected_ids
    assert "non_project_history" not in detected_ids
