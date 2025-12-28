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
