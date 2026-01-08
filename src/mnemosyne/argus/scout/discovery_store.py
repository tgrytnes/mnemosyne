"""Weaviate persistence for Scout discoveries."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from weaviate.classes.query import Filter

from mnemosyne.alexandria.weaviate_schema import Discoveries, WeaviateSchemaManager
from mnemosyne.argus.scout.radar import ConceptDetection


@dataclass(frozen=True)
class RunMetadata:
    run_id: str
    clusters_analyzed: int
    errors: list[str]
    dry_run: bool


@dataclass(frozen=True)
class StoreResult:
    stored_ids: list[str]
    skipped_duplicates: int


class DiscoveryStore:
    """Store discovery records with deduplication and run metadata."""

    def __init__(self, client, dedup_similarity_threshold: float = 0.8):
        self._client = client
        self._dedup_threshold = dedup_similarity_threshold
        self._schema = WeaviateSchemaManager(client)
        self._schema.ensure_collection_exists(Discoveries.collection_name)

    def store_detections(
        self,
        detections: Iterable[ConceptDetection],
        run_metadata: RunMetadata,
    ) -> StoreResult:
        detections = list(detections)
        if not detections:
            return StoreResult(stored_ids=[], skipped_duplicates=0)

        collection = self._client.collections.get(Discoveries.collection_name)
        stored_ids: list[str] = []
        skipped_duplicates = 0

        grouped: dict[str, list[ConceptDetection]] = {}
        for detection in detections:
            grouped.setdefault(detection.pattern_type, []).append(detection)

        for pattern_type, group in grouped.items():
            existing = self._fetch_existing_by_pattern(collection, pattern_type=pattern_type)
            for detection in group:
                if self._is_duplicate(detection.cluster_ids, existing):
                    skipped_duplicates += 1
                    continue
                existing.append(detection.cluster_ids)
                if run_metadata.dry_run:
                    continue

                properties = {
                    "patternType": detection.pattern_type,
                    "clusterIds": detection.cluster_ids,
                    "confidenceScore": detection.confidence_score,
                    "detectedAt": datetime.now(UTC),
                    "signals": json.dumps(
                        {"concept_key": detection.concept_key, **detection.signals},
                        sort_keys=True,
                    ),
                    "runId": run_metadata.run_id,
                    "clustersAnalyzed": run_metadata.clusters_analyzed,
                    "errors": json.dumps(run_metadata.errors, sort_keys=True),
                    "dryRun": run_metadata.dry_run,
                }
                if detection.discovery_id:
                    properties["discoveryId"] = detection.discovery_id
                if detection.discovery_job_key:
                    properties["discoveryJobKey"] = detection.discovery_job_key
                if detection.candidate_key:
                    properties["candidateKey"] = detection.candidate_key
                response = collection.data.insert(
                    properties=properties,
                    vector={"default": detection.embedding},
                )
                stored_ids.append(str(response))

        return StoreResult(stored_ids=stored_ids, skipped_duplicates=skipped_duplicates)

    def _fetch_existing_by_pattern(self, collection, pattern_type: str) -> list[list[str]]:
        response = collection.query.fetch_objects(
            filters=Filter.by_property("patternType").equal(pattern_type),
            limit=1000,
        )
        existing: list[list[str]] = []
        for obj in response.objects:
            cluster_ids = obj.properties.get("clusterIds")
            parsed = _parse_cluster_ids(cluster_ids)
            if parsed:
                existing.append(parsed)
        return existing

    def _is_duplicate(self, cluster_ids: list[str], existing: Iterable[list[str]]) -> bool:
        for existing_ids in existing:
            if jaccard_similarity(cluster_ids, existing_ids) >= self._dedup_threshold:
                return True
        return False


def _parse_cluster_ids(raw) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(item) for item in raw]
    if isinstance(raw, str):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            value = raw
        if isinstance(value, list):
            return [str(item) for item in value]
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
    return []


def jaccard_similarity(left: Iterable[str], right: Iterable[str]) -> float:
    left_set = {str(item) for item in left}
    right_set = {str(item) for item in right}
    if not left_set and not right_set:
        return 1.0
    union = left_set | right_set
    if not union:
        return 0.0
    intersection = left_set & right_set
    return len(intersection) / len(union)
