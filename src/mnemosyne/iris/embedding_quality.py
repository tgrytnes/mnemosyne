"""
Embedding quality analysis for Mnemosyne.

Provides metrics to evaluate embedding quality:
- Cosine similarity distributions (intra/inter-cluster)
- Vector space coverage and dimensionality usage
- Embedding collapse detection
- Nearest neighbor consistency
"""

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity


@dataclass
class EmbeddingQualityMetrics:
    """Container for embedding quality metrics."""

    avg_pairwise_similarity: float
    similarity_std: float
    vector_space_coverage: float
    dimensionality_usage: float
    embedding_collapse_detected: bool
    avg_vector_magnitude: float
    magnitude_std: float


class EmbeddingQualityAnalyzer:
    """
    Analyzes embedding quality from vector data.

    Computes metrics to assess whether embeddings are well-distributed,
    use the full vector space, and maintain semantic distinctions.
    """

    def __init__(self, vectors: np.ndarray, collapse_threshold: float = 0.95):
        """
        Initialize analyzer with embedding vectors.

        Args:
            vectors: Array of shape (n_samples, n_dimensions)
            collapse_threshold: Similarity threshold for collapse detection
        """
        if vectors.ndim != 2:
            raise ValueError(f"Expected 2D array, got shape {vectors.shape}")

        self.vectors = vectors
        self.collapse_threshold = collapse_threshold
        self.n_samples = vectors.shape[0]
        self.n_dimensions = vectors.shape[1]

    def compute_pairwise_similarity(
        self, sample_size: Optional[int] = 1000
    ) -> tuple[float, float]:
        """
        Compute average pairwise cosine similarity.

        For large datasets, samples randomly to avoid O(n²) complexity.

        Args:
            sample_size: Max number of vectors to sample

        Returns:
            (mean_similarity, std_similarity)
        """
        # Sample if dataset is large
        if self.n_samples > sample_size:
            indices = np.random.choice(self.n_samples, sample_size, replace=False)
            sample_vectors = self.vectors[indices]
        else:
            sample_vectors = self.vectors

        # Compute pairwise similarities
        similarities = cosine_similarity(sample_vectors)

        # Exclude diagonal (self-similarity = 1.0)
        mask = ~np.eye(similarities.shape[0], dtype=bool)
        off_diagonal = similarities[mask]

        return float(np.mean(off_diagonal)), float(np.std(off_diagonal))

    def compute_vector_space_coverage(self) -> float:
        """
        Measure how much of the vector space is being used.

        Returns percentage of dimensions with non-trivial variance.
        High coverage (>70%) indicates good use of embedding space.
        """
        # Compute variance per dimension
        variances = np.var(self.vectors, axis=0)

        # Count dimensions with non-trivial variance (>1e-6)
        active_dimensions = np.sum(variances > 1e-6)

        return float(active_dimensions / self.n_dimensions)

    def compute_dimensionality_usage(self) -> float:
        """
        Measure effective dimensionality using explained variance.

        Uses PCA-style analysis: what % of variance is explained by
        first k principal components?

        Returns: Percentage of variance explained by top 90% of components
        """
        # Center the data
        centered = self.vectors - np.mean(self.vectors, axis=0)

        # Compute covariance matrix (use SVD for numerical stability)
        # For large n_dimensions, use randomized SVD
        if self.n_dimensions > 500:
            from sklearn.decomposition import PCA

            pca = PCA(n_components=min(100, self.n_dimensions), svd_solver="randomized")
            pca.fit(centered)
            explained_variance_ratio = pca.explained_variance_ratio_
        else:
            # Full SVD for smaller dimensionality
            _, s, _ = np.linalg.svd(centered, full_matrices=False)
            explained_variance = (s**2) / (self.n_samples - 1)
            total_variance = np.sum(explained_variance)
            explained_variance_ratio = explained_variance / total_variance

        # How many components explain 90% of variance?
        cumsum = np.cumsum(explained_variance_ratio)
        n_components_90 = np.searchsorted(cumsum, 0.90) + 1

        # Return as percentage of total dimensions
        return float(n_components_90 / self.n_dimensions)

    def detect_embedding_collapse(self) -> bool:
        """
        Detect if embeddings have collapsed (all vectors too similar).

        Collapse occurs when:
        - Average pairwise similarity > threshold (default 0.95)
        - Vector space coverage < 10%

        Returns: True if collapse detected
        """
        avg_sim, _ = self.compute_pairwise_similarity()
        coverage = self.compute_vector_space_coverage()

        return avg_sim > self.collapse_threshold or coverage < 0.10

    def compute_vector_magnitudes(self) -> tuple[float, float]:
        """
        Compute average vector magnitude and standard deviation.

        Useful for detecting if embeddings are normalized or if
        magnitude varies significantly.

        Returns:
            (mean_magnitude, std_magnitude)
        """
        magnitudes = np.linalg.norm(self.vectors, axis=1)
        return float(np.mean(magnitudes)), float(np.std(magnitudes))

    def analyze(self) -> EmbeddingQualityMetrics:
        """
        Run full embedding quality analysis.

        Returns:
            EmbeddingQualityMetrics with all computed metrics
        """
        avg_sim, sim_std = self.compute_pairwise_similarity()
        coverage = self.compute_vector_space_coverage()
        dim_usage = self.compute_dimensionality_usage()
        collapse = self.detect_embedding_collapse()
        avg_mag, mag_std = self.compute_vector_magnitudes()

        return EmbeddingQualityMetrics(
            avg_pairwise_similarity=avg_sim,
            similarity_std=sim_std,
            vector_space_coverage=coverage,
            dimensionality_usage=dim_usage,
            embedding_collapse_detected=collapse,
            avg_vector_magnitude=avg_mag,
            magnitude_std=mag_std,
        )
