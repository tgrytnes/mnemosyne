"""Unit tests for cluster profile hashing."""

from __future__ import annotations

from datetime import UTC, datetime

from mnemosyne.alexandria.the_gates import ClusterProfile
from mnemosyne.argus.delta_sync import compute_profile_hash


def test_profile_hash_changes_on_content_change() -> None:
    base = ClusterProfile(
        cluster_id="cluster-1",
        theme_summary="Knowledge management",
        key_entities=["zettelkasten"],
        dominant_topics=["notes"],
        tags=["research"],
        confidence_score=0.8,
        representative_note_ids=["note-1"],
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
        metadata={"source": "unit"},
    )
    updated = base.model_copy(update={"theme_summary": "Knowledge management systems"})

    assert compute_profile_hash(base) != compute_profile_hash(updated)


def test_profile_hash_stable_for_same_content() -> None:
    profile = ClusterProfile(
        cluster_id="cluster-2",
        theme_summary="Project planning",
        key_entities=["timeline"],
        dominant_topics=["milestone"],
        tags=["project"],
        confidence_score=0.7,
        representative_note_ids=["note-2"],
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
        metadata={"source": "unit"},
    )

    assert compute_profile_hash(profile) == compute_profile_hash(profile)
