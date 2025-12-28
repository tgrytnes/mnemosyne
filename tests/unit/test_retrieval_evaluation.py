"""Unit tests for retrieval evaluation."""

import json
from pathlib import Path

import pytest

from mnemosyne.iris.retrieval_evaluation import (
    GroundTruthDataset,
    GroundTruthQuery,
    RetrievalEvaluator,
)


class TestGroundTruthDataset:
    """Test suite for GroundTruthDataset."""

    def test_load_from_file(self, tmp_path):
        """Test loading ground truth from JSON file."""
        # Create sample JSON
        gt_data = {
            "queries": [
                {
                    "id": "q001",
                    "query": "test query",
                    "relevant_docs": ["doc1.md", "doc2.md"],
                }
            ]
        }

        gt_file = tmp_path / "ground_truth.json"
        gt_file.write_text(json.dumps(gt_data))

        # Load dataset
        dataset = GroundTruthDataset(gt_file)

        assert len(dataset) == 1
        assert dataset.queries[0].query_id == "q001"
        assert dataset.queries[0].query == "test query"
        assert len(dataset.queries[0].relevant_docs) == 2
