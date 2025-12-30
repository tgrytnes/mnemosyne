"""Pattern detectors for Scout latent analysis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable

from mnemosyne.argus.scout.radar import ClusterRepresentation, ConceptDetection, cosine_similarity


@dataclass(frozen=True)
class ClusterStats:
    cluster_id: str
    recent_notes: int
    previous_notes: int
    total_notes: int


def detect_emerging_themes(
    cluster_stats: Iterable[ClusterStats],
    representations: dict[str, ClusterRepresentation],
    min_recent_notes: int,
    max_previous_notes: int,
) -> list[ConceptDetection]:
    detections: list[ConceptDetection] = []
    for stats in cluster_stats:
        if stats.recent_notes < min_recent_notes:
            continue
        if stats.previous_notes > max_previous_notes:
            continue
        cluster = representations.get(stats.cluster_id)
        if cluster is None:
            continue
        confidence = stats.recent_notes / max(stats.total_notes, 1)
        detections.append(
            ConceptDetection(
                concept_key="emerging_theme",
                pattern_type="emerging_theme",
                cluster_ids=[stats.cluster_id],
                confidence_score=confidence,
                signals={
                    "recent_notes": float(stats.recent_notes),
                    "previous_notes": float(stats.previous_notes),
                    "total_notes": float(stats.total_notes),
                },
                embedding=cluster.embedding,
            )
        )
    return detections


def detect_orphans(
    cluster_ids: Iterable[str],
    representations: dict[str, ClusterRepresentation],
    cluster_links: dict[str, list[str]] | None = None,
    min_neighbors: int = 1,
) -> list[ConceptDetection]:
    detections: list[ConceptDetection] = []
    cluster_links = cluster_links or {}

    for cluster_id in cluster_ids:
        neighbors = cluster_links.get(cluster_id, [])
        if len(neighbors) >= min_neighbors:
            continue
        cluster = representations.get(cluster_id)
        if cluster is None:
            continue
        detections.append(
            ConceptDetection(
                concept_key="orphan_cluster",
                pattern_type="orphan",
                cluster_ids=[cluster_id],
                confidence_score=1.0,
                signals={"neighbor_count": float(len(neighbors))},
                embedding=cluster.embedding,
            )
        )
    return detections


def detect_contradictions(
    representations: Iterable[ClusterRepresentation],
    similarity_threshold: float,
    polarity_threshold: float,
) -> list[ConceptDetection]:
    reps = list(representations)
    detections: list[ConceptDetection] = []

    for i, left in enumerate(reps):
        for right in reps[i + 1 :]:
            similarity = cosine_similarity(left.embedding, right.embedding)
            if similarity < similarity_threshold:
                continue
            left_polarity = polarity_score(left.text)
            right_polarity = polarity_score(right.text)
            polarity_gap = abs(left_polarity - right_polarity)
            if polarity_gap < polarity_threshold:
                continue
            if left_polarity == 0.0 or right_polarity == 0.0:
                continue
            if left_polarity * right_polarity > 0:
                continue

            confidence = min(1.0, similarity * polarity_gap)
            avg_embedding = [
                (l + r) / 2 for l, r in zip(left.embedding, right.embedding)
            ]
            detections.append(
                ConceptDetection(
                    concept_key="contradiction",
                    pattern_type="contradiction",
                    cluster_ids=[left.cluster_id, right.cluster_id],
                    confidence_score=confidence,
                    signals={
                        "similarity": similarity,
                        "polarity_left": left_polarity,
                        "polarity_right": right_polarity,
                    },
                    embedding=avg_embedding,
                )
            )
    return detections


def polarity_score(text: str) -> float:
    positive_terms = {
        "improve",
        "success",
        "good",
        "benefit",
        "positive",
        "increase",
        "support",
        "agree",
        "effective",
    }
    negative_terms = {
        "fail",
        "bad",
        "risk",
        "negative",
        "decrease",
        "harm",
        "oppose",
        "ineffective",
        "issue",
    }
    tokens = [token.strip(".,!?;:()[]").lower() for token in text.split()]
    positive = sum(1 for token in tokens if token in positive_terms)
    negative = sum(1 for token in tokens if token in negative_terms)
    total = positive + negative
    if total == 0:
        return 0.0
    return (positive - negative) / total


def partition_note_times(
    timestamps: Iterable[datetime],
    window_days: int,
    now: datetime | None = None,
) -> tuple[int, int]:
    now = now or datetime.utcnow()
    cutoff = now - timedelta(days=window_days)
    recent = 0
    previous = 0
    for timestamp in timestamps:
        if timestamp >= cutoff:
            recent += 1
        else:
            previous += 1
    return recent, previous
