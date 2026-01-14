"""
Semantic chunking using embedding cosine similarity between sentences.
"""

from __future__ import annotations

import logging
import math
import re

from mnemosyne.aletheia.text_chunker import TextChunk, TextChunker
from mnemosyne.providers.base import EmbeddingProvider

logger = logging.getLogger(__name__)


class SemanticCosineChunker:
    """
    Split text into chunks based on cosine similarity drops between sentences.
    """

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        fallback_chunker: TextChunker | None = None,
        similarity_threshold: float = 0.78,
        min_chunk_size: int = 100,
        max_chunk_size: int = 1000,
        embedding_model: str = "",
    ):
        self.embedding_provider = embedding_provider
        self.fallback_chunker = fallback_chunker or TextChunker()
        self.similarity_threshold = similarity_threshold
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.embedding_model = embedding_model

    def chunk(self, text: str, source_file: str, structure=None) -> list[TextChunk]:
        if not text or not text.strip():
            return []

        if len(text) <= self.min_chunk_size:
            return [TextChunk(text=text, index=0, source_file=source_file)]

        sentences = self._split_sentences(text)
        if len(sentences) <= 1:
            return [TextChunk(text=text.strip(), index=0, source_file=source_file)]

        try:
            vectors = [
                self.embedding_provider.embed(model=self.embedding_model, text=sentence["text"])
                for sentence in sentences
            ]
        except Exception as exc:
            logger.warning("Semantic-cosine embedding failed; falling back: %s", exc)
            return self.fallback_chunker.chunk(text, source_file)

        boundaries = self._compute_boundaries(sentences, vectors)
        return self._chunks_from_boundaries(text, source_file, boundaries)

    def _compute_boundaries(
        self, sentences: list[dict[str, int | str]], vectors: list[list[float]]
    ) -> list[int]:
        boundaries: list[int] = []
        current_start = int(sentences[0]["start"])
        prev_vector = vectors[0]

        for idx in range(1, len(sentences)):
            sentence = sentences[idx]
            similarity = self._cosine_similarity(prev_vector, vectors[idx])
            candidate_len = int(sentence["end"]) - current_start

            if candidate_len > self.max_chunk_size:
                boundaries.append(int(sentence["start"]))
                current_start = int(sentence["start"])
            elif candidate_len >= self.min_chunk_size and similarity < self.similarity_threshold:
                boundaries.append(int(sentence["start"]))
                current_start = int(sentence["start"])

            prev_vector = vectors[idx]

        return boundaries

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
                current += segment
            else:
                merged.append(current)
                current = segment
        if current:
            merged.append(current)

        chunks: list[TextChunk] = []
        index = 0
        for segment in merged:
            if len(segment) > self.max_chunk_size and self.fallback_chunker:
                fallback_chunks = self.fallback_chunker.chunk(segment, source_file)
                for fallback_chunk in fallback_chunks:
                    chunks.append(
                        TextChunk(
                            text=fallback_chunk.text,
                            index=index,
                            source_file=source_file,
                        )
                    )
                    index += 1
            else:
                chunks.append(TextChunk(text=segment, index=index, source_file=source_file))
                index += 1

        return chunks

    @staticmethod
    def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)

    @staticmethod
    def _split_sentences(text: str) -> list[dict[str, int | str]]:
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        results: list[dict[str, int | str]] = []
        cursor = 0
        for sentence in sentences:
            if not sentence.strip():
                continue
            start = text.find(sentence, cursor)
            if start == -1:
                continue
            end = start + len(sentence)
            results.append({"text": sentence, "start": start, "end": end})
            cursor = end
        return results
