"""
Unit tests for ClusterProfileRepository.
"""

from mnemosyne.alexandria.cluster_profile_repository import ClusterProfileRepository
from mnemosyne.alexandria.the_gates import ClusterProfile


class TestClusterProfileRepository:
    """Test repository SQL interactions."""

    def test_ensure_table_executes_ddl(self, mocker):
        connection = mocker.MagicMock()
        repo = ClusterProfileRepository(connection)

        repo.ensure_table()

        connection.cursor.assert_called_once()
        connection.commit.assert_called_once()

    def test_save_executes_insert(self, mocker):
        connection = mocker.MagicMock()
        repo = ClusterProfileRepository(connection)

        profile = ClusterProfile(
            cluster_id="cluster-1",
            theme_summary="Summary",
            key_entities=["entity"],
            dominant_topics=["topic"],
            tags=["tag"],
            confidence_score=0.5,
            representative_note_ids=["note-1"],
            metadata={"source": "test"},
        )

        repo.save(profile)

        connection.cursor.assert_called_once()
        connection.commit.assert_called_once()
