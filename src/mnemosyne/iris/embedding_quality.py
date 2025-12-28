"""Embedding quality analysis."""

import numpy as np
from sklearn.decomposition import PCA
from sklearn.metrics.pairwise import cosine_similarity


class EmbeddingQualityAnalyzer:
    """Analyzer for embedding quality metrics."""

    def __init__(self, vectors: np.ndarray, collapse_threshold: float = 0.95):
        """Initialize analyzer with embedding vectors.

        Args:
            vectors: 2D numpy array of shape (n_samples, n_dimensions)
            collapse_threshold: Threshold for detecting embedding collapse (default: 0.95)

        Raises:
            ValueError: If vectors is not a 2D array
        """
        if vectors.ndim != 2:
            raise ValueError(f"Expected 2D array, got shape {vectors.shape}")
        self.vectors = vectors
        self.n_samples = vectors.shape[0]
        self.n_dimensions = vectors.shape[1]
        self.collapse_threshold = collapse_threshold

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

    def compute_vector_space_coverage(self, threshold: float = 0.01) -> float:
        """Compute what percentage of vector space dimensions are used.

        Args:
            threshold: Minimum variance for a dimension to be considered "used"

        Returns:
            float: Fraction of dimensions with variance > threshold (0.0 to 1.0)
        """
        # Compute variance for each dimension across all vectors
        variance_per_dim = np.var(self.vectors, axis=0)

        # Count dimensions with meaningful variance
        used_dims = np.sum(variance_per_dim > threshold)

        # Return fraction of dimensions used
        coverage = float(used_dims) / self.n_dimensions

        return coverage

    def detect_embedding_collapse(self) -> bool:
        """Detect if embeddings have collapsed (all vectors too similar).

        Returns:
            bool: True if average pairwise similarity exceeds collapse_threshold
        """
        mean_sim, _ = self.compute_pairwise_similarity()
        return mean_sim > self.collapse_threshold

    def compute_dimensionality_usage(self, variance_threshold: float = 0.95) -> float:
        """Compute effective dimensionality using PCA.

        Args:
            variance_threshold: Cumulative variance to capture (default: 0.95)

        Returns:
            float: Fraction of dimensions needed to capture variance_threshold of variance
        """
        # Use PCA to find how many dimensions capture most variance
        pca = PCA(n_components=variance_threshold, svd_solver="full")
        pca.fit(self.vectors)

        # Return fraction of dimensions used
        n_components_used = pca.n_components_
        dim_usage = float(n_components_used) / self.n_dimensions

        return dim_usage

    def compute_vector_magnitudes(self) -> tuple[float, float]:
        """Compute statistics of vector magnitudes.

        Returns:
            tuple: (mean_magnitude, std_magnitude)
        """
        # Compute L2 norm for each vector
        magnitudes = np.linalg.norm(self.vectors, axis=1)

        mean_mag = float(np.mean(magnitudes))
        std_mag = float(np.std(magnitudes))

        return mean_mag, std_mag
