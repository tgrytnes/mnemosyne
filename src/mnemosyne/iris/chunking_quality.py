"""
Chunking quality analysis for Mnemosyne.

Provides metrics to evaluate text chunking quality:
- Chunk size distribution and statistics
- Semantic coherence within chunks
- Boundary quality (splits at natural boundaries?)
- Overlap effectiveness
"""

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity


@dataclass
class ChunkData:
    """Single chunk with text and optional embedding."""

    text: str
    chunk_id: str
    source_file: str
    chunk_index: int
    embedding: Optional[np.ndarray] = None


@dataclass
class ChunkingQualityMetrics:
    """Container for chunking quality metrics."""

    avg_chunk_size: float
    chunk_size_std: float
    min_chunk_size: int
    max_chunk_size: int
    semantic_coherence: Optional[float]  # Requires embeddings
    boundary_quality: float  # % of chunks ending at sentence boundaries
    overlap_effectiveness: Optional[float]  # Requires adjacent chunk analysis


class ChunkingQualityAnalyzer:
    """
    Analyzes chunking quality from chunk data.

    Evaluates whether chunks:
    - Have appropriate sizes
    - Maintain semantic coherence
    - Split at natural boundaries
    - Preserve context through overlap
    """

    def __init__(self, chunks: List[ChunkData]):
        """
        Initialize analyzer with chunk data.

        Args:
            chunks: List of ChunkData objects
        """
        if not chunks:
            raise ValueError("Cannot analyze empty chunk list")

        self.chunks = chunks
        self.n_chunks = len(chunks)

    def compute_size_statistics(self) -> tuple[float, float, int, int]:
        """
        Compute chunk size statistics.

        Returns:
            (mean_size, std_size, min_size, max_size)
        """
        sizes = [len(chunk.text) for chunk in self.chunks]

        return (
            float(np.mean(sizes)),
            float(np.std(sizes)),
            int(np.min(sizes)),
            int(np.max(sizes)),
        )

    def compute_semantic_coherence(self) -> Optional[float]:
        """
        Compute average semantic coherence within chunks.

        For chunks with multiple sentences, measures if sentences
        within a chunk are semantically similar (coherent topic).

        Requires: Chunks must have embeddings

        Returns:
            Average intra-chunk similarity, or None if embeddings unavailable
        """
        # Check if embeddings are available
        if not all(chunk.embedding is not None for chunk in self.chunks):
            return None

        # For each chunk, split into sentences and compute intra-chunk similarity
        # This is a simplified version - ideally would embed each sentence separately
        # For now, we approximate by comparing adjacent chunks (assumed to overlap)

        coherence_scores = []

        # Group chunks by source file
        from collections import defaultdict

        file_chunks = defaultdict(list)
        for chunk in self.chunks:
            file_chunks[chunk.source_file].append(chunk)

        # For each file, compute coherence of adjacent chunks
        for source_file, file_chunk_list in file_chunks.items():
            # Sort by chunk index
            sorted_chunks = sorted(file_chunk_list, key=lambda c: c.chunk_index)

            # Compare adjacent chunks
            for i in range(len(sorted_chunks) - 1):
                emb1 = sorted_chunks[i].embedding
                emb2 = sorted_chunks[i + 1].embedding

                if emb1 is not None and emb2 is not None:
                    # Cosine similarity between adjacent chunks
                    sim = cosine_similarity(emb1.reshape(1, -1), emb2.reshape(1, -1))[
                        0, 0
                    ]
                    coherence_scores.append(sim)

        if not coherence_scores:
            return None

        return float(np.mean(coherence_scores))

    def compute_boundary_quality(self) -> float:
        """
        Compute percentage of chunks ending at natural boundaries.

        Natural boundaries:
        - Sentence endings (. ! ?)
        - Paragraph breaks (\\n\\n)
        - Section endings

        Returns:
            Percentage (0.0 to 1.0) of chunks with natural boundaries
        """
        natural_boundary_count = 0

        for chunk in self.chunks:
            text = chunk.text.rstrip()

            # Check if ends with sentence punctuation
            if text.endswith((".", "!", "?", "\n\n")):
                natural_boundary_count += 1
            # Check if ends with paragraph break
            elif text.endswith("\n"):
                natural_boundary_count += 1

        return natural_boundary_count / self.n_chunks

    def compute_overlap_effectiveness(self) -> Optional[float]:
        """
        Measure how well overlap preserves context.

        For chunks with overlap, checks if overlapping content
        appears in both chunks.

        This is a proxy metric - ideal implementation would verify
        that important context (entities, key terms) appears in overlap.

        Returns:
            Average overlap ratio, or None if not applicable
        """
        # Group chunks by source file
        from collections import defaultdict

        file_chunks = defaultdict(list)
        for chunk in self.chunks:
            file_chunks[chunk.source_file].append(chunk)

        overlap_ratios = []

        for source_file, file_chunk_list in file_chunks.items():
            # Sort by chunk index
            sorted_chunks = sorted(file_chunk_list, key=lambda c: c.chunk_index)

            # Find overlap between adjacent chunks
            for i in range(len(sorted_chunks) - 1):
                chunk1 = sorted_chunks[i].text
                chunk2 = sorted_chunks[i + 1].text

                # Simple heuristic: find longest common substring at boundaries
                overlap_size = self._find_overlap_size(chunk1, chunk2)

                if overlap_size > 0:
                    # Overlap ratio relative to smaller chunk
                    min_chunk_size = min(len(chunk1), len(chunk2))
                    overlap_ratios.append(overlap_size / min_chunk_size)

        if not overlap_ratios:
            return None

        return float(np.mean(overlap_ratios))

    def _find_overlap_size(self, text1: str, text2: str, min_overlap: int = 10) -> int:
        """
        Find size of overlap between end of text1 and start of text2.

        Args:
            text1: First text
            text2: Second text
            min_overlap: Minimum overlap size to consider

        Returns:
            Size of overlap in characters
        """
        max_possible_overlap = min(len(text1), len(text2))

        # Try decreasing overlap sizes
        for overlap_size in range(max_possible_overlap, min_overlap - 1, -1):
            if text1[-overlap_size:] == text2[:overlap_size]:
                return overlap_size

        return 0

    def analyze(self) -> ChunkingQualityMetrics:
        """
        Run full chunking quality analysis.

        Returns:
            ChunkingQualityMetrics with all computed metrics
        """
        avg_size, size_std, min_size, max_size = self.compute_size_statistics()
        coherence = self.compute_semantic_coherence()
        boundary_quality = self.compute_boundary_quality()
        overlap_eff = self.compute_overlap_effectiveness()

        return ChunkingQualityMetrics(
            avg_chunk_size=avg_size,
            chunk_size_std=size_std,
            min_chunk_size=min_size,
            max_chunk_size=max_size,
            semantic_coherence=coherence,
            boundary_quality=boundary_quality,
            overlap_effectiveness=overlap_eff,
        )
