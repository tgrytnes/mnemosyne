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


class TestRetrievalEvaluator:
    """Test suite for RetrievalEvaluator."""

    def test_recall_at_k_perfect(self):
        """Test recall@k with perfect retrieval."""
        evaluator = RetrievalEvaluator()

        # Perfect retrieval: all relevant docs in top k
        retrieved = ["doc1.md", "doc2.md", "doc3.md"]
        relevant = ["doc1.md", "doc2.md"]

        recall = evaluator.recall_at_k(retrieved, relevant, k=3)

        assert recall == 1.0  # Found 2/2 relevant docs
