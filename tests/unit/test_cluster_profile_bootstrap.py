"""Unit tests for cluster profile bootstrap."""

from mnemosyne.argus.cluster_profile_bootstrap import ClusterProfileBootstrapper


def test_bootstrapper_skips_when_profiles_exist(mocker):
    repo = mocker.MagicMock()
    repo.has_profiles.return_value = True
    mocker.patch(
        "mnemosyne.argus.cluster_profile_bootstrap.ClusterProfileRepository",
        return_value=repo,
    )
    delta_sync = mocker.patch("mnemosyne.argus.cluster_profile_bootstrap.DeltaSyncNode")

    bootstrapper = ClusterProfileBootstrapper(
        weaviate_client=mocker.MagicMock(),
        postgres_connection=mocker.MagicMock(),
        llm_provider=mocker.MagicMock(),
        profile_source="lethe",
        centroid_collection_name="ClusterCentroidLethe",
        chunk_collection_name="TheLethe",
        text_property="body",
        source_property="sourcePath",
        heading_property="subject",
        chunk_index_property="chunkIndex",
    )

    assert bootstrapper.ensure_profiles(["1"]) == 0
    delta_sync.assert_not_called()


def test_bootstrapper_runs_delta_sync_when_empty(mocker):
    repo = mocker.MagicMock()
    repo.has_profiles.return_value = False
    mocker.patch(
        "mnemosyne.argus.cluster_profile_bootstrap.ClusterProfileRepository",
        return_value=repo,
    )

    node = mocker.MagicMock()
    node.run_once.return_value.profile_updates = 2
    mocker.patch("mnemosyne.argus.cluster_profile_bootstrap.DeltaSyncNode", return_value=node)

    bootstrapper = ClusterProfileBootstrapper(
        weaviate_client=mocker.MagicMock(),
        postgres_connection=mocker.MagicMock(),
        llm_provider=mocker.MagicMock(),
        profile_source="lethe",
        centroid_collection_name="ClusterCentroidLethe",
        chunk_collection_name="TheLethe",
        text_property="body",
        source_property="sourcePath",
        heading_property="subject",
        chunk_index_property="chunkIndex",
    )

    assert bootstrapper.ensure_profiles(["1"]) == 2
    node.run_once.assert_called_once_with(["1"])
