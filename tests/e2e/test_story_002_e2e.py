"""
E2E tests for Story 002 structured metadata synthesis.
"""

import json
import time

import pytest

from mnemosyne.alexandria.cluster_profile_repository import ClusterProfileRepository
from mnemosyne.argus.cluster_metadata_synthesis import (
    ClusterData,
    ClusterMetadataSynthesizer,
)


@pytest.mark.e2e
def test_story_002_end_to_end_pipeline(postgres_connection, mocker):
    repo = ClusterProfileRepository(postgres_connection)
    repo.ensure_table()

    clusters = [
        ClusterData(
            cluster_id=f"cluster-{i}",
            representative_notes=[f"Note content {i}"],
            representative_note_ids=[f"note-{i}"],
            tags=["research"],
        )
        for i in range(20)
    ]

    responses = [
        {
            "response": json.dumps(
                {
                    "cluster_id": cluster.cluster_id,
                    "theme_summary": f"Summary {cluster.cluster_id}",
                    "key_entities": ["entity"],
                    "dominant_topics": ["topic"],
                    "tags": cluster.tags,
                    "confidence_score": 0.8,
                    "representative_note_ids": cluster.representative_note_ids,
                }
            )
        }
        for cluster in clusters
    ]

    mock_ollama = mocker.MagicMock()
    mock_ollama.generate.side_effect = responses

    synthesizer = ClusterMetadataSynthesizer(mock_ollama)

    start = time.monotonic()
    results = [synthesizer.synthesize(cluster) for cluster in clusters]
    elapsed = time.monotonic() - start

    success_rate = sum(1 for result in results if result.status == "success") / len(results)
    assert success_rate >= 0.95
    assert elapsed < 5 * 60

    for result in results:
        repo.save(result.profile)

    fetched = repo.get("cluster-0")
    assert fetched is not None
    assert fetched.theme_summary == "Summary cluster-0"
