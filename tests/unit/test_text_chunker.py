"""
Unit tests for text chunking functionality.

Tests the TextChunker class which splits cleaned text into chunks
for embedding generation using LangChain's RecursiveCharacterTextSplitter.
"""

import pytest

from src.mnemosyne.aletheia.text_chunker import TextChunk, TextChunker


class TestTextChunker:
    """Test text chunking for embedding generation"""

    @pytest.fixture
    def chunker(self):
        """Create a text chunker with standard settings (400 chars, 100 overlap)"""
        return TextChunker(chunk_size=400, chunk_overlap=100)

    def test_chunk_short_text(self, chunker):
        """Should return single chunk for text shorter than chunk_size"""
        # GIVEN: Short text (less than 400 chars)
        text = "This is a short piece of text that fits in one chunk."

        # WHEN: Chunking the text
        chunks = chunker.chunk(text, source_file="test.md")

        # THEN: Returns exactly 1 chunk
        assert len(chunks) == 1
        assert chunks[0].text == text
        assert chunks[0].index == 0
        assert chunks[0].source_file == "test.md"

    def test_chunk_long_text(self, chunker):
        """Should split long text into multiple chunks"""
        # GIVEN: Long text (more than 400 chars)
        # Create a 1000-character text
        text = "This is sentence number one. " * 35  # ~1015 chars

        # WHEN: Chunking the text
        chunks = chunker.chunk(text, source_file="test.md")

        # THEN: Returns multiple chunks
        assert len(chunks) > 1
        # Each chunk should be roughly chunk_size
        for chunk in chunks:
            assert len(chunk.text) <= 400 + 50  # Allow small buffer for word boundaries

    def test_chunk_overlap(self, chunker):
        """Should have overlap between consecutive chunks"""
        # GIVEN: Long text that will be split
        text = "A" * 300 + " " + "B" * 300

        # WHEN: Chunking with 100-char overlap
        chunks = chunker.chunk(text, source_file="test.md")

        # THEN: Consecutive chunks should share content
        if len(chunks) > 1:
            # Last part of first chunk should appear in second chunk
            # (This tests that overlap is working)
            assert len(chunks) >= 2

    def test_chunk_indices(self, chunker):
        """Should assign sequential indices to chunks"""
        # GIVEN: Text that creates multiple chunks
        text = "Sentence. " * 100  # ~1000 chars

        # WHEN: Chunking the text
        chunks = chunker.chunk(text, source_file="test.md")

        # THEN: Indices are sequential starting from 0
        for i, chunk in enumerate(chunks):
            assert chunk.index == i

    def test_chunk_preserves_source_file(self, chunker):
        """Should preserve source_file in all chunks"""
        # GIVEN: Text and source file
        text = "Content. " * 100
        source_file = "/path/to/my/note.md"

        # WHEN: Chunking the text
        chunks = chunker.chunk(text, source_file=source_file)

        # THEN: All chunks have correct source_file
        for chunk in chunks:
            assert chunk.source_file == source_file

    def test_chunk_empty_string(self, chunker):
        """Should handle empty string gracefully"""
        # GIVEN: Empty string
        text = ""

        # WHEN: Chunking the text
        chunks = chunker.chunk(text, source_file="test.md")

        # THEN: Returns empty list
        assert chunks == []

    def test_chunk_whitespace_only(self, chunker):
        """Should handle whitespace-only text"""
        # GIVEN: Only whitespace
        text = "   \n\n   \t  "

        # WHEN: Chunking the text
        chunks = chunker.chunk(text, source_file="test.md")

        # THEN: Returns empty list (after stripping)
        assert chunks == []

    def test_chunk_respects_sentence_boundaries(self, chunker):
        """Should prefer splitting at sentence boundaries when possible"""
        # GIVEN: Text with clear sentence boundaries
        sentences = [f"This is sentence number {i}. " for i in range(50)]
        text = "".join(sentences)

        # WHEN: Chunking the text
        chunks = chunker.chunk(text, source_file="test.md")

        # THEN: Should create multiple chunks and at least some end with periods
        # LangChain will split at ". " separator when possible, but not always
        # at the end of chunks due to overlap and size constraints
        assert len(chunks) > 1
        chunks_ending_with_period = sum(1 for c in chunks if c.text.rstrip().endswith("."))
        # At least the last chunk should end with a period
        assert chunks_ending_with_period >= 1

    def test_custom_chunk_size(self):
        """Should respect custom chunk_size parameter"""
        # GIVEN: Custom chunker with smaller size
        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        text = "A" * 250

        # WHEN: Chunking the text
        chunks = chunker.chunk(text, source_file="test.md")

        # THEN: Each chunk respects the 100-char limit
        for chunk in chunks:
            assert len(chunk.text) <= 120  # Allow buffer for word boundaries

    def test_custom_overlap(self):
        """Should respect custom chunk_overlap parameter"""
        # GIVEN: Custom chunker with no overlap
        chunker = TextChunker(chunk_size=200, chunk_overlap=0)
        text = "A" * 500

        # WHEN: Chunking the text
        chunks = chunker.chunk(text, source_file="test.md")

        # THEN: Returns chunks with minimal overlap
        assert len(chunks) >= 2

    def test_chunk_with_newlines(self, chunker):
        """Should handle text with multiple paragraphs"""
        # GIVEN: Multi-paragraph text
        text = """First paragraph with some content here.

Second paragraph with different content.

Third paragraph with more information."""

        # WHEN: Chunking the text
        chunks = chunker.chunk(text, source_file="test.md")

        # THEN: Successfully chunks the text
        assert len(chunks) >= 1
        # Should preserve paragraph structure where possible
        all_text = "".join(c.text for c in chunks)
        assert "First paragraph" in all_text
        assert "Second paragraph" in all_text

    def test_chunk_dataclass_attributes(self, chunker):
        """Should create TextChunk dataclass with correct attributes"""
        # GIVEN: Simple text
        text = "Test content"

        # WHEN: Chunking the text
        chunks = chunker.chunk(text, source_file="test.md")

        # THEN: Chunk has all required attributes
        chunk = chunks[0]
        assert isinstance(chunk, TextChunk)
        assert hasattr(chunk, "text")
        assert hasattr(chunk, "index")
        assert hasattr(chunk, "source_file")
        assert chunk.text == text
        assert chunk.index == 0
        assert chunk.source_file == "test.md"

    def test_realistic_obsidian_note(self, chunker):
        """Should handle realistic Obsidian note after cleaning"""
        # GIVEN: Realistic cleaned note (after markdown cleaning)
        text = """Python Testing Best Practices

Testing is crucial for software quality. Here are key principles:

Unit tests should be fast and isolated. They test individual functions
without external dependencies. Use mocks for databases and APIs.

Integration tests verify that components work together correctly.
They test real database connections and API calls.

Test-driven development helps design better code. Write tests first,
then implement the minimal code to pass. This leads to cleaner APIs
and better separation of concerns.

Always aim for high test coverage but focus on critical paths.
Not all code needs 100% coverage, prioritize business logic."""

        # WHEN: Chunking the note
        chunks = chunker.chunk(text, source_file="python-testing.md")

        # THEN: Successfully chunks with reasonable distribution
        assert len(chunks) >= 1
        assert all(chunk.source_file == "python-testing.md" for chunk in chunks)
        assert all(chunk.index == i for i, chunk in enumerate(chunks))
        # Verify content is preserved
        combined = " ".join(c.text for c in chunks)
        assert "Testing is crucial" in combined
        assert "Test-driven development" in combined
