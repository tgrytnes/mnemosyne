"""
Unit tests for ClusterProfile schema.
"""

import pytest

from mnemosyne.alexandria.the_gates import ClusterProfile


class TestClusterProfile:
    """Test ClusterProfile validation and defaults."""

    def test_valid_profile(self):
        profile = ClusterProfile(
            cluster_id="cluster-1",
            theme_summary="Project planning and milestones",
            key_entities=["milestone", "schedule"],
            dominant_topics=["planning", "delivery"],
            tags=["project"],
            confidence_score=0.82,
            representative_note_ids=["note-1"],
            metadata={"sources": ["note-1"]},
        )

        assert profile.cluster_id == "cluster-1"
        assert profile.theme_summary
        assert profile.confidence_score == 0.82

    def test_missing_required_fields_raises(self):
        with pytest.raises(Exception):
            ClusterProfile(
                cluster_id="cluster-1",
                key_entities=["x"],
                dominant_topics=["y"],
                tags=[],
                confidence_score=0.1,
                representative_note_ids=[],
            )
