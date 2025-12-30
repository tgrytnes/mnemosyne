"""
Unit tests for Scout pattern detectors.
"""

from mnemosyne.argus.scout.patterns import (
    ClusterStats,
    detect_contradictions,
    detect_emerging_themes,
    detect_orphans,
)
from mnemosyne.argus.scout.radar import ClusterRepresentation


def test_detect_emerging_themes():
    reps = {
        "1": ClusterRepresentation(cluster_id="1", text="alpha", embedding=[1.0, 0.0]),
        "2": ClusterRepresentation(cluster_id="2", text="beta", embedding=[0.0, 1.0]),
    }
    stats = [
        ClusterStats(cluster_id="1", recent_notes=3, previous_notes=0, total_notes=3),
        ClusterStats(cluster_id="2", recent_notes=1, previous_notes=2, total_notes=3),
    ]
    detections = detect_emerging_themes(
        stats, reps, min_recent_notes=2, max_previous_notes=0
    )

    assert len(detections) == 1
    assert detections[0].cluster_ids == ["1"]
    assert detections[0].pattern_type == "emerging_theme"


def test_detect_orphans_with_links():
    reps = {
        "a": ClusterRepresentation(cluster_id="a", text="alpha", embedding=[1.0, 0.0]),
        "b": ClusterRepresentation(cluster_id="b", text="beta", embedding=[0.0, 1.0]),
    }
    detections = detect_orphans(
        cluster_ids=["a", "b"],
        representations=reps,
        cluster_links={"a": ["b"]},
        min_neighbors=1,
    )

    assert len(detections) == 1
    assert detections[0].cluster_ids == ["b"]


def test_detect_contradictions_polarity_and_similarity():
    reps = [
        ClusterRepresentation(
            cluster_id="1",
            text="We should improve the process and it is good.",
            embedding=[1.0, 0.0],
        ),
        ClusterRepresentation(
            cluster_id="2",
            text="The process is bad and will fail.",
            embedding=[0.9, 0.1],
        ),
        ClusterRepresentation(
            cluster_id="3",
            text="Neutral note without sentiment.",
            embedding=[0.0, 1.0],
        ),
    ]

    detections = detect_contradictions(
        reps,
        similarity_threshold=0.8,
        polarity_threshold=0.5,
    )

    assert detections
    assert detections[0].pattern_type == "contradiction"
    assert set(detections[0].cluster_ids) == {"1", "2"}
