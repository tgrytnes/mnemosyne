"""Unit tests for chunking quality analysis."""

import numpy as np
import pytest

from mnemosyne.iris.chunking_quality import ChunkData, ChunkingQualityAnalyzer


class TestChunkingQualityAnalyzer:
    """Test suite for ChunkingQualityAnalyzer."""

    @pytest.fixture
    def sample_chunks(self):
        """Create sample chunks for testing."""
        return [
            ChunkData(
                text="This is a test chunk. It has some content.",
                chunk_id="chunk1",
                source_file="test.md",
                chunk_index=0,
                embedding=np.random.randn(384),
            ),
            ChunkData(
                text="Another chunk with different content.",
                chunk_id="chunk2",
                source_file="test.md",
                chunk_index=1,
                embedding=np.random.randn(384),
            ),
            ChunkData(
                text="Final chunk",
                chunk_id="chunk3",
                source_file="test.md",
                chunk_index=2,
                embedding=np.random.randn(384),
            ),
        ]

    def test_init_with_empty_chunks(self):
        """Test that empty chunk list raises ValueError."""
        with pytest.raises(ValueError, match="empty chunk list"):
            ChunkingQualityAnalyzer([])

    def test_compute_size_statistics(self, sample_chunks):
        """Test chunk size statistics computation."""
        analyzer = ChunkingQualityAnalyzer(sample_chunks)

        mean, std, min_size, max_size = analyzer.compute_size_statistics()

        # Check types
        assert isinstance(mean, float)
        assert isinstance(std, float)
        assert isinstance(min_size, int)
        assert isinstance(max_size, int)

        # Check bounds
        assert min_size <= mean <= max_size
        assert std >= 0.0

    def test_compute_boundary_quality_perfect(self):
        """Test boundary quality with all natural boundaries."""
        chunks = [
            ChunkData(
                text="Sentence ending with period.",
                chunk_id="c1",
                source_file="test.md",
                chunk_index=0,
            ),
            ChunkData(
                text="Another sentence!",
                chunk_id="c2",
                source_file="test.md",
                chunk_index=1,
            ),
            ChunkData(
                text="Question?",
                chunk_id="c3",
                source_file="test.md",
                chunk_index=2,
            ),
        ]

        analyzer = ChunkingQualityAnalyzer(chunks)
        boundary_quality = analyzer.compute_boundary_quality()

        assert boundary_quality == 1.0  # 100% natural boundaries

    def test_compute_boundary_quality_partial(self):
        """Test boundary quality with mixed boundaries."""
        chunks = [
            ChunkData(
                text="Good boundary.",
                chunk_id="c1",
                source_file="test.md",
                chunk_index=0,
            ),
            ChunkData(
                text="Bad bound",  # No punctuation
                chunk_id="c2",
                source_file="test.md",
                chunk_index=1,
            ),
            ChunkData(
                text="Another good one!",
                chunk_id="c3",
                source_file="test.md",
                chunk_index=2,
            ),
        ]

        analyzer = ChunkingQualityAnalyzer(chunks)
        boundary_quality = analyzer.compute_boundary_quality()

        assert abs(boundary_quality - 2.0 / 3.0) < 0.01  # ~67%

    def test_find_overlap_size(self):
        """Test overlap detection between texts."""
        chunks = [ChunkData("dummy", "c1", "test.md", 0)]
        analyzer = ChunkingQualityAnalyzer(chunks)

        # Exact overlap
        text1 = "Hello world, this is a test"
        text2 = "this is a test and more content"

        overlap = analyzer._find_overlap_size(text1, text2)

        assert overlap > 10  # Should find "this is a test"

    def test_find_overlap_size_no_overlap(self):
        """Test overlap detection with no overlap."""
        chunks = [ChunkData("dummy", "c1", "test.md", 0)]
        analyzer = ChunkingQualityAnalyzer(chunks)

        text1 = "Completely different"
        text2 = "No overlap here"

        overlap = analyzer._find_overlap_size(text1, text2)

        assert overlap == 0

    def test_compute_overlap_effectiveness(self):
        """Test overlap effectiveness computation."""
        chunks = [
            ChunkData(
                text="First chunk with some overlap content",
                chunk_id="c1",
                source_file="test.md",
                chunk_index=0,
            ),
            ChunkData(
                text="overlap content and new material",  # Overlaps with previous
                chunk_id="c2",
                source_file="test.md",
                chunk_index=1,
            ),
        ]

        analyzer = ChunkingQualityAnalyzer(chunks)
        overlap_eff = analyzer.compute_overlap_effectiveness()

        # Should detect some overlap
        assert overlap_eff is not None
        assert 0.0 <= overlap_eff <= 1.0

    def test_compute_semantic_coherence_with_embeddings(self, sample_chunks):
        """Test semantic coherence with embeddings."""
        analyzer = ChunkingQualityAnalyzer(sample_chunks)
        coherence = analyzer.compute_semantic_coherence()

        # Should compute coherence
        assert coherence is not None
        assert -1.0 <= coherence <= 1.0  # Cosine similarity range

    def test_compute_semantic_coherence_without_embeddings(self):
        """Test semantic coherence without embeddings."""
        chunks = [
            ChunkData(
                text="Test chunk",
                chunk_id="c1",
                source_file="test.md",
                chunk_index=0,
                embedding=None,  # No embedding
            ),
        ]

        analyzer = ChunkingQualityAnalyzer(chunks)
        coherence = analyzer.compute_semantic_coherence()

        assert coherence is None

    def test_analyze_returns_all_metrics(self, sample_chunks):
        """Test that analyze() returns complete metrics."""
        analyzer = ChunkingQualityAnalyzer(sample_chunks)
        metrics = analyzer.analyze()

        # Check all fields are present
        assert hasattr(metrics, "avg_chunk_size")
        assert hasattr(metrics, "chunk_size_std")
        assert hasattr(metrics, "min_chunk_size")
        assert hasattr(metrics, "max_chunk_size")
        assert hasattr(metrics, "semantic_coherence")
        assert hasattr(metrics, "boundary_quality")
        assert hasattr(metrics, "overlap_effectiveness")

        # Check types
        assert isinstance(metrics.avg_chunk_size, float)
        assert isinstance(metrics.boundary_quality, float)
