"""
Semantic chunking using LLM boundary detection.
"""

import hashlib
import json
import logging
import os

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
        model: str | None = None,  # Better for semantic understanding, runs on Pi
        temperature: float = 0.1,  # Lower temperature for more consistent boundary detection
        request_timeout: float = 10.0,  # Longer timeout for larger model
        total_timeout: float = 60.0,
    ):
        self.ollama_client = ollama_client
        self.state_tracker = state_tracker
        self.fallback_chunker = fallback_chunker or TextChunker()
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.model = model or os.getenv("SEMANTIC_LLM_MODEL", "gemma3:1b")
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
            "You are a text segmentation expert.\n"
            "Identify where the topic changes significantly.\n\n"
            "Rules:\n"
            "- A topic change is when the subject matter shifts to a new, distinct concept.\n"
            "- Only return CHARACTER OFFSETS (0-based index into the text string).\n"
            "- Do NOT return line numbers or word counts.\n"
            "- Return JSON ONLY: {\"boundaries\": [offsets...]}\n"
            "- If there is an obvious topic shift, include at least one boundary.\n"
            "- If no topic changes exist, return {\"boundaries\": []}.\n\n"
            "Example:\n"
            "Text: \"Cats are pets. Dogs are pets.\\n\\nQuantum physics studies particles.\"\n"
            "Output: {\"boundaries\": [29]}\n\n"
            f"Text:\n{text}\n\n"
            "Output format:\n"
            "{\"boundaries\": [120, 450, 980]}"
        )

        response = self.ollama_client.generate(
            model=self.model,
            prompt=prompt,
            format="json",
            options={"temperature": self.temperature},
        )

        raw = response.get("response", "{}")
        try:
            data = json.loads(raw)
            boundaries = data.get("boundaries", [])

            if not isinstance(boundaries, list):
                logger.warning(f"Invalid boundaries type: {type(boundaries)}, using empty list")
                return []

            # Validate all items are integers
            valid_boundaries = [b for b in boundaries if isinstance(b, int) and 0 < b < len(text)]

            if len(valid_boundaries) != len(boundaries):
                logger.warning(
                    f"Filtered {len(boundaries) - len(valid_boundaries)} invalid boundaries"
                )

            return sorted(valid_boundaries)

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse LLM response: {e}, raw: {raw[:100]}")
            return []

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
