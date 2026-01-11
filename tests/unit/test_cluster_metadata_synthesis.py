"""
Unit tests for cluster metadata synthesis.

NOTE: Unit tests appropriately use MOCKS to test isolated logic.
Integration/E2E tests use REAL Ollama and Weaviate.
"""

import json

from mnemosyne.argus.cluster_metadata_synthesis import (
    ClusterData,
    ClusterMetadataSynthesizer,
)


class TestClusterMetadataSynthesizer:
    """
    Test LLM-driven cluster profile synthesis logic.

    These unit tests use mocks to test:
    - JSON parsing logic
    - Retry behavior
    - Error handling
    - Schema validation

    For real LLM testing, see:
    - tests/integration/test_cluster_metadata_synthesis.py
    - tests/e2e/test_story_002_e2e.py
    """

    def test_synthesizes_profile_from_json(self, mocker):
        llm_provider = mocker.MagicMock()
        llm_provider.generate.return_value = {
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

        synthesizer = ClusterMetadataSynthesizer(llm_provider)
        cluster = ClusterData(
            cluster_id="cluster-1",
            representative_notes=["Note content"],
            representative_note_ids=["note-1"],
        )

        result = synthesizer.synthesize(cluster)

        assert result.status == "success"
        assert result.profile is not None
        assert "Project milestones and planning" in result.profile.theme_summary
        llm_provider.generate.assert_called_once()

    def test_retries_on_invalid_json(self, mocker):
        llm_provider = mocker.MagicMock()
        llm_provider.generate.side_effect = [
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

        synthesizer = ClusterMetadataSynthesizer(llm_provider, max_retries=1)
        cluster = ClusterData(
            cluster_id="cluster-1",
            representative_notes=["Note content"],
            representative_note_ids=[],
        )

        result = synthesizer.synthesize(cluster)

        assert result.status == "success"
        assert llm_provider.generate.call_count == 1

    def test_coerces_numeric_cluster_id(self, mocker):
        llm_provider = mocker.MagicMock()
        llm_provider.generate.return_value = {
            "response": json.dumps(
                {
                    "cluster_id": 91001,
                    "theme_summary": "Cluster summary",
                    "key_entities": ["entity"],
                    "dominant_topics": ["topic"],
                    "tags": ["tag"],
                    "confidence_score": 0.7,
                    "representative_note_ids": ["note-1"],
                }
            )
        }

        synthesizer = ClusterMetadataSynthesizer(llm_provider)
        cluster = ClusterData(
            cluster_id="91001",
            representative_notes=["Note content"],
            representative_note_ids=["note-1"],
        )

        result = synthesizer.synthesize(cluster)

        assert result.status == "success"
        assert result.profile is not None
        assert result.profile.cluster_id == "91001"

    def test_fails_after_retries(self, mocker):
        llm_provider = mocker.MagicMock()
        llm_provider.generate.side_effect = RuntimeError("LLM offline")

        synthesizer = ClusterMetadataSynthesizer(llm_provider, max_retries=1)
        cluster = ClusterData(
            cluster_id="cluster-1",
            representative_notes=["Note content"],
            representative_note_ids=[],
        )

        result = synthesizer.synthesize(cluster)

        assert result.status == "failed"
        assert result.profile is None
        assert llm_provider.generate.call_count == 2
