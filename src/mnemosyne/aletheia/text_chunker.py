"""
Text chunker for splitting cleaned markdown into embedding-sized chunks.

Uses LangChain's RecursiveCharacterTextSplitter to split text at natural
boundaries (paragraphs, sentences, words) with configurable overlap.
"""

from dataclasses import dataclass

from langchain.text_splitter import RecursiveCharacterTextSplitter


@dataclass
class TextChunk:
    """
    A chunk of text ready for embedding.

    Attributes:
        text: The chunk content
        index: Position in the original document (0-indexed)
        source_file: Path to the original file
    """

    text: str
    index: int
    source_file: str


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
