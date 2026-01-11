"""
Unit tests for chunking strategy factory.
"""

import pytest

from mnemosyne.aletheia.chunking_strategy_factory import (
    ChunkingStrategyConfig,
    ChunkingStrategyFactory,
)
from mnemosyne.aletheia.hybrid_chunker import HybridChunker
from mnemosyne.aletheia.semantic_chunker import SemanticChunker
from mnemosyne.aletheia.text_chunker import TextChunker


class TestChunkingStrategyFactory:
    """Test strategy creation based on config"""

    def test_creates_recursive_strategy(self, mocker):
        factory = ChunkingStrategyFactory(
            llm_provider=mocker.MagicMock(), state_tracker=mocker.MagicMock()
        )
        config = ChunkingStrategyConfig(strategy="recursive")

        chunker = factory.create(config)

        assert isinstance(chunker, TextChunker)

    def test_creates_semantic_strategy(self, mocker):
        factory = ChunkingStrategyFactory(
            llm_provider=mocker.MagicMock(), state_tracker=mocker.MagicMock()
        )
        config = ChunkingStrategyConfig(strategy="semantic")

        chunker = factory.create(config)

        assert isinstance(chunker, SemanticChunker)

    def test_creates_hybrid_strategy(self, mocker):
        factory = ChunkingStrategyFactory(
            llm_provider=mocker.MagicMock(), state_tracker=mocker.MagicMock()
        )
        config = ChunkingStrategyConfig(strategy="hybrid")

        chunker = factory.create(config)

        assert isinstance(chunker, HybridChunker)

    def test_invalid_strategy_raises(self, mocker):
        factory = ChunkingStrategyFactory(
            llm_provider=mocker.MagicMock(), state_tracker=mocker.MagicMock()
        )
        config = ChunkingStrategyConfig(strategy="unknown")

        with pytest.raises(ValueError):
            factory.create(config)
