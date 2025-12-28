"""Embedding quality analysis."""

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity


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

    def compute_pairwise_similarity(self) -> tuple[float, float]:
        """Compute pairwise cosine similarity statistics.

        Returns:
            tuple: (mean_similarity, std_similarity)
        """
        # Compute cosine similarity matrix
        sim_matrix = cosine_similarity(self.vectors)

        # Get upper triangle (excluding diagonal) to avoid counting same pairs twice
        triu_indices = np.triu_indices_from(sim_matrix, k=1)
        similarities = sim_matrix[triu_indices]

        mean_sim = float(np.mean(similarities))
        std_sim = float(np.std(similarities))

        return mean_sim, std_sim
