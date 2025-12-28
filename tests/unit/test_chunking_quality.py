"""Unit tests for chunking quality analysis."""

import numpy as np
import pytest

from mnemosyne.iris.chunking_quality import ChunkingQualityAnalyzer


class TestChunkingQualityAnalyzer:
    """Test suite for ChunkingQualityAnalyzer."""

    def test_init_with_valid_data(self):
        """Test initialization with valid chunks and vectors."""
        chunks = ["This is chunk one.", "This is chunk two.", "This is chunk three."]
        vectors = np.random.randn(3, 384)

        analyzer = ChunkingQualityAnalyzer(chunks, vectors)

        assert analyzer.n_chunks == 3
        assert len(analyzer.chunks) == 3

    def test_init_with_mismatched_lengths(self):
        """Test that mismatched chunks/vectors raises ValueError."""
        chunks = ["chunk1", "chunk2"]
        vectors = np.random.randn(3, 384)  # 3 vectors for 2 chunks

        with pytest.raises(ValueError, match="Number of chunks"):
            ChunkingQualityAnalyzer(chunks, vectors)

    def test_compute_chunk_size_stats(self):
        """Test chunk size statistics computation."""
        # Create chunks with known sizes
        chunks = [
            "a" * 100,  # 100 chars
            "b" * 200,  # 200 chars
            "c" * 300,  # 300 chars
        ]
        vectors = np.random.randn(3, 384)

        analyzer = ChunkingQualityAnalyzer(chunks, vectors)
        avg_size, std_size, min_size, max_size = analyzer.compute_chunk_size_stats()

        assert avg_size == 200.0  # (100 + 200 + 300) / 3
        assert min_size == 100
        assert max_size == 300
        assert std_size == pytest.approx(81.65, rel=0.01)  # Standard deviation
