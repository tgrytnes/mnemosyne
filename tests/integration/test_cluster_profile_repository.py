"""
Integration tests for ClusterProfileRepository using PostgreSQL.
"""

from datetime import datetime

import pytest

from mnemosyne.alexandria.cluster_profile_repository import ClusterProfileRepository
from mnemosyne.alexandria.the_gates import ClusterProfile


@pytest.mark.integration
def test_save_and_get_profile(postgres_connection):
    repo = ClusterProfileRepository(postgres_connection)
    repo.ensure_table()

    profile = ClusterProfile(
        cluster_id="cluster-42",
        theme_summary="Automation and workflows",
        key_entities=["workflow"],
        dominant_topics=["automation"],
        tags=["ops"],
        confidence_score=0.88,
        representative_note_ids=["note-9"],
        created_at=datetime.utcnow(),
        metadata={"source": "test"},
    )

    repo.save(profile)
    fetched = repo.get("cluster-42")

    assert fetched is not None
    assert fetched.cluster_id == "cluster-42"
    assert fetched.theme_summary == "Automation and workflows"
