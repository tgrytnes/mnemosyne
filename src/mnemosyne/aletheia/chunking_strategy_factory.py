"""
Factory for creating chunking strategies based on configuration.
"""

from dataclasses import dataclass

from mnemosyne.aletheia.hybrid_chunker import HybridChunker
from mnemosyne.aletheia.semantic_chunker import SemanticChunker
from mnemosyne.aletheia.text_chunker import TextChunker


@dataclass
class ChunkingStrategyConfig:
    """Configuration for chunking strategies."""

    strategy: str = "recursive"
    chunk_size: int = 400
    chunk_overlap: int = 100
    semantic_min_chunk_size: int = 100
    semantic_max_chunk_size: int = 1000
    semantic_model: str = "qwen3:0.6b"
    semantic_temperature: float = 0.2
    semantic_request_timeout: float = 5.0
    semantic_total_timeout: float = 30.0
    section_semantic_min_length: int = 1000


class ChunkingStrategyFactory:
    """Create chunking strategies from config values."""

    def __init__(self, ollama_client, state_tracker):
        self.ollama_client = ollama_client
        self.state_tracker = state_tracker

    def create(
        self,
        config: ChunkingStrategyConfig,
        recursive_chunker: TextChunker | None = None,
    ):
        recursive = recursive_chunker or TextChunker(
            chunk_size=config.chunk_size, chunk_overlap=config.chunk_overlap
        )

        strategy = (config.strategy or "recursive").lower()
        if strategy == "recursive":
            return recursive

        semantic = SemanticChunker(
            ollama_client=self.ollama_client,
            state_tracker=self.state_tracker,
            fallback_chunker=recursive,
            min_chunk_size=config.semantic_min_chunk_size,
            max_chunk_size=config.semantic_max_chunk_size,
            model=config.semantic_model,
            temperature=config.semantic_temperature,
            request_timeout=config.semantic_request_timeout,
            total_timeout=config.semantic_total_timeout,
        )

        if strategy == "semantic":
            return semantic

        if strategy == "hybrid":
            return HybridChunker(
                semantic_chunker=semantic,
                recursive_chunker=recursive,
                section_semantic_min_length=config.section_semantic_min_length,
            )

        raise ValueError(f"Unknown chunking strategy: {config.strategy}")
