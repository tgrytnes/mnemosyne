"""
Unit tests for hybrid chunking strategy.
"""

import pytest

from mnemosyne.aletheia.hybrid_chunker import HybridChunker
from mnemosyne.aletheia.structure_extractor import StructureExtractor
from mnemosyne.aletheia.text_chunker import TextChunk, TextChunker


class DummySemanticChunker:
    """Simple semantic chunker stub for testing."""

    def __init__(self):
        self.calls = []

    def chunk(self, text: str, source_file: str, structure=None):
        self.calls.append(text)
        return [TextChunk(text=text, index=0, source_file=source_file)]


class TestHybridChunker:
    """Test hybrid chunking behavior"""

    @pytest.fixture
    def extractor(self):
        return StructureExtractor()

    def test_attaches_heading_metadata(self, extractor):
        """Should attach heading metadata to all chunks"""
        markdown = """# Main

Intro text.

## Section One

Section content here."""

        structure = extractor.extract_structure(markdown)
        semantic = DummySemanticChunker()
        recursive = TextChunker(chunk_size=400, chunk_overlap=100)
        chunker = HybridChunker(
            semantic_chunker=semantic,
            recursive_chunker=recursive,
            section_semantic_min_length=0,
        )

        chunks = chunker.chunk(markdown, source_file="note.md", structure=structure)

        assert len(chunks) >= 1
        assert all(chunk.heading_path for chunk in chunks)
        assert any("Main" in chunk.heading_path for chunk in chunks)

    def test_small_sections_skip_semantic(self, extractor, mocker):
        """Should skip semantic chunking for short sections"""
        markdown = """# Main

Short content."""

        structure = extractor.extract_structure(markdown)
        semantic = mocker.MagicMock()
        recursive = TextChunker(chunk_size=400, chunk_overlap=100)

        chunker = HybridChunker(
            semantic_chunker=semantic,
            recursive_chunker=recursive,
            section_semantic_min_length=500,
        )

        chunks = chunker.chunk(markdown, source_file="note.md", structure=structure)

        assert len(chunks) == 1
        semantic.chunk.assert_not_called()

    def test_large_sections_use_semantic(self, extractor, mocker):
        """Should call semantic chunker for large sections"""
        markdown = "# Main\n\n" + ("Long content. " * 200)
        structure = extractor.extract_structure(markdown)

        semantic = mocker.MagicMock()
        semantic.chunk.return_value = [TextChunk(text="semantic", index=0, source_file="note.md")]
        recursive = TextChunker(chunk_size=400, chunk_overlap=100)

        chunker = HybridChunker(
            semantic_chunker=semantic,
            recursive_chunker=recursive,
            section_semantic_min_length=200,
        )

        chunks = chunker.chunk(markdown, source_file="note.md", structure=structure)

        assert len(chunks) == 1
        semantic.chunk.assert_called_once()
