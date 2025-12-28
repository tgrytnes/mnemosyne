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
