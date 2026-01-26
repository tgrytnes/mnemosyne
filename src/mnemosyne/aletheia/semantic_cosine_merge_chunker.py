"""
Merge semantic chunks using embedding similarity.
"""

from __future__ import annotations

import hashlib
import logging
import math

from mnemosyne.aletheia.semantic_chunker import SemanticChunker
from mnemosyne.aletheia.text_chunker import TextChunk, TextChunker
from mnemosyne.providers.base import EmbeddingProvider

logger = logging.getLogger(__name__)


class SemanticCosineMergeChunker:
    """
    Run semantic chunking, then merge adjacent chunks that are too similar.
    """

    def __init__(
        self,
        semantic_chunker: SemanticChunker,
        embedding_provider: EmbeddingProvider,
        similarity_threshold: float = 0.85,
        min_chunk_size: int = 100,
        max_chunk_size: int = 1000,
        embedding_model: str = "",
        max_embed_chars: int = 2000,
        fallback_chunker: TextChunker | None = None,
    ):
        self.semantic_chunker = semantic_chunker
        self.embedding_provider = embedding_provider
        self.similarity_threshold = similarity_threshold
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.embedding_model = embedding_model
        self.max_embed_chars = max_embed_chars
        self.fallback_chunker = fallback_chunker or TextChunker()
        self._embedding_cache: dict[str, list[float]] = {}

    def chunk(self, text: str, source_file: str, structure=None) -> list[TextChunk]:
        if not text or not text.strip():
            return []

        chunks = self.semantic_chunker.chunk(text, source_file, structure=structure)
        if len(chunks) <= 1:
            return chunks

        try:
            embeddings = [self._embed_text(chunk.text) for chunk in chunks]
        except Exception as exc:
            logger.warning("Semantic-cosine merge failed; falling back: %s", exc)
            return chunks

        merged: list[TextChunk] = []
        current_text = chunks[0].text
        current_index = 0

        for idx in range(1, len(chunks)):
            next_text = chunks[idx].text
            similarity = self._cosine_similarity(embeddings[idx - 1], embeddings[idx])
            combined_len = len(current_text) + len(next_text)

            should_merge = similarity >= self.similarity_threshold
            if len(current_text) < self.min_chunk_size or len(next_text) < self.min_chunk_size:
                should_merge = True

            if should_merge and combined_len <= self.max_chunk_size:
                current_text = f"{current_text}{next_text}"
                continue

            merged.append(
                TextChunk(text=current_text, index=current_index, source_file=source_file)
            )
            current_index += 1
            current_text = next_text

        if current_text:
            merged.append(
                TextChunk(text=current_text, index=current_index, source_file=source_file)
            )

        final_chunks: list[TextChunk] = []
        index = 0
        for chunk in merged:
            if len(chunk.text) > self.max_chunk_size and self.fallback_chunker:
                fallback_chunks = self.fallback_chunker.chunk(chunk.text, source_file)
                for fallback in fallback_chunks:
                    final_chunks.append(
                        TextChunk(text=fallback.text, index=index, source_file=source_file)
                    )
                    index += 1
            else:
                final_chunks.append(
                    TextChunk(text=chunk.text, index=index, source_file=source_file)
                )
                index += 1

        return final_chunks

    def _embed_text(self, text: str) -> list[float]:
        trimmed = text[: self.max_embed_chars]
        key = hashlib.sha256(trimmed.encode("utf-8")).hexdigest()
        if key in self._embedding_cache:
            return self._embedding_cache[key]
        vec = self.embedding_provider.embed(model=self.embedding_model, text=trimmed)
        self._embedding_cache[key] = vec
        return vec

    @staticmethod
    def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)
