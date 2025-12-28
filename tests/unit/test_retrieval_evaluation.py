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

    def test_file_not_found(self, tmp_path):
        """Test error when file doesn't exist."""
        nonexistent = tmp_path / "nonexistent.json"

        with pytest.raises(FileNotFoundError):
            GroundTruthDataset(nonexistent)

    def test_iteration(self, tmp_path):
        """Test iterating over queries."""
        gt_data = {
            "queries": [
                {"id": "q001", "query": "query1", "relevant_docs": ["doc1.md"]},
                {"id": "q002", "query": "query2", "relevant_docs": ["doc2.md"]},
            ]
        }

        gt_file = tmp_path / "ground_truth.json"
        gt_file.write_text(json.dumps(gt_data))

        dataset = GroundTruthDataset(gt_file)

        queries = list(dataset)
        assert len(queries) == 2
        assert all(isinstance(q, GroundTruthQuery) for q in queries)


class TestRetrievalEvaluator:
    """Test suite for RetrievalEvaluator."""

    @pytest.fixture
    def sample_ground_truth(self, tmp_path):
        """Create sample ground truth dataset."""
        gt_data = {
            "queries": [
                {
                    "id": "q001",
                    "query": "test query 1",
                    "relevant_docs": ["doc1.md", "doc2.md"],
                },
                {
                    "id": "q002",
                    "query": "test query 2",
                    "relevant_docs": ["doc3.md"],
                },
            ]
        }

        gt_file = tmp_path / "ground_truth.json"
        gt_file.write_text(json.dumps(gt_data))

        return GroundTruthDataset(gt_file)

    def test_recall_at_k_perfect(self, sample_ground_truth):
        """Test Recall@k with perfect retrieval."""
        evaluator = RetrievalEvaluator(sample_ground_truth)

        # Perfect retrieval: all relevant docs in top k
        retrieved = ["doc1.md", "doc2.md", "doc3.md", "doc4.md"]
        relevant = ["doc1.md", "doc2.md"]

        recall = evaluator.recall_at_k(retrieved, relevant, k=5)

        assert recall == 1.0  # Found 2/2 relevant docs

    def test_recall_at_k_partial(self, sample_ground_truth):
        """Test Recall@k with partial retrieval."""
        evaluator = RetrievalEvaluator(sample_ground_truth)

        # Partial retrieval: only 1 of 2 relevant docs in top k
        retrieved = ["doc1.md", "doc3.md", "doc4.md"]
        relevant = ["doc1.md", "doc2.md"]

        recall = evaluator.recall_at_k(retrieved, relevant, k=3)

        assert recall == 0.5  # Found 1/2 relevant docs

    def test_recall_at_k_zero(self, sample_ground_truth):
        """Test Recall@k with no relevant docs found."""
        evaluator = RetrievalEvaluator(sample_ground_truth)

        retrieved = ["doc3.md", "doc4.md", "doc5.md"]
        relevant = ["doc1.md", "doc2.md"]

        recall = evaluator.recall_at_k(retrieved, relevant, k=3)

        assert recall == 0.0

    def test_ndcg_at_k_perfect(self, sample_ground_truth):
        """Test NDCG@k with perfect ranking."""
        evaluator = RetrievalEvaluator(sample_ground_truth)

        # Perfect ranking: relevant docs at top
        retrieved = ["doc1.md", "doc2.md", "doc3.md", "doc4.md"]
        relevant = ["doc1.md", "doc2.md"]

        ndcg = evaluator.ndcg_at_k(retrieved, relevant, k=5)

        assert ndcg == 1.0  # Perfect NDCG

    def test_ndcg_at_k_imperfect(self, sample_ground_truth):
        """Test NDCG@k with imperfect ranking."""
        evaluator = RetrievalEvaluator(sample_ground_truth)

        # Relevant docs not at top
        retrieved = ["doc3.md", "doc1.md", "doc4.md", "doc2.md"]
        relevant = ["doc1.md", "doc2.md"]

        ndcg = evaluator.ndcg_at_k(retrieved, relevant, k=5)

        # NDCG should be < 1.0 (not perfect ranking)
        assert 0.0 < ndcg < 1.0

    def test_reciprocal_rank_first(self, sample_ground_truth):
        """Test MRR when first result is relevant."""
        evaluator = RetrievalEvaluator(sample_ground_truth)

        retrieved = ["doc1.md", "doc2.md", "doc3.md"]
        relevant = ["doc1.md"]

        rr = evaluator.reciprocal_rank(retrieved, relevant)

        assert rr == 1.0  # 1 / rank 1

    def test_reciprocal_rank_third(self, sample_ground_truth):
        """Test MRR when third result is relevant."""
        evaluator = RetrievalEvaluator(sample_ground_truth)

        retrieved = ["doc2.md", "doc3.md", "doc1.md"]
        relevant = ["doc1.md"]

        rr = evaluator.reciprocal_rank(retrieved, relevant)

        assert abs(rr - 1.0 / 3.0) < 0.001  # 1 / rank 3

    def test_reciprocal_rank_none(self, sample_ground_truth):
        """Test MRR when no relevant docs found."""
        evaluator = RetrievalEvaluator(sample_ground_truth)

        retrieved = ["doc2.md", "doc3.md", "doc4.md"]
        relevant = ["doc1.md"]

        rr = evaluator.reciprocal_rank(retrieved, relevant)

        assert rr == 0.0

    def test_evaluate_complete(self, sample_ground_truth):
        """Test full evaluation with mock retrieval function."""
        evaluator = RetrievalEvaluator(sample_ground_truth)

        # Mock retrieval function (always returns same results)
        def mock_retrieve(query: str):
            return ["doc1.md", "doc2.md", "doc3.md", "doc4.md", "doc5.md"]

        metrics = evaluator.evaluate(mock_retrieve, k_values=[5, 10])

        # Check all metrics are present
        assert hasattr(metrics, "recall_at_5")
        assert hasattr(metrics, "recall_at_10")
        assert hasattr(metrics, "ndcg_at_5")
        assert hasattr(metrics, "ndcg_at_10")
        assert hasattr(metrics, "mrr")
        assert metrics.num_queries == 2

        # All metrics should be in [0, 1]
        assert 0.0 <= metrics.recall_at_5 <= 1.0
        assert 0.0 <= metrics.ndcg_at_5 <= 1.0
        assert 0.0 <= metrics.mrr <= 1.0
