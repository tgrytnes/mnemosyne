"""
Unit tests for Scout latent radar scoring.
"""

from mnemosyne.argus.scout.discovery_store import jaccard_similarity
from mnemosyne.argus.scout.radar import (
    ClusterRepresentation,
    ConceptPrototype,
    LatentRadar,
    best_margin_score,
)


def test_jaccard_similarity_basic():
    assert jaccard_similarity(["a", "b"], ["a"]) == 0.5
    assert jaccard_similarity(["a"], ["a"]) == 1.0
    assert jaccard_similarity([], []) == 1.0
    assert jaccard_similarity(["a"], ["b"]) == 0.0


def test_latent_radar_scores_margin():
    def embedder(text: str) -> list[float]:
        mapping = {
            "positive": [1.0, 0.0],
            "negative": [0.0, 1.0],
            "cluster": [0.9, 0.1],
        }
        return mapping[text]

    radar = LatentRadar(embedder)
    concept = ConceptPrototype(
        key="demo",
        positive_texts=["positive"],
        negative_texts=["negative"],
        threshold=0.2,
    )

    clusters = [
        ClusterRepresentation(cluster_id="c1", text="cluster", embedding=embedder("cluster"))
    ]
    detections = radar.detect(concept, clusters, pattern_type="project_candidate")

    assert len(detections) == 1
    detection = detections[0]
    assert detection.confidence_score > 0.0
    assert detection.signals["positive_max"] > detection.signals["negative_max"]
    assert detection.pattern_type == "project_candidate"


def test_latent_radar_respects_threshold():
    def embedder(text: str) -> list[float]:
        mapping = {
            "positive": [1.0, 0.0],
            "negative": [0.0, 1.0],
            "cluster": [0.55, 0.45],
        }
        return mapping[text]

    radar = LatentRadar(embedder)
    concept = ConceptPrototype(
        key="demo",
        positive_texts=["positive"],
        negative_texts=["negative"],
        threshold=0.2,
    )

    clusters = [
        ClusterRepresentation(cluster_id="c1", text="cluster", embedding=embedder("cluster"))
    ]
    detections = radar.detect(concept, clusters, pattern_type="project_candidate")

    assert detections == []


def test_latent_radar_supports_multiple_concepts():
    def embedder(text: str) -> list[float]:
        mapping = {
            "private": [1.0, 0.0],
            "professional": [0.0, 1.0],
            "cluster_private": [0.9, 0.1],
            "cluster_professional": [0.1, 0.9],
        }
        return mapping[text]

    radar = LatentRadar(embedder)
    private = ConceptPrototype(
        key="project_private",
        positive_texts=["private"],
        negative_texts=["professional"],
        threshold=0.3,
    )
    professional = ConceptPrototype(
        key="project_professional",
        positive_texts=["professional"],
        negative_texts=["private"],
        threshold=0.3,
    )

    clusters = [
        ClusterRepresentation(
            cluster_id="c1", text="cluster_private", embedding=embedder("cluster_private")
        ),
        ClusterRepresentation(
            cluster_id="c2",
            text="cluster_professional",
            embedding=embedder("cluster_professional"),
        ),
    ]

    private_hits = radar.detect(private, clusters, pattern_type="project_candidate")
    professional_hits = radar.detect(professional, clusters, pattern_type="project_candidate")

    assert {hit.cluster_ids[0] for hit in private_hits} == {"c1"}
    assert {hit.cluster_ids[0] for hit in professional_hits} == {"c2"}


def test_best_margin_score_selects_strongest_embedding():
    positive_vecs = [[1.0, 0.0]]
    negative_vecs = [[0.0, 1.0]]
    candidates = [[0.2, 0.8], [0.9, 0.1]]

    result = best_margin_score(candidates, positive_vecs, negative_vecs)

    assert result is not None
    score, pos_max, neg_max, embedding = result
    assert embedding == [0.9, 0.1]
    assert score > 0
    assert pos_max > neg_max
