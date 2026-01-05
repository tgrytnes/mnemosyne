"""
Unit tests for DeltaSyncNode profile source handling.
"""

from datetime import UTC, datetime
from types import SimpleNamespace

from mnemosyne.alexandria.the_gates import ClusterProfile
from mnemosyne.argus.delta_sync import ClusterSnapshot, DeltaSyncConfig, DeltaSyncNode


def test_delta_sync_saves_profile_with_source(mocker):
    weaviate_client = mocker.MagicMock()
    postgres_connection = mocker.MagicMock()
    ollama_client = mocker.MagicMock()

    profile_repo = mocker.MagicMock()
    sync_repo = mocker.MagicMock()
    mocker.patch(
        "mnemosyne.argus.delta_sync.ClusterProfileRepository",
        return_value=profile_repo,
    )
    mocker.patch(
        "mnemosyne.argus.delta_sync.ClusterSyncStateRepository",
        return_value=sync_repo,
    )

    rep = SimpleNamespace(text="representative text", chunk_id="chunk-1")
    reps_node = mocker.MagicMock(return_value={"representative_chunks": [rep], "error": None})
    mocker.patch("mnemosyne.argus.delta_sync.GetClusterRepresentatives", return_value=reps_node)

    profile = ClusterProfile(
        cluster_id="1",
        theme_summary="Lethe profile",
        key_entities=["entity"],
        dominant_topics=["topic"],
        tags=["lethe"],
        confidence_score=0.6,
        representative_note_ids=["chunk-1"],
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
        metadata={"source": "lethe"},
    )
    synth = mocker.MagicMock()
    synth.synthesize.return_value = SimpleNamespace(status="success", profile=profile)
    mocker.patch("mnemosyne.argus.delta_sync.ClusterMetadataSynthesizer", return_value=synth)

    node = DeltaSyncNode(
        weaviate_client=weaviate_client,
        postgres_connection=postgres_connection,
        ollama_client=ollama_client,
        config=DeltaSyncConfig(max_retries=0, retry_backoff_seconds=0.0),
        profile_source="lethe",
    )
    node._fetch_cluster_snapshots = mocker.MagicMock(
        return_value=[ClusterSnapshot(cluster_id="1", vector_count=1, last_modified=None)]
    )
    sync_repo.list_all.return_value = []

    node.run_once()

    profile_repo.save.assert_called_with(profile, source="lethe")
