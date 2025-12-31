"""Runner for Scout latent analysis over existing clusters."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

import weaviate
from weaviate.classes.query import Filter

from mnemosyne.alexandria.weaviate_schema import TheMuses
from mnemosyne.argus.nodes.cluster_representatives import GetClusterRepresentatives
from mnemosyne.argus.scout.discovery_store import DiscoveryStore, RunMetadata
from mnemosyne.argus.scout.patterns import (
    ClusterStats,
    detect_contradictions,
    detect_emerging_themes,
    detect_orphans,
    partition_note_times,
)
from mnemosyne.argus.scout.radar import (
    ClusterRepresentation,
    ConceptDetection,
    ConceptPrototype,
    LatentRadar,
)

Embedder = Callable[[str], list[float]]


@dataclass(frozen=True)
class ScoutConfig:
    project_concepts: list[ConceptPrototype]
    emerging_window_days: int = 30
    emerging_min_recent: int = 3
    emerging_max_previous: int = 1
    orphan_min_neighbors: int = 1
    contradiction_similarity_threshold: float = 0.75
    contradiction_polarity_threshold: float = 0.5
    dedup_similarity_threshold: float = 0.8
    cluster_representation_k: int = 5
    performance_target_seconds: int | None = None


@dataclass(frozen=True)
class ScoutRunSummary:
    run_id: str
    clusters_analyzed: int
    detections_by_type: dict[str, int]
    dry_run: bool
    duration_seconds: float
    errors: list[str]
    performance_target_seconds: int | None


class ScoutRunner:
    """Runs full Scout analysis and persists discoveries."""

    def __init__(
        self,
        client: weaviate.WeaviateClient,
        embedder: Embedder,
        config: ScoutConfig,
    ):
        self._client = client
        self._embedder = embedder
        self._config = config
        self._muses_collection = client.collections.get(TheMuses.collection_name)
        self._representatives = GetClusterRepresentatives(client=client)
        self._radar = LatentRadar(embedder)
        self._store = DiscoveryStore(
            client, dedup_similarity_threshold=config.dedup_similarity_threshold
        )

    def run(
        self,
        run_id: str | None = None,
        dry_run: bool = False,
        cluster_links: dict[str, list[str]] | None = None,
    ) -> ScoutRunSummary:
        start = datetime.now(UTC)
        errors: list[str] = []
        run_id = run_id or f"scout-{start.isoformat()}"

        cluster_ids = self._fetch_cluster_ids()
        representations: dict[str, ClusterRepresentation] = {}
        stats: list[ClusterStats] = []

        for cluster_id in cluster_ids:
            representation = self._build_representation(cluster_id, errors)
            if representation is None:
                continue
            representations[cluster_id] = representation
            stats.append(self._build_stats(cluster_id, errors))

        detections: list[ConceptDetection] = []
        detections.extend(
            detect_emerging_themes(
                stats,
                representations,
                min_recent_notes=self._config.emerging_min_recent,
                max_previous_notes=self._config.emerging_max_previous,
            )
        )
        detections.extend(
            detect_orphans(
                cluster_ids=cluster_ids,
                representations=representations,
                cluster_links=cluster_links,
                min_neighbors=self._config.orphan_min_neighbors,
            )
        )
        detections.extend(
            detect_contradictions(
                representations.values(),
                similarity_threshold=self._config.contradiction_similarity_threshold,
                polarity_threshold=self._config.contradiction_polarity_threshold,
            )
        )
        detections.extend(self._detect_project_candidates(representations.values()))

        run_metadata = RunMetadata(
            run_id=run_id,
            clusters_analyzed=len(representations),
            errors=errors,
            dry_run=dry_run,
        )
        self._store.store_detections(detections, run_metadata)

        duration_seconds = (datetime.now(UTC) - start).total_seconds()
        if self._config.performance_target_seconds is not None:
            if duration_seconds > self._config.performance_target_seconds:
                errors.append(
                    "Run exceeded performance target "
                    f"({duration_seconds:.2f}s > {self._config.performance_target_seconds}s)"
                )

        detections_by_type: dict[str, int] = {}
        for detection in detections:
            detections_by_type[detection.pattern_type] = (
                detections_by_type.get(detection.pattern_type, 0) + 1
            )

        return ScoutRunSummary(
            run_id=run_id,
            clusters_analyzed=len(representations),
            detections_by_type=detections_by_type,
            dry_run=dry_run,
            duration_seconds=duration_seconds,
            errors=errors,
            performance_target_seconds=self._config.performance_target_seconds,
        )

    def _fetch_cluster_ids(self) -> list[str]:
        response = self._muses_collection.query.fetch_objects(limit=10000)
        cluster_ids = {
            str(obj.properties.get("clusterId"))
            for obj in response.objects
            if obj.properties.get("clusterId") is not None
        }
        return sorted(cluster_ids)

    def _build_representation(
        self, cluster_id: str, errors: list[str]
    ) -> ClusterRepresentation | None:
        try:
            state = self._representatives({"cluster_id": int(cluster_id)})
        except Exception as exc:
            errors.append(f"Failed to get representatives for {cluster_id}: {exc}")
            return None

        reps = state.get("representative_chunks", [])
        if not reps:
            errors.append(f"No representatives for cluster {cluster_id}")
            return None

        reps = reps[: self._config.cluster_representation_k]
        text = "\n".join(rep.text for rep in reps if rep.text)
        if not text:
            errors.append(f"Empty representative text for cluster {cluster_id}")
            return None

        embedding = self._embedder(text)
        return ClusterRepresentation(cluster_id=cluster_id, text=text, embedding=embedding)

    def _build_stats(self, cluster_id: str, errors: list[str]) -> ClusterStats:
        response = self._muses_collection.query.fetch_objects(
            filters=Filter.by_property("clusterId").equal(int(cluster_id)),
            limit=10000,
        )
        timestamps = []
        for obj in response.objects:
            raw = obj.properties.get("fileModifiedAt")
            if raw is None:
                continue
            if isinstance(raw, datetime):
                timestamps.append(raw)
            elif isinstance(raw, str):
                parsed = _parse_datetime(raw)
                if parsed:
                    timestamps.append(parsed)
        recent, previous = partition_note_times(
            timestamps, window_days=self._config.emerging_window_days
        )
        return ClusterStats(
            cluster_id=cluster_id,
            recent_notes=recent,
            previous_notes=previous,
            total_notes=len(timestamps),
        )

    def _detect_project_candidates(
        self, representations: Iterable[ClusterRepresentation]
    ) -> list[ConceptDetection]:
        detections: list[ConceptDetection] = []
        for concept in self._config.project_concepts:
            detections.extend(
                self._radar.detect(
                    concept,
                    representations,
                    pattern_type="project_candidate",
                )
            )
        return detections


def _parse_datetime(raw: str) -> datetime | None:
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        return datetime.fromisoformat(raw)
    except ValueError:
        return None
