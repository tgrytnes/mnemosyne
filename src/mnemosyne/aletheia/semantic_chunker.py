"""
Semantic chunking using LLM boundary detection.
"""

import hashlib
import json
import logging

from mnemosyne.aletheia.ingestion_state import IngestionStateTracker
from mnemosyne.aletheia.text_chunker import TextChunk, TextChunker

logger = logging.getLogger(__name__)


class SemanticChunker:
    """
    Split text into chunks using LLM-detected topic boundaries.
    """

    def __init__(
        self,
        ollama_client,
        state_tracker: IngestionStateTracker | None = None,
        fallback_chunker: TextChunker | None = None,
        min_chunk_size: int = 100,
        max_chunk_size: int = 1000,
        model: str = "qwen3:0.6b",
        temperature: float = 0.2,
        request_timeout: float = 5.0,
        total_timeout: float = 30.0,
    ):
        self.ollama_client = ollama_client
        self.state_tracker = state_tracker
        self.fallback_chunker = fallback_chunker or TextChunker()
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.model = model
        self.temperature = temperature
        self.request_timeout = request_timeout
        self.total_timeout = total_timeout

    def chunk(self, text: str, source_file: str, structure=None) -> list[TextChunk]:
        """
        Chunk text using LLM boundaries with fallback to recursive splitting.
        """
        if not text or not text.strip():
            return []

        if len(text) <= self.min_chunk_size:
            return [TextChunk(text=text, index=0, source_file=source_file)]

        cache_key = self._cache_key(text)
        boundaries = self._get_cached_boundaries(cache_key)

        if boundaries is None:
            try:
                boundaries = self._identify_boundaries(text)
                self._cache_boundaries(cache_key, boundaries)
            except Exception as exc:
                logger.warning("Semantic chunking failed, falling back: %s", exc)
                return self.fallback_chunker.chunk(text, source_file)

        return self._chunks_from_boundaries(text, source_file, boundaries)

    def _cache_key(self, text: str) -> str:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return f"{self.model}:{self.min_chunk_size}:{self.max_chunk_size}:{digest}"

    def _get_cached_boundaries(self, cache_key: str) -> list[int] | None:
        if not self.state_tracker:
            return None
        return self.state_tracker.get_cached_semantic_boundaries(cache_key)

    def _cache_boundaries(self, cache_key: str, boundaries: list[int]) -> None:
        if not self.state_tracker:
            return
        self.state_tracker.cache_semantic_boundaries(
            cache_key=cache_key,
            boundaries=boundaries,
            model=self.model,
            min_chunk_size=self.min_chunk_size,
            max_chunk_size=self.max_chunk_size,
        )

    def _identify_boundaries(self, text: str) -> list[int]:
        prompt = (
            "Identify character offsets where the topic changes.\n"
            "Return a JSON object with a 'boundaries' list.\n\n"
            f"Text:\n{text}\n\n"
            "Output format:\n"
            '{"boundaries": [120, 450, 980]}'
        )

        response = self.ollama_client.generate(
            model=self.model,
            prompt=prompt,
            format="json",
            options={"temperature": self.temperature},
        )

        raw = response.get("response", "{}")
        data = json.loads(raw)
        boundaries = data.get("boundaries", [])

        if not isinstance(boundaries, list) or not all(
            isinstance(item, int) for item in boundaries
        ):
            raise ValueError("Invalid boundaries response")

        return boundaries

    def _chunks_from_boundaries(
        self, text: str, source_file: str, boundaries: list[int]
    ) -> list[TextChunk]:
        positions = [0] + sorted({b for b in boundaries if 0 < b < len(text)}) + [len(text)]
        segments = [text[start:end] for start, end in zip(positions, positions[1:])]
        segments = [segment for segment in segments if segment.strip()]

        merged = []
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
