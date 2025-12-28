"""Chunking quality analysis."""

from dataclasses import dataclass

import numpy as np


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
