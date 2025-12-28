"""Integration tests for quality analyzers.

Tests the complete quality analysis pipeline with real data.
"""

import numpy as np
import pytest

from mnemosyne.iris.chunking_quality import ChunkingQualityAnalyzer
from mnemosyne.iris.embedding_quality import EmbeddingQualityAnalyzer
from mnemosyne.iris.retrieval_evaluation import GroundTruthDataset, RetrievalEvaluator


@pytest.mark.integration
class TestQualityAnalyzersIntegration:
    """Integration tests for quality analyzers."""

    def test_embedding_quality_analysis_with_realistic_data(self):
        """Test embedding quality analyzer with realistic synthetic data."""
        # Generate realistic embedding vectors (384 dimensions like nomic-embed-text)
        n_samples = 100
        n_dimensions = 384

        # Create vectors with realistic properties
        vectors = np.random.randn(n_samples, n_dimensions)
        # Normalize to unit vectors (typical for embeddings)
        vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)

        # Analyze
        analyzer = EmbeddingQualityAnalyzer(vectors)
        metrics = analyzer.analyze()

        # Verify metrics are in expected ranges
        # Note: cosine similarity can be slightly negative due to numerical precision
        assert -0.1 <= metrics.avg_pairwise_similarity <= 1.0
        assert metrics.similarity_std >= 0.0
        assert 0.0 <= metrics.vector_space_coverage <= 1.0
        assert 0.0 <= metrics.dimensionality_usage <= 1.0
        assert isinstance(metrics.embedding_collapse_detected, bool)
        assert metrics.avg_vector_magnitude == pytest.approx(1.0, rel=0.01)  # Unit vectors

    def test_chunking_quality_analysis_with_realistic_data(self):
        """Test chunking quality analyzer with realistic synthetic data."""
        # Generate realistic chunks
        chunks = [
            "This is a chunk about machine learning. It discusses neural networks.",
            "This chunk covers data science topics. It includes statistics and probability.",
            "This is about software engineering. It covers testing and deployment.",
        ]

        # Generate corresponding vectors
        vectors = np.random.randn(len(chunks), 384)
        vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)

        # Analyze
        analyzer = ChunkingQualityAnalyzer(chunks, vectors)
        metrics = analyzer.analyze()

        # Verify metrics
        assert metrics.avg_chunk_size > 0
        assert metrics.min_chunk_size > 0
        assert metrics.max_chunk_size >= metrics.min_chunk_size
        # Note: cosine similarity can be slightly negative due to numerical precision
        assert -0.1 <= metrics.semantic_coherence <= 1.0
        assert 0.0 <= metrics.boundary_quality <= 1.0
        assert metrics.boundary_quality == 1.0  # All chunks end with punctuation

    def test_retrieval_evaluator_with_ground_truth(self, tmp_path):
        """Test retrieval evaluator with sample ground truth data."""
        # Create ground truth file
        import json

        gt_data = {
            "queries": [
                {
                    "id": "q001",
                    "query": "machine learning",
                    "relevant_docs": ["doc1.md", "doc2.md"],
                },
                {
                    "id": "q002",
                    "query": "data science",
                    "relevant_docs": ["doc3.md"],
                },
            ]
        }

        gt_file = tmp_path / "ground_truth.json"
        gt_file.write_text(json.dumps(gt_data))

        # Load dataset
        dataset = GroundTruthDataset(gt_file)
        assert len(dataset) == 2

        # Test retrieval metrics
        evaluator = RetrievalEvaluator()

        # Simulate retrieval results
        retrieved = ["doc1.md", "doc4.md", "doc2.md"]
        relevant = dataset.queries[0].relevant_docs

        # Compute metrics
        recall_5 = evaluator.recall_at_k(retrieved, relevant, k=5)
        ndcg_5 = evaluator.ndcg_at_k(retrieved, relevant, k=5)
        mrr = evaluator.reciprocal_rank(retrieved, relevant)

        # Verify metrics are computed
        assert 0.0 <= recall_5 <= 1.0
        assert 0.0 <= ndcg_5 <= 1.0
        assert 0.0 <= mrr <= 1.0
        assert recall_5 == 1.0  # Found both relevant docs
        assert mrr == 1.0  # First doc is relevant

    def test_complete_quality_pipeline(self):
        """Test complete quality analysis pipeline."""
        # Generate realistic test data
        n_chunks = 50
        chunks = [f"This is chunk {i}. It contains some text." for i in range(n_chunks)]
        vectors = np.random.randn(n_chunks, 384)
        vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)

        # Run embedding analysis
        embedding_analyzer = EmbeddingQualityAnalyzer(vectors)
        embedding_metrics = embedding_analyzer.analyze()

        # Run chunking analysis
        chunking_analyzer = ChunkingQualityAnalyzer(chunks, vectors)
        chunking_metrics = chunking_analyzer.analyze()

        # Verify both analyses completed successfully
        assert embedding_metrics.avg_pairwise_similarity is not None
        assert chunking_metrics.avg_chunk_size is not None

        # Verify metrics are related (same vectors)
        assert embedding_metrics.avg_vector_magnitude == pytest.approx(1.0, rel=0.01)
