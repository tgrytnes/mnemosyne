"""
Unit tests for cluster metadata synthesis.
"""

import json

from mnemosyne.argus.cluster_metadata_synthesis import (
    ClusterData,
    ClusterMetadataSynthesizer,
)


class TestClusterMetadataSynthesizer:
    """Test LLM-driven cluster profile synthesis."""

    def test_synthesizes_profile_from_json(self, mocker):
        ollama_client = mocker.MagicMock()
        ollama_client.generate.return_value = {
            "response": json.dumps(
                {
                    "cluster_id": "cluster-1",
                    "theme_summary": "Project milestones and planning",
                    "key_entities": ["milestone"],
                    "dominant_topics": ["planning"],
                    "tags": ["project"],
                    "confidence_score": 0.9,
                    "representative_note_ids": ["note-1"],
                }
            )
        }

        synthesizer = ClusterMetadataSynthesizer(ollama_client)
        cluster = ClusterData(
            cluster_id="cluster-1",
            representative_notes=["Note content"],
            representative_note_ids=["note-1"],
        )

        result = synthesizer.synthesize(cluster)

        assert result.status == "success"
        assert result.profile is not None
        assert result.profile.theme_summary == "Project milestones and planning"
        ollama_client.generate.assert_called_once()

    def test_retries_on_invalid_json(self, mocker):
        ollama_client = mocker.MagicMock()
        ollama_client.generate.side_effect = [
            {"response": "not-json"},
            {
                "response": json.dumps(
                    {
                        "cluster_id": "cluster-1",
                        "theme_summary": "Valid JSON",
                        "key_entities": [],
                        "dominant_topics": [],
                        "tags": [],
                        "confidence_score": 0.4,
                        "representative_note_ids": [],
                    }
                )
            },
        ]

        synthesizer = ClusterMetadataSynthesizer(ollama_client, max_retries=1)
        cluster = ClusterData(
            cluster_id="cluster-1",
            representative_notes=["Note content"],
            representative_note_ids=[],
        )

        result = synthesizer.synthesize(cluster)

        assert result.status == "success"
        assert ollama_client.generate.call_count == 2

    def test_fails_after_retries(self, mocker):
        ollama_client = mocker.MagicMock()
        ollama_client.generate.return_value = {"response": "not-json"}

        synthesizer = ClusterMetadataSynthesizer(ollama_client, max_retries=1)
        cluster = ClusterData(
            cluster_id="cluster-1",
            representative_notes=["Note content"],
            representative_note_ids=[],
        )

        result = synthesizer.synthesize(cluster)

        assert result.status == "failed"
        assert result.profile is None
