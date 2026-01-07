"""
Unit tests for DeltaSyncDetector timestamp handling.
"""

from datetime import UTC, datetime

from mnemosyne.alexandria.cluster_sync_state_repository import ClusterSyncState
from mnemosyne.argus.delta_sync import ClusterSnapshot, DeltaSyncDetector


def test_identify_changed_handles_naive_and_aware_timestamps():
    detector = DeltaSyncDetector()
    snapshots = [
        ClusterSnapshot(
            cluster_id="1",
            vector_count=1,
            last_modified=datetime(2025, 1, 2, tzinfo=UTC),
        )
    ]
    state = ClusterSyncState(
        cluster_id="1",
        last_sync_timestamp=datetime(2025, 1, 1),
        vector_count_at_sync=1,
        profile_hash=None,
        sync_status="success",
        last_error=None,
    )

    changed = detector.identify_changed(snapshots, {"1": state})

    assert changed == ["1"]
