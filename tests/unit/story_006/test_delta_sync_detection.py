"""Unit tests for delta sync change detection."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from mnemosyne.argus.delta_sync import ClusterSnapshot, ClusterSyncState, DeltaSyncDetector


def test_detects_changed_clusters_by_last_modified() -> None:
    now = datetime.now(UTC)
    state = ClusterSyncState(
        cluster_id="42",
        last_sync_timestamp=now - timedelta(hours=1),
        vector_count_at_sync=10,
        profile_hash="hash-a",
        sync_status="success",
        last_error=None,
    )
    snapshot = ClusterSnapshot(
        cluster_id="42",
        vector_count=10,
        last_modified=now,
    )

    detector = DeltaSyncDetector()
    changed = detector.identify_changed([snapshot], {"42": state})

    assert changed == ["42"]


def test_detects_changed_clusters_by_vector_count_when_no_timestamp() -> None:
    now = datetime.now(UTC)
    state = ClusterSyncState(
        cluster_id="7",
        last_sync_timestamp=now - timedelta(days=1),
        vector_count_at_sync=5,
        profile_hash="hash-b",
        sync_status="success",
        last_error=None,
    )
    snapshot = ClusterSnapshot(
        cluster_id="7",
        vector_count=9,
        last_modified=None,
    )

    detector = DeltaSyncDetector()
    changed = detector.identify_changed([snapshot], {"7": state})

    assert changed == ["7"]


def test_skips_unchanged_clusters() -> None:
    now = datetime.now(UTC)
    state = ClusterSyncState(
        cluster_id="1",
        last_sync_timestamp=now,
        vector_count_at_sync=3,
        profile_hash="hash-c",
        sync_status="success",
        last_error=None,
    )
    snapshot = ClusterSnapshot(
        cluster_id="1",
        vector_count=3,
        last_modified=now - timedelta(minutes=1),
    )

    detector = DeltaSyncDetector()
    changed = detector.identify_changed([snapshot], {"1": state})

    assert changed == []
