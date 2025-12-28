"""Chunking quality analysis."""

from dataclasses import dataclass

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity


@dataclass
class ChunkingQualityMetrics:
    """Container for chunking quality metrics."""

    avg_chunk_size: float
    chunk_size_std: float
    min_chunk_size: int
    max_chunk_size: int
    semantic_coherence: float
    boundary_quality: float


class ChunkingQualityAnalyzer:
    """Analyzer for chunking quality metrics."""

    def __init__(self, chunks: list[str], vectors: np.ndarray):
        """Initialize analyzer with text chunks and their embeddings.

        Args:
            chunks: List of text chunks
            vectors: 2D numpy array of embeddings (n_chunks, n_dimensions)

        Raises:
            ValueError: If number of chunks doesn't match number of vectors
        """
        if len(chunks) != len(vectors):
            raise ValueError(
                f"Number of chunks ({len(chunks)}) must match number of vectors ({len(vectors)})"
            )

        self.chunks = chunks
        self.vectors = vectors
        self.n_chunks = len(chunks)

    def compute_chunk_size_stats(self) -> tuple[float, float, int, int]:
        """Compute chunk size statistics.

        Returns:
            tuple: (avg_size, std_size, min_size, max_size)
        """
        sizes = [len(chunk) for chunk in self.chunks]

        avg_size = float(np.mean(sizes))
        std_size = float(np.std(sizes))
        min_size = min(sizes)
        max_size = max(sizes)

        return avg_size, std_size, min_size, max_size

    def compute_semantic_coherence(self) -> float:
        """Compute semantic coherence (average pairwise cosine similarity).

        Returns:
            float: Average pairwise cosine similarity (0.0 to 1.0)
        """
        if self.n_chunks < 2:
            return 0.0

        # Compute pairwise cosine similarity matrix
        sim_matrix = cosine_similarity(self.vectors)

        # Get upper triangle (excluding diagonal)
        triu_indices = np.triu_indices_from(sim_matrix, k=1)
        similarities = sim_matrix[triu_indices]

        # Return average similarity
        return float(np.mean(similarities))
