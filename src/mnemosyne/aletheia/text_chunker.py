"""
Text chunker for splitting cleaned markdown into embedding-sized chunks.

Uses LangChain's RecursiveCharacterTextSplitter to split text at natural
boundaries (paragraphs, sentences, words) with configurable overlap.
"""

from dataclasses import dataclass, field
from typing import Optional

from langchain.text_splitter import RecursiveCharacterTextSplitter

from mnemosyne.aletheia.structure_extractor import DocumentStructure


@dataclass
class TextChunk:
    """
    A chunk of text ready for embedding.

    Attributes:
        text: The chunk content
        index: Position in the original document (0-indexed)
        source_file: Path to the original file
        heading_path: Full heading path (e.g., "# Main > ## Section > ### Subsection")
        heading_level: Heading level (0 = no heading, 1-6 = # to ######)
        section_title: Immediate parent heading title
    """

    text: str
    index: int
    source_file: str
    heading_path: str = ""
    heading_level: int = 0
    section_title: str = ""


class TextChunker:
    """
    Splits cleaned text into chunks for embedding generation.

    Uses recursive splitting strategy that tries to split at:
    1. Double newlines (paragraphs)
    2. Single newlines
    3. Sentences (periods)
    4. Spaces (words)
    5. Characters (last resort)

    This preserves semantic coherence better than naive character splitting.
    """

    def __init__(self, chunk_size: int = 400, chunk_overlap: int = 100):
        """
        Initialize text chunker.

        Args:
            chunk_size: Target size for each chunk in characters
            chunk_overlap: Number of characters to overlap between chunks
                          (helps preserve context across boundaries)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # Create LangChain splitter with semantic-aware separators
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=[
                "\n\n",  # Paragraphs (highest priority)
                "\n",  # Lines
                ". ",  # Sentences
                " ",  # Words
                "",  # Characters (fallback)
            ],
        )

    def chunk(self, text: str, source_file: str) -> list[TextChunk]:
        """
        Split text into chunks.

        Args:
            text: Cleaned text to chunk
            source_file: Path to source file (for tracking)

        Returns:
            List of TextChunk objects with sequential indices
        """
        # Handle empty or whitespace-only text
        if not text or not text.strip():
            return []

        # Split text using LangChain splitter
        raw_chunks = self.splitter.split_text(text)

        # Wrap in TextChunk dataclass with metadata
        chunks = [
            TextChunk(
                text=chunk_text,
                index=i,
                source_file=source_file,
            )
            for i, chunk_text in enumerate(raw_chunks)
        ]

        return chunks

    def chunk_with_structure(
        self, text: str, source_file: str, structure: DocumentStructure
    ) -> list[TextChunk]:
        """
        Split text into chunks with document structure metadata.

        Assigns each chunk to its parent heading based on character position
        in the original document.

        Args:
            text: Cleaned text to chunk
            source_file: Path to source file (for tracking)
            structure: Document structure extracted from original markdown

        Returns:
            List of TextChunk objects with heading metadata
        """
        # Handle empty or whitespace-only text
        if not text or not text.strip():
            return []

        # Split text using LangChain splitter with metadata
        # We need to track start positions for each chunk
        chunks_with_starts = self.splitter.create_documents([text])

        chunks = []
        for i, doc in enumerate(chunks_with_starts):
            chunk_text = doc.page_content

            # Find this chunk's start position in the original text
            # Use the actual content to find position
            if i == 0:
                chunk_start = text.find(chunk_text)
            else:
                # For subsequent chunks, search from after the previous chunk
                # accounting for overlap
                prev_chunk = chunks[i - 1]
                # Find first unique part of this chunk that wasn't in previous
                chunk_start = text.find(chunk_text[:50], chunks[i - 1]._start_pos + 1)
                if chunk_start == -1:
                    # Fallback: try finding anywhere
                    chunk_start = text.find(chunk_text)

            if chunk_start == -1:
                # Ultimate fallback: estimate based on previous position
                chunk_start = chunks[i - 1]._start_pos + len(chunks[i - 1].text) if i > 0 else 0

            # Find the heading at this position
            heading = structure.get_heading_at_pos(chunk_start)

            if heading and heading.level > 0:
                # Chunk is under a heading
                heading_path = structure.get_heading_path(heading)
                heading_level = heading.level
                section_title = heading.title
            else:
                # Chunk is not under any heading (root level)
                heading_path = ""
                heading_level = 0
                section_title = ""

            # Create chunk with heading metadata
            chunk = TextChunk(
                text=chunk_text,
                index=i,
                source_file=source_file,
                heading_path=heading_path,
                heading_level=heading_level,
                section_title=section_title,
            )
            # Store start position for next iteration (private attribute for tracking)
            chunk._start_pos = chunk_start
            chunks.append(chunk)

        return chunks
