"""
Factory for creating chunking strategies based on configuration.
"""

from dataclasses import dataclass

from mnemosyne.aletheia.hybrid_chunker import HybridChunker
from mnemosyne.aletheia.semantic_chunker import SemanticChunker
from mnemosyne.aletheia.semantic_cosine_chunker import SemanticCosineChunker
from mnemosyne.aletheia.text_chunker import TextChunker
from mnemosyne.providers.base import EmbeddingProvider, LLMProvider


@dataclass
class ChunkingStrategyConfig:
    """Configuration for chunking strategies."""

    strategy: str = "recursive"
    chunk_size: int = 400
    chunk_overlap: int = 100
    semantic_min_chunk_size: int = 100
    semantic_max_chunk_size: int = 1000
    semantic_model: str = "gemma3:1b"  # Better for semantic boundary detection
    semantic_temperature: float = 0.2
    semantic_request_timeout: float = 5.0
    semantic_total_timeout: float = 30.0
    section_semantic_min_length: int = 1000
    semantic_cosine_threshold: float = 0.78
    semantic_cosine_min_chunk_size: int = 100
    semantic_cosine_max_chunk_size: int = 1000
    semantic_cosine_embedding_model: str = ""


class ChunkingStrategyFactory:
    """Create chunking strategies from config values."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        state_tracker,
        embedding_provider: EmbeddingProvider | None = None,
    ):
        self.llm_provider = llm_provider
        self.state_tracker = state_tracker
        self.embedding_provider = embedding_provider

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
            llm_provider=self.llm_provider,
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

        if strategy == "semantic_cosine":
            if self.embedding_provider is None:
                raise ValueError("embedding_provider is required for semantic_cosine chunking")
            return SemanticCosineChunker(
                embedding_provider=self.embedding_provider,
                fallback_chunker=recursive,
                similarity_threshold=config.semantic_cosine_threshold,
                min_chunk_size=config.semantic_cosine_min_chunk_size,
                max_chunk_size=config.semantic_cosine_max_chunk_size,
                embedding_model=config.semantic_cosine_embedding_model,
            )

        if strategy == "hybrid":
            return HybridChunker(
                semantic_chunker=semantic,
                recursive_chunker=recursive,
                section_semantic_min_length=config.section_semantic_min_length,
            )

        raise ValueError(f"Unknown chunking strategy: {config.strategy}")
