"""Delta sync node for re-processing changed clusters."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256

from apscheduler.schedulers.background import BackgroundScheduler

from mnemosyne.alexandria.cluster_profile_repository import ClusterProfileRepository
from mnemosyne.alexandria.cluster_sync_state_repository import (
    ClusterSyncState,
    ClusterSyncStateRepository,
)
from mnemosyne.alexandria.weaviate_schema import ClusterCentroidCollection
from mnemosyne.argus.cluster_metadata_synthesis import ClusterData, ClusterMetadataSynthesizer
from mnemosyne.argus.nodes.cluster_representatives import GetClusterRepresentatives

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ClusterSnapshot:
    cluster_id: str
    vector_count: int
    last_modified: datetime | None


class DeltaSyncDetector:
    """Identify clusters requiring delta sync."""

    def identify_changed(
        self,
        snapshots: list[ClusterSnapshot],
        states: dict[str, ClusterSyncState],
    ) -> list[str]:
        changed: list[str] = []
        for snapshot in snapshots:
            state = states.get(snapshot.cluster_id)
            if state is None:
                changed.append(snapshot.cluster_id)
                continue

            last_sync = state.last_sync_timestamp
            if snapshot.last_modified and last_sync:
                if snapshot.last_modified > last_sync:
                    changed.append(snapshot.cluster_id)
                    continue

            if snapshot.last_modified is None:
                if snapshot.vector_count != state.vector_count_at_sync:
                    changed.append(snapshot.cluster_id)
        return changed


@dataclass
class DeltaSyncConfig:
    schedule_minutes: int = 30
    max_retries: int = 2
    retry_backoff_seconds: float = 2.0


@dataclass
class DeltaSyncStats:
    total_clusters: int
    changed_clusters: int
    processed_clusters: int
    skipped_clusters: int
    profile_updates: int
    graph_updates: int
    cache_invalidations: int
    failed_clusters: int
    duration_seconds: float


def compute_profile_hash(profile) -> str:
    payload = json.dumps(profile.model_dump(), sort_keys=True, default=str)
    return sha256(payload.encode()).hexdigest()


class DeltaSyncNode:
    """Run delta sync for changed clusters and update downstream systems."""

    def __init__(
        self,
        *,
        weaviate_client,
        postgres_connection,
        ollama_client,
        graph_pipeline=None,
        cache_store=None,
        config: DeltaSyncConfig | None = None,
    ) -> None:
        self.weaviate_client = weaviate_client
        self.postgres_connection = postgres_connection
        self.ollama_client = ollama_client
        self.graph_pipeline = graph_pipeline
        self.cache_store = cache_store
        self.config = config or DeltaSyncConfig()

        self.profile_repo = ClusterProfileRepository(postgres_connection)
        self.profile_repo.ensure_table()
        self.sync_repo = ClusterSyncStateRepository(postgres_connection)
        self.sync_repo.ensure_table()
        self.detector = DeltaSyncDetector()

    def run_once(self) -> DeltaSyncStats:
        start = time.monotonic()
        snapshots = self._fetch_cluster_snapshots()
        states = {state.cluster_id: state for state in self.sync_repo.list_all()}
        changed_ids = self.detector.identify_changed(snapshots, states)
        snapshot_map = {snapshot.cluster_id: snapshot for snapshot in snapshots}

        processed = 0
        skipped = 0
        updated_profiles = 0
        updated_graph = 0
        invalidations = 0
        failed = 0

        for cluster_id in changed_ids:
            snapshot = snapshot_map[cluster_id]
            result = self._process_cluster(cluster_id, snapshot, states.get(cluster_id))
            if result["status"] == "success":
                processed += 1
                updated_profiles += result["profile_updated"]
                updated_graph += result["graph_updated"]
                invalidations += result["cache_invalidations"]
            elif result["status"] == "skipped":
                skipped += 1
            else:
                failed += 1

        duration = time.monotonic() - start
        stats = DeltaSyncStats(
            total_clusters=len(snapshots),
            changed_clusters=len(changed_ids),
            processed_clusters=processed,
            skipped_clusters=skipped,
            profile_updates=updated_profiles,
            graph_updates=updated_graph,
            cache_invalidations=invalidations,
            failed_clusters=failed,
            duration_seconds=duration,
        )

        logger.info(
            "Delta sync complete: %s changed, %s processed, %s skipped, %s failed in %.2fs",
            stats.changed_clusters,
            stats.processed_clusters,
            stats.skipped_clusters,
            stats.failed_clusters,
            stats.duration_seconds,
        )
        return stats

    def _fetch_cluster_snapshots(self) -> list[ClusterSnapshot]:
        centroid_collection = self.weaviate_client.collections.get(
            ClusterCentroidCollection.collection_name
        )
        response = centroid_collection.query.fetch_objects(limit=10000)
        snapshots: list[ClusterSnapshot] = []
        for obj in response.objects:
            cluster_id = str(obj.properties.get("clusterId"))
            vector_count = int(obj.properties.get("clusterSize") or 0)
            last_updated = obj.properties.get("lastUpdated")
            last_modified = None
            if last_updated:
                try:
                    last_modified = datetime.fromisoformat(str(last_updated).replace("Z", "+00:00"))
                except Exception:
                    last_modified = None
            snapshots.append(
                ClusterSnapshot(
                    cluster_id=cluster_id,
                    vector_count=vector_count,
                    last_modified=last_modified,
                )
            )
        return snapshots

    def _process_cluster(
        self,
        cluster_id: str,
        snapshot: ClusterSnapshot,
        existing_state: ClusterSyncState | None,
    ) -> dict:
        last_error = None
        for attempt in range(self.config.max_retries + 1):
            try:
                profile_updated, graph_updated, cache_invalidations = self._sync_cluster(
                    cluster_id,
                    snapshot,
                    existing_state,
                )
                return {
                    "status": "success",
                    "profile_updated": profile_updated,
                    "graph_updated": graph_updated,
                    "cache_invalidations": cache_invalidations,
                }
            except Exception as exc:
                last_error = str(exc)
                if attempt < self.config.max_retries:
                    time.sleep(self.config.retry_backoff_seconds * (attempt + 1))
                else:
                    break

        now = datetime.now(UTC)
        state = ClusterSyncState(
            cluster_id=cluster_id,
            last_sync_timestamp=now,
            vector_count_at_sync=snapshot.vector_count,
            profile_hash=existing_state.profile_hash if existing_state else None,
            sync_status="failed",
            last_error=last_error,
            next_sync_scheduled=now + timedelta(minutes=self.config.schedule_minutes),
        )
        self.sync_repo.upsert(state)
        logger.error("Delta sync failed for cluster %s: %s", cluster_id, last_error)
        return {"status": "failed", "profile_updated": 0, "graph_updated": 0}

    def _sync_cluster(
        self,
        cluster_id: str,
        snapshot: ClusterSnapshot,
        existing_state: ClusterSyncState | None,
    ) -> tuple[int, int, int]:
        cluster_int = int(cluster_id)
        reps_node = GetClusterRepresentatives(self.weaviate_client)
        state = {"cluster_id": cluster_int, "representative_chunks": [], "error": None}
        reps_state = reps_node(state)
        reps = reps_state.get("representative_chunks", [])
        notes = [rep.text for rep in reps]
        note_ids = [rep.chunk_id for rep in reps]

        if not notes:
            raise ValueError(f"No representative chunks for cluster {cluster_id}")

        cluster_data = ClusterData(
            cluster_id=cluster_id,
            representative_notes=notes,
            representative_note_ids=note_ids,
            tags=None,
        )

        synthesizer = ClusterMetadataSynthesizer(self.ollama_client)
        result = synthesizer.synthesize(cluster_data)
        if result.status != "success" or result.profile is None:
            raise ValueError(result.error or "Profile synthesis failed")

        profile = result.profile
        profile_hash = compute_profile_hash(profile)
        now = datetime.now(UTC)
        profile_updated = 0
        graph_updated = 0
        cache_invalidations = 0

        if existing_state is None or existing_state.profile_hash != profile_hash:
            self.profile_repo.save(profile)
            profile_updated = 1

            if self.graph_pipeline:
                self.graph_pipeline.build_graph(cluster_ids=[cluster_id])
                graph_updated = 1

            if self.cache_store:
                cache_invalidations = self.cache_store.invalidate_by_cluster_ids([cluster_id])
        else:
            logger.info("Cluster %s profile unchanged; skipping graph update", cluster_id)

        sync_status = "success" if profile_updated else "skipped"
        state = ClusterSyncState(
            cluster_id=cluster_id,
            last_sync_timestamp=now,
            vector_count_at_sync=snapshot.vector_count,
            profile_hash=profile_hash,
            sync_status=sync_status,
            last_error=None,
            next_sync_scheduled=now + timedelta(minutes=self.config.schedule_minutes),
        )
        self.sync_repo.upsert(state)

        return profile_updated, graph_updated, cache_invalidations


def start_delta_sync_scheduler(node: DeltaSyncNode, interval_minutes: int) -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(node.run_once, "interval", minutes=interval_minutes)
    scheduler.start()
    return scheduler
