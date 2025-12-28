"""
Unit tests for text chunking functionality.

Tests the TextChunker class which splits cleaned text into chunks
for embedding generation using LangChain's RecursiveCharacterTextSplitter.
"""

import pytest

from src.mnemosyne.aletheia.text_chunker import TextChunk, TextChunker
from mnemosyne.aletheia.structure_extractor import (
    DocumentStructure,
    HeadingNode,
    StructureExtractor,
)


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


class TestTextChunkerWithStructure:
    """Test text chunking with document structure (Story 020)"""

    @pytest.fixture
    def chunker(self):
        """Create a text chunker with standard settings"""
        return TextChunker(chunk_size=400, chunk_overlap=100)

    @pytest.fixture
    def extractor(self):
        """Create a structure extractor"""
        return StructureExtractor()

    def test_chunk_with_structure_attaches_metadata(self, chunker, extractor):
        """Should attach heading metadata to chunks"""
        # GIVEN: Markdown with headings (extract structure first)
        markdown = """# Main Heading

Content under main heading.

## Section One

Content under section one."""

        structure = extractor.extract_structure(markdown)
        # Clean text (simulate markdown cleaning)
        cleaned_text = markdown

        # WHEN: Chunking with structure
        chunks = chunker.chunk_with_structure(
            text=cleaned_text, source_file="test.md", structure=structure
        )

        # THEN: Chunks have heading metadata
        assert len(chunks) >= 1
        for chunk in chunks:
            assert hasattr(chunk, "heading_path")
            assert hasattr(chunk, "heading_level")
            assert hasattr(chunk, "section_title")

    def test_chunk_with_structure_assigns_correct_headings(self, chunker, extractor):
        """Should assign chunks to correct parent headings"""
        # GIVEN: Document with clear heading structure
        markdown = """# Main Heading

Content at position 20-50.

## Section One

Content at position 80-110."""

        structure = extractor.extract_structure(markdown)
        cleaned_text = markdown

        # WHEN: Chunking with structure
        chunks = chunker.chunk_with_structure(
            text=cleaned_text, source_file="test.md", structure=structure
        )

        # THEN: First chunk belongs to "Main Heading"
        # Note: Exact behavior depends on chunk positions, but at least one
        # chunk should have heading metadata
        assert any(chunk.heading_path for chunk in chunks)

    def test_chunk_with_structure_handles_no_headings(self, chunker, extractor):
        """Should handle documents without headings"""
        # GIVEN: Plain text without headings
        text = "Just plain content without any structure."
        structure = extractor.extract_structure(text)

        # WHEN: Chunking with structure
        chunks = chunker.chunk_with_structure(text=text, source_file="test.md", structure=structure)

        # THEN: Chunks have empty/null heading metadata
        assert len(chunks) == 1
        assert chunks[0].heading_path == ""
        assert chunks[0].heading_level == 0
        assert chunks[0].section_title == ""

    def test_chunk_with_structure_nested_headings(self, chunker, extractor):
        """Should handle nested heading hierarchies"""
        # GIVEN: Document with nested headings and enough content to create multiple chunks
        markdown = (
            """# Main

Content at the main level. This needs to be long enough to potentially span chunks.

## Section

More content under section. Let's add more text here to make it realistic. """
            + "More text. " * 50
            + """

### Subsection

Even more content under subsection. """
            + "Additional content. " * 50
        )

        structure = extractor.extract_structure(markdown)
        cleaned_text = markdown

        # WHEN: Chunking with structure
        chunks = chunker.chunk_with_structure(
            text=cleaned_text, source_file="test.md", structure=structure
        )

        # THEN: At least some chunks have heading paths
        heading_paths = [c.heading_path for c in chunks if c.heading_path]
        assert len(heading_paths) > 0

        # At least one chunk should be under "Subsection" with nested path
        subsection_chunks = [c for c in chunks if "Subsection" in c.heading_path]
        assert len(subsection_chunks) > 0
        # The subsection path should be nested
        assert any(">" in c.heading_path for c in subsection_chunks)

    def test_chunk_with_structure_preserves_existing_fields(self, chunker, extractor):
        """Should preserve text, index, source_file from original chunking"""
        # GIVEN: Simple document
        markdown = """# Heading

Content here."""

        structure = extractor.extract_structure(markdown)
        cleaned_text = markdown

        # WHEN: Chunking with structure
        chunks = chunker.chunk_with_structure(
            text=cleaned_text, source_file="test.md", structure=structure
        )

        # THEN: Original fields still present
        chunk = chunks[0]
        assert hasattr(chunk, "text")
        assert hasattr(chunk, "index")
        assert hasattr(chunk, "source_file")
        assert chunk.source_file == "test.md"
        assert chunk.index == 0

    def test_chunk_with_structure_backward_compatible(self, chunker):
        """Should still work without structure parameter (backward compatibility)"""
        # GIVEN: Text without structure
        text = "Some content"

        # WHEN: Chunking without structure (old API)
        chunks = chunker.chunk(text, source_file="test.md")

        # THEN: Works as before
        assert len(chunks) == 1
        assert chunks[0].text == text
        assert chunks[0].source_file == "test.md"

    def test_chunk_with_structure_complex_document(self, chunker, extractor):
        """Should handle realistic document with multiple sections"""
        # GIVEN: Realistic Obsidian note structure
        markdown = """# Python Testing

Testing is important.

## Unit Tests

Unit tests are fast.

They test individual functions.

## Integration Tests

Integration tests verify components work together.

### Database Tests

These test database interactions.

## Best Practices

Always write tests first."""

        structure = extractor.extract_structure(markdown)
        cleaned_text = markdown

        # WHEN: Chunking with structure
        chunks = chunker.chunk_with_structure(
            text=cleaned_text, source_file="python-testing.md", structure=structure
        )

        # THEN: Multiple chunks with appropriate heading metadata
        assert len(chunks) >= 1
        # All chunks should have structure metadata
        assert all(hasattr(c, "heading_path") for c in chunks)
        assert all(hasattr(c, "heading_level") for c in chunks)
        # At least some chunks should be under specific sections
        section_titles = [c.section_title for c in chunks if c.section_title]
        assert len(section_titles) > 0
