"""Unit tests for retrieval evaluation."""

import json

import pytest

from mnemosyne.iris.retrieval_evaluation import (
    GroundTruthDataset,
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

    def test_recall_at_k_partial(self):
        """Test recall@k with partial retrieval."""
        evaluator = RetrievalEvaluator()

        # Partial retrieval: only 1 of 3 relevant docs in top 2
        retrieved = ["doc1.md", "doc4.md", "doc2.md", "doc3.md"]
        relevant = ["doc1.md", "doc2.md", "doc3.md"]

        recall = evaluator.recall_at_k(retrieved, relevant, k=2)

        assert recall == pytest.approx(1 / 3)  # Found 1/3 relevant docs

    def test_recall_at_k_zero(self):
        """Test recall@k with no relevant docs found."""
        evaluator = RetrievalEvaluator()

        # No relevant docs in top k
        retrieved = ["doc4.md", "doc5.md", "doc1.md"]
        relevant = ["doc1.md", "doc2.md"]

        recall = evaluator.recall_at_k(retrieved, relevant, k=2)

        assert recall == 0.0  # Found 0/2 relevant docs

    def test_recall_at_k_empty_relevant(self):
        """Test recall@k with empty relevant docs."""
        evaluator = RetrievalEvaluator()

        retrieved = ["doc1.md", "doc2.md"]
        relevant = []

        recall = evaluator.recall_at_k(retrieved, relevant, k=2)

        assert recall == 0.0

    def test_ndcg_at_k_perfect(self):
        """Test NDCG@k with perfect ranking."""
        evaluator = RetrievalEvaluator()

        # Perfect ranking: all relevant docs at top in order
        retrieved = ["doc1.md", "doc2.md", "doc3.md", "doc4.md"]
        relevant = ["doc1.md", "doc2.md", "doc3.md"]

        ndcg = evaluator.ndcg_at_k(retrieved, relevant, k=4)

        assert ndcg == 1.0  # Perfect ranking

    def test_ndcg_at_k_worst(self):
        """Test NDCG@k with worst ranking."""
        evaluator = RetrievalEvaluator()

        # Worst ranking: all relevant docs at bottom
        retrieved = ["doc4.md", "doc5.md", "doc1.md", "doc2.md"]
        relevant = ["doc1.md", "doc2.md"]

        ndcg = evaluator.ndcg_at_k(retrieved, relevant, k=2)

        assert ndcg == 0.0  # No relevant docs in top k

    def test_ndcg_at_k_partial(self):
        """Test NDCG@k with partial ranking."""
        evaluator = RetrievalEvaluator()

        # Mixed ranking: some relevant docs in top k but not ideal order
        retrieved = ["doc1.md", "doc4.md", "doc2.md"]
        relevant = ["doc1.md", "doc2.md"]

        ndcg = evaluator.ndcg_at_k(retrieved, relevant, k=3)

        # NDCG should be between 0 and 1
        assert 0.0 < ndcg < 1.0

    def test_reciprocal_rank_first_position(self):
        """Test MRR when first relevant doc is at position 1."""
        evaluator = RetrievalEvaluator()

        # First relevant doc is first in results
        retrieved = ["doc1.md", "doc2.md", "doc3.md"]
        relevant = ["doc1.md"]

        rr = evaluator.reciprocal_rank(retrieved, relevant)

        assert rr == 1.0  # 1/1 = 1.0

    def test_reciprocal_rank_third_position(self):
        """Test MRR when first relevant doc is at position 3."""
        evaluator = RetrievalEvaluator()

        # First relevant doc is at position 3
        retrieved = ["doc4.md", "doc5.md", "doc1.md", "doc2.md"]
        relevant = ["doc1.md", "doc2.md"]

        rr = evaluator.reciprocal_rank(retrieved, relevant)

        assert rr == pytest.approx(1 / 3)  # 1/3 ≈ 0.333

    def test_reciprocal_rank_no_relevant_found(self):
        """Test MRR when no relevant docs are found."""
        evaluator = RetrievalEvaluator()

        # No relevant docs in results
        retrieved = ["doc4.md", "doc5.md"]
        relevant = ["doc1.md", "doc2.md"]

        rr = evaluator.reciprocal_rank(retrieved, relevant)

        assert rr == 0.0
