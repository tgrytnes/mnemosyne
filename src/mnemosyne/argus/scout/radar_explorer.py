"""Radar exploration for Story 011: explore pairs, store weak links with identity + checkpointing."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from collections.abc import Callable, Iterable, Sequence

import numpy as np
from mnemosyne.alexandria.weaviate_schema import Discoveries, WeaviateSchemaManager
from mnemosyne.argus.scout.radar import ClusterRepresentation


def make_candidate_key(discovery_job_key: str, cluster_ids: Sequence[str], link_type: str) -> str:
    ordered = sorted(str(c) for c in cluster_ids)
    return "|".join([discovery_job_key, *ordered, link_type])


class ExplorationState:
    """Persist explored cluster pairs to support incremental runs."""

    def __init__(self, path: Path):
        self.path = path
        self._explored: set[frozenset[str]] = set()
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text())
            for pair in raw.get("explored_pairs", []):
                if isinstance(pair, (list, tuple)) and len(pair) == 2:
                    self._explored.add(frozenset([str(pair[0]), str(pair[1])]))
        except json.JSONDecodeError:
            self._explored = set()

    def has_been_explored(self, pair: tuple[str, str]) -> bool:
        return frozenset(pair) in self._explored

    def mark_explored(self, pairs: Iterable[tuple[str, str]]) -> None:
        for a, b in pairs:
            self._explored.add(frozenset([str(a), str(b)]))

    def save(self) -> None:
        payload = {
            "explored_pairs": [sorted(list(pair)) for pair in self._explored],
        }
        self.path.write_text(json.dumps(payload, indent=2))


@dataclass
class WeakLinkDiscovery:
    discovery_id: str
    discovery_job_key: str
    candidate_key: str
    cluster_ids: list[str]
    confidence: float
    explanation: str
    embedding: list[float]
    explorer_strategy: str
    pattern_type: str = "weak_link"


@dataclass
class ExplorationSummary:
    pairs_explored: int
    new_discoveries: int
    strategy: str
    run_metadata: dict


class RadarExplorer:
    def __init__(
        self,
        weaviate_client,
        embedder: Callable[[str], list[float]],
        strategy: str = "breadth_first",
        budget_seconds: int = 30,
        checkpoint_path: Path | str | None = None,
        discovery_job_key: str = "latent-radar",
        max_pairs_per_cluster: int | None = None,
    ):
        self.client = weaviate_client
        self.embedder = embedder
        self.strategy = strategy
        self.budget_seconds = budget_seconds
        self.discovery_job_key = discovery_job_key
        self.max_pairs_per_cluster = max_pairs_per_cluster
        self.state = ExplorationState(Path(checkpoint_path)) if checkpoint_path else None
        WeaviateSchemaManager(self.client).ensure_collection_exists(Discoveries.collection_name)

    def run(self, clusters: list[ClusterRepresentation]) -> ExplorationSummary:
        start = time.perf_counter()
        pairs_explored = 0
        stored = 0

        normalized = {c.cluster_id: _normalize(np.array(c.embedding)) for c in clusters}
        pairs = _pair_candidates(clusters, strategy=self.strategy, limit=self.max_pairs_per_cluster)
        collection = self.client.collections.get(Discoveries.collection_name)

        # Clean up prior runs for this job key to avoid stale discoveries influencing assertions
        collection.data.delete_many(Filter.by_property("discoveryJobKey").equal(self.discovery_job_key))

        for c1, c2 in pairs:
            if time.perf_counter() - start > self.budget_seconds:
                break
            if self.state and self.state.has_been_explored((c1.cluster_id, c2.cluster_id)):
                continue

            sim = _cosine(normalized[c1.cluster_id], normalized[c2.cluster_id])
            pairs_explored += 1
            if sim < 0.15:
                self._mark_explored_pair(c1, c2)
                continue

            candidate_key = make_candidate_key(
                discovery_job_key=self.discovery_job_key,
                cluster_ids=[c1.cluster_id, c2.cluster_id],
                link_type="weak_link",
            )
            discovery = WeakLinkDiscovery(
                discovery_id=candidate_key,
                discovery_job_key=self.discovery_job_key,
                candidate_key=candidate_key,
                cluster_ids=[c1.cluster_id, c2.cluster_id],
                confidence=float(sim),
                explanation=f"Semantic proximity {sim:.2f}",
                embedding=((np.array(c1.embedding) + np.array(c2.embedding)) / 2).tolist(),
                explorer_strategy=self.strategy,
            )
            stored += int(self._store_if_new(collection, discovery))
            self._mark_explored_pair(c1, c2)

        if self.state:
            self.state.save()

        summary = ExplorationSummary(
            pairs_explored=pairs_explored,
            new_discoveries=stored,
            strategy=self.strategy,
            run_metadata={"discovery_job_key": self.discovery_job_key},
        )
        return summary

    def _mark_explored_pair(self, c1: ClusterRepresentation, c2: ClusterRepresentation) -> None:
        if self.state:
            self.state.mark_explored({(c1.cluster_id, c2.cluster_id)})

    def _store_if_new(self, collection, discovery: WeakLinkDiscovery) -> bool:
        existing = collection.query.fetch_objects(
            filters=Filter.by_property("candidateKey").equal(discovery.candidate_key),
            limit=1,
        )
        if existing.objects:
            return False

        properties = {
            "patternType": discovery.pattern_type,
            "clusterIds": discovery.cluster_ids,
            "confidenceScore": discovery.confidence,
            "detectedAt": datetime.utcnow(),
            "signals": json.dumps({"explanation": discovery.explanation}),
            "runId": self.discovery_job_key,
            "clustersAnalyzed": len(discovery.cluster_ids),
            "errors": json.dumps([], sort_keys=True),
            "dryRun": False,
            "discoveryJobKey": discovery.discovery_job_key,
            "candidateKey": discovery.candidate_key,
            "discoveryId": discovery.discovery_id,
            "explorerStrategy": discovery.explorer_strategy,
        }
        collection.data.insert(properties=properties, vector=discovery.embedding)
        return True


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) or 1e-9
    return float(np.dot(a, b) / denom)


def _normalize(vec: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vec)
    if norm == 0:
        return vec
    return vec / norm


def _pair_candidates(
    clusters: list[ClusterRepresentation], strategy: str, limit: int | None
) -> list[tuple[ClusterRepresentation, ClusterRepresentation]]:
    pairs: list[tuple[ClusterRepresentation, ClusterRepresentation]] = []
    n = len(clusters)
    for i in range(n):
        added = 0
        for j in range(i + 1, n):
            pairs.append((clusters[i], clusters[j]))
            added += 1
            if limit and added >= limit:
                break
    if strategy == "curiosity":
        # Sort by textual length difference as a proxy for diversity; similarity checked later
        pairs.sort(key=lambda p: abs(len(p[0].text) - len(p[1].text)), reverse=True)
    return pairs
