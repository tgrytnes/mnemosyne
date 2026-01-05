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

    repo.save(profile, source="test")
    fetched = repo.get("cluster-42", source="test")

    assert fetched is not None
    assert fetched.cluster_id == "cluster-42"
    assert fetched.theme_summary == "Automation and workflows"


@pytest.mark.integration
def test_profiles_with_same_cluster_id_can_be_distinguished(postgres_connection):
    repo = ClusterProfileRepository(postgres_connection)
    repo.ensure_table()

    profile_muses = ClusterProfile(
        cluster_id="cluster-99",
        theme_summary="Muses profile",
        key_entities=["vault"],
        dominant_topics=["notes"],
        tags=["muses"],
        confidence_score=0.91,
        representative_note_ids=["note-m"],
        created_at=datetime.utcnow(),
        metadata={"source": "muses"},
    )
    profile_lethe = ClusterProfile(
        cluster_id="cluster-99",
        theme_summary="Lethe profile",
        key_entities=["archive"],
        dominant_topics=["emails"],
        tags=["lethe"],
        confidence_score=0.72,
        representative_note_ids=["note-l"],
        created_at=datetime.utcnow(),
        metadata={"source": "lethe"},
    )

    repo.save(profile_muses, source="muses")
    repo.save(profile_lethe, source="lethe")

    fetched_muses = repo.get("cluster-99", source="muses")
    fetched_lethe = repo.get("cluster-99", source="lethe")

    assert fetched_muses is not None
    assert fetched_muses.theme_summary == "Muses profile"
    assert fetched_lethe is not None
    assert fetched_lethe.theme_summary == "Lethe profile"
