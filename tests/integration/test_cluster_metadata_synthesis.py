"""
Integration tests for cluster metadata synthesis + persistence.
"""

import json

import pytest

from mnemosyne.alexandria.cluster_profile_repository import ClusterProfileRepository
from mnemosyne.argus.cluster_metadata_synthesis import (
    ClusterData,
    ClusterMetadataSynthesizer,
)


@pytest.mark.integration
def test_synthesis_and_storage_with_mocked_llm(postgres_connection, mocker):
    repo = ClusterProfileRepository(postgres_connection)
    repo.ensure_table()

    mock_ollama = mocker.MagicMock()
    mock_ollama.generate.return_value = {
        "response": json.dumps(
            {
                "cluster_id": "cluster-99",
                "theme_summary": "Knowledge management themes",
                "key_entities": ["notes"],
                "dominant_topics": ["knowledge"],
                "tags": ["research"],
                "confidence_score": 0.77,
                "representative_note_ids": ["note-10"],
            }
        )
    }

    synthesizer = ClusterMetadataSynthesizer(mock_ollama)
    cluster = ClusterData(
        cluster_id="cluster-99",
        representative_notes=["Note content"],
        representative_note_ids=["note-10"],
    )

    result = synthesizer.synthesize(cluster)
    assert result.profile is not None

    repo.save(result.profile)
    fetched = repo.get("cluster-99")

    assert fetched is not None
    assert fetched.theme_summary == "Knowledge management themes"
