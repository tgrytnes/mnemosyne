"""
Consensus chunking: keep boundaries where semantic and recursive agree.
"""

from __future__ import annotations

import logging

from mnemosyne.aletheia.semantic_chunker import SemanticChunker
from mnemosyne.aletheia.text_chunker import TextChunk, TextChunker

logger = logging.getLogger(__name__)


class SemanticConsensusChunker:
    """
    Run semantic + recursive chunking and keep overlapping boundaries.
    """

    def __init__(
        self,
        semantic_chunker: SemanticChunker,
        recursive_chunker: TextChunker,
        min_chunk_size: int = 100,
        max_chunk_size: int = 1000,
        boundary_tolerance: int = 20,
    ):
        self.semantic_chunker = semantic_chunker
        self.recursive_chunker = recursive_chunker
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.boundary_tolerance = boundary_tolerance

    def chunk(self, text: str, source_file: str, structure=None) -> list[TextChunk]:
        if not text or not text.strip():
            return []

        try:
            semantic_chunks = self.semantic_chunker.chunk(text, source_file, structure=structure)
        except Exception as exc:
            logger.warning("Semantic consensus failed; falling back: %s", exc)
            return self._recursive_chunks(text, source_file, structure)

        recursive_chunks = self._recursive_chunks(text, source_file, structure)

        if not semantic_chunks:
            return recursive_chunks
        if not recursive_chunks:
            return semantic_chunks

        semantic_boundaries = self._extract_boundaries(text, semantic_chunks)
        recursive_boundaries = self._extract_boundaries(text, recursive_chunks)
        consensus = self._consensus_boundaries(semantic_boundaries, recursive_boundaries)

        if not consensus:
            return semantic_chunks

        return self._chunks_from_boundaries(text, source_file, consensus)

    def _recursive_chunks(self, text: str, source_file: str, structure=None) -> list[TextChunk]:
        if structure is not None:
            return self.recursive_chunker.chunk_with_structure(text, source_file, structure)
        return self.recursive_chunker.chunk(text, source_file)

    def _extract_boundaries(self, text: str, chunks: list[TextChunk]) -> list[int]:
        boundaries: list[int] = []
        cursor = 0
        for idx, chunk in enumerate(chunks):
            start = text.find(chunk.text, cursor)
            if start == -1:
                start = text.find(chunk.text)
            if start == -1:
                start = cursor
            if idx > 0:
                boundaries.append(start)
            cursor = max(cursor, start + len(chunk.text))
        return boundaries

    def _consensus_boundaries(self, primary: list[int], secondary: list[int]) -> list[int]:
        result: list[int] = []
        for boundary in primary:
            if any(abs(boundary - other) <= self.boundary_tolerance for other in secondary):
                result.append(boundary)
        return sorted(set(result))

    def _chunks_from_boundaries(
        self, text: str, source_file: str, boundaries: list[int]
    ) -> list[TextChunk]:
        positions = [0] + sorted({b for b in boundaries if 0 < b < len(text)}) + [len(text)]
        segments = [text[start:end].strip() for start, end in zip(positions, positions[1:])]
        segments = [segment for segment in segments if segment]

        merged: list[str] = []
        current = ""
        for segment in segments:
            if not current:
                current = segment
                continue
            if len(current) < self.min_chunk_size or len(segment) < self.min_chunk_size:
                combined_len = len(current) + len(segment)
                if combined_len <= self.max_chunk_size:
                    current += segment
                else:
                    merged.append(current)
                    current = segment
            else:
                merged.append(current)
                current = segment

        if current:
            merged.append(current)

        chunks: list[TextChunk] = []
        index = 0
        for segment in merged:
            if len(segment) > self.max_chunk_size:
                fallback_chunks = self.recursive_chunker.chunk(segment, source_file)
                for fallback in fallback_chunks:
                    chunks.append(
                        TextChunk(text=fallback.text, index=index, source_file=source_file)
                    )
                    index += 1
            else:
                chunks.append(TextChunk(text=segment, index=index, source_file=source_file))
                index += 1

        return chunks
