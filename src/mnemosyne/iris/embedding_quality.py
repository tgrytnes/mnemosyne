"""Embedding quality analysis."""

import numpy as np


class EmbeddingQualityAnalyzer:
    """Analyzer for embedding quality metrics."""

    def __init__(self, vectors: np.ndarray):
        """Initialize analyzer with embedding vectors.

        Args:
            vectors: 2D numpy array of shape (n_samples, n_dimensions)

        Raises:
            ValueError: If vectors is not a 2D array
        """
        if vectors.ndim != 2:
            raise ValueError(f"Expected 2D array, got shape {vectors.shape}")
        self.vectors = vectors
        self.n_samples = vectors.shape[0]
        self.n_dimensions = vectors.shape[1]
