"""Latent radar scoring for Scout concept detection."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from hashlib import sha256
from math import sqrt

Embedder = Callable[[str], list[float]]


@dataclass(frozen=True)
class ConceptPrototype:
    """Defines a concept with positive/negative prototype texts."""

    key: str
    positive_texts: list[str]
    negative_texts: list[str]
    threshold: float


@dataclass(frozen=True)
class ClusterRepresentation:
    """Represents a cluster summary with its embedding."""

    cluster_id: str
    text: str
    embedding: list[float]


@dataclass(frozen=True)
class ConceptDetection:
    """Result of a concept detection on a single cluster."""

    concept_key: str
    pattern_type: str
    cluster_ids: list[str]
    confidence_score: float
    signals: dict[str, float]
    embedding: list[float]
    discovery_job_key: str | None = None
    candidate_key: str | None = None
    discovery_id: str | None = None


class LatentRadar:
    """Scores cluster representations against concept prototypes."""

    def __init__(self, embedder: Embedder):
        self._embedder = embedder

    def embed_prototypes(
        self, concept: ConceptPrototype
    ) -> tuple[list[list[float]], list[list[float]]]:
        positives = [self._embedder(text) for text in concept.positive_texts]
        negatives = [self._embedder(text) for text in concept.negative_texts]
        return positives, negatives

    def detect(
        self,
        concept: ConceptPrototype,
        clusters: Iterable[ClusterRepresentation],
        pattern_type: str,
    ) -> list[ConceptDetection]:
        positive_vecs, negative_vecs = self.embed_prototypes(concept)
        detections: list[ConceptDetection] = []

        for cluster in clusters:
            score, pos_max, neg_max = self.score(cluster.embedding, positive_vecs, negative_vecs)
            if score < concept.threshold:
                continue
            discovery_job_key, candidate_key, discovery_id = discovery_identity(
                concept.key, [cluster.cluster_id]
            )
            detections.append(
                ConceptDetection(
                    concept_key=concept.key,
                    pattern_type=pattern_type,
                    cluster_ids=[cluster.cluster_id],
                    confidence_score=score,
                    signals={
                        "positive_max": pos_max,
                        "negative_max": neg_max,
                        "threshold": concept.threshold,
                    },
                    embedding=cluster.embedding,
                    discovery_job_key=discovery_job_key,
                    candidate_key=candidate_key,
                    discovery_id=discovery_id,
                )
            )

        return detections

    def score(
        self,
        cluster_embedding: list[float],
        positive_vecs: list[list[float]],
        negative_vecs: list[list[float]],
    ) -> tuple[float, float, float]:
        pos_max = max(
            (cosine_similarity(cluster_embedding, vec) for vec in positive_vecs),
            default=0.0,
        )
        neg_max = max(
            (cosine_similarity(cluster_embedding, vec) for vec in negative_vecs),
            default=0.0,
        )
        return pos_max - neg_max, pos_max, neg_max


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    if len(a) != len(b):
        raise ValueError("Vectors must be same length for cosine similarity.")

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sqrt(sum(x * x for x in a))
    norm_b = sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def best_margin_score(
    embeddings: Iterable[list[float]],
    positive_vecs: list[list[float]],
    negative_vecs: list[list[float]],
) -> tuple[float, float, float, list[float]] | None:
    best: tuple[float, float, float, list[float]] | None = None
    for embedding in embeddings:
        score, pos_max, neg_max = _margin_score(embedding, positive_vecs, negative_vecs)
        if best is None or score > best[0]:
            best = (score, pos_max, neg_max, embedding)
    return best


def _margin_score(
    embedding: list[float],
    positive_vecs: list[list[float]],
    negative_vecs: list[list[float]],
) -> tuple[float, float, float]:
    pos_max = max(
        (cosine_similarity(embedding, vec) for vec in positive_vecs),
        default=0.0,
    )
    neg_max = max(
        (cosine_similarity(embedding, vec) for vec in negative_vecs),
        default=0.0,
    )
    return pos_max - neg_max, pos_max, neg_max


def discovery_identity(
    concept_key: str,
    cluster_ids: Iterable[str],
    candidate_label: str | None = None,
) -> tuple[str, str, str]:
    candidate_key = _candidate_key(cluster_ids, candidate_label=candidate_label)
    return concept_key, candidate_key, f"{concept_key}:{candidate_key}"


def _candidate_key(cluster_ids: Iterable[str], candidate_label: str | None = None) -> str:
    if candidate_label:
        return _slugify(candidate_label)
    return _hash_cluster_ids(cluster_ids)


def _hash_cluster_ids(cluster_ids: Iterable[str]) -> str:
    normalized = sorted(str(cluster_id) for cluster_id in cluster_ids)
    payload = "|".join(normalized)
    digest = sha256(payload.encode("utf-8")).hexdigest()
    return digest[:12]


def _slugify(value: str) -> str:
    cleaned = []
    for ch in value.strip().lower():
        if ch.isalnum() or ch in {"-", "_"}:
            cleaned.append(ch)
        elif ch.isspace():
            cleaned.append("_")
    slug = "".join(cleaned)
    return slug.strip("_") or "unknown"
