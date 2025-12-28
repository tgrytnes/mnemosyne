"""Unit tests for embedding quality analysis."""

import numpy as np
import pytest

from mnemosyne.iris.embedding_quality import EmbeddingQualityAnalyzer


class TestEmbeddingQualityAnalyzer:
    """Test suite for EmbeddingQualityAnalyzer."""

    def test_init_with_valid_vectors(self):
        """Test initialization with valid 2D array."""
        vectors = np.random.randn(100, 384)
        analyzer = EmbeddingQualityAnalyzer(vectors)

        assert analyzer.n_samples == 100
        assert analyzer.n_dimensions == 384

    def test_init_with_invalid_shape(self):
        """Test that 1D array raises ValueError."""
        vectors = np.random.randn(100)  # 1D array

        with pytest.raises(ValueError, match="Expected 2D array"):
            EmbeddingQualityAnalyzer(vectors)

    def test_compute_pairwise_similarity(self):
        """Test pairwise similarity computation."""
        # Create known vectors
        vectors = np.array(
            [
                [1.0, 0.0, 0.0],
                [0.9, 0.1, 0.0],  # Very similar to first
                [0.0, 1.0, 0.0],  # Orthogonal to first
            ]
        )

        analyzer = EmbeddingQualityAnalyzer(vectors)
        mean_sim, std_sim = analyzer.compute_pairwise_similarity()

        # Mean should be moderate (mix of similar and dissimilar)
        assert 0.0 <= mean_sim <= 1.0
        assert std_sim >= 0.0

    def test_compute_vector_space_coverage_full(self):
        """Test coverage with vectors using all dimensions."""
        # Vectors with variance in all dimensions
        vectors = np.random.randn(100, 50)

        analyzer = EmbeddingQualityAnalyzer(vectors)
        coverage = analyzer.compute_vector_space_coverage()

        # Should use most dimensions (>90%)
        assert coverage > 0.9

    def test_compute_vector_space_coverage_partial(self):
        """Test coverage with vectors using only some dimensions."""
        # Vectors that only use first 10 of 50 dimensions
        vectors = np.zeros((100, 50))
        vectors[:, :10] = np.random.randn(100, 10)

        analyzer = EmbeddingQualityAnalyzer(vectors)
        coverage = analyzer.compute_vector_space_coverage()

        # Should detect low coverage (~20%)
        assert coverage < 0.3

    def test_detect_embedding_collapse_positive(self):
        """Test collapse detection with collapsed embeddings."""
        # All vectors nearly identical (collapsed)
        base_vector = np.random.randn(384)
        vectors = np.tile(base_vector, (100, 1))
        vectors += np.random.randn(100, 384) * 0.01  # Tiny noise

        analyzer = EmbeddingQualityAnalyzer(vectors, collapse_threshold=0.95)
        collapsed = analyzer.detect_embedding_collapse()

        assert collapsed is True

    def test_detect_embedding_collapse_negative(self):
        """Test collapse detection with healthy embeddings."""
        # Well-distributed random vectors
        vectors = np.random.randn(100, 384)

        analyzer = EmbeddingQualityAnalyzer(vectors, collapse_threshold=0.95)
        collapsed = analyzer.detect_embedding_collapse()

        assert collapsed is False

    def test_dimensionality_usage(self):
        """Test dimensionality usage computation."""
        # Create vectors with known structure
        vectors = np.random.randn(100, 100)

        analyzer = EmbeddingQualityAnalyzer(vectors)
        dim_usage = analyzer.compute_dimensionality_usage()

        # Should be between 0 and 1
        assert 0.0 <= dim_usage <= 1.0

    def test_compute_vector_magnitudes(self):
        """Test vector magnitude computation."""
        # Unit vectors (magnitude = 1.0)
        vectors = np.random.randn(100, 384)
        vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)

        analyzer = EmbeddingQualityAnalyzer(vectors)
        mean_mag, std_mag = analyzer.compute_vector_magnitudes()

        # Should be close to 1.0 with low variance
        assert abs(mean_mag - 1.0) < 0.01
        assert std_mag < 0.01

    def test_analyze_returns_all_metrics(self):
        """Test that analyze() returns complete metrics."""
        vectors = np.random.randn(100, 384)
        analyzer = EmbeddingQualityAnalyzer(vectors)

        metrics = analyzer.analyze()

        # Check all fields are present
        assert hasattr(metrics, "avg_pairwise_similarity")
        assert hasattr(metrics, "similarity_std")
        assert hasattr(metrics, "vector_space_coverage")
        assert hasattr(metrics, "dimensionality_usage")
        assert hasattr(metrics, "embedding_collapse_detected")
        assert hasattr(metrics, "avg_vector_magnitude")
        assert hasattr(metrics, "magnitude_std")

        # Check types
        assert isinstance(metrics.avg_pairwise_similarity, float)
        assert isinstance(metrics.embedding_collapse_detected, bool)
