"""
Unit tests for chunking strategy selection via environment config.
"""

from unittest.mock import MagicMock

from mnemosyne.aletheia.hybrid_chunker import HybridChunker
from mnemosyne.aletheia.text_chunker import TextChunker
from mnemosyne.cli.ingest import IngestionConfig, create_ingestor
from mnemosyne.config.providers import ProviderConfig


class TestChunkingConfigEnv:
    """Test CHUNKING_STRATEGY env var is honored."""

    def test_env_selects_hybrid_strategy(self, monkeypatch, tmp_path, mocker):
        """Should create hybrid chunker when CHUNKING_STRATEGY=hybrid"""
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
        monkeypatch.setenv("CHUNKING_STRATEGY", "hybrid")

        mock_weaviate = mocker.MagicMock()
        mock_ollama = mocker.MagicMock()

        monkeypatch.setattr(
            "mnemosyne.cli.ingest.weaviate.connect_to_local",
            lambda *args, **kwargs: mock_weaviate,
        )
        monkeypatch.setattr(
            "mnemosyne.cli.ingest.ollama.Client", lambda *args, **kwargs: mock_ollama
        )
        monkeypatch.setattr(
            "mnemosyne.aletheia.obsidian_ingestor.WeaviateSchemaManager.ensure_collection_exists",
            lambda *args, **kwargs: None,
        )

        config = IngestionConfig()
        ingestor = create_ingestor(config)

        assert isinstance(ingestor.chunker, HybridChunker)

    def test_default_strategy_is_recursive(self, monkeypatch, tmp_path, mocker):
        """Should default to recursive chunking when CHUNKING_STRATEGY not set"""
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
        monkeypatch.delenv("CHUNKING_STRATEGY", raising=False)

        mock_weaviate = mocker.MagicMock()
        mock_ollama = mocker.MagicMock()

        monkeypatch.setattr(
            "mnemosyne.cli.ingest.weaviate.connect_to_local",
            lambda *args, **kwargs: mock_weaviate,
        )
        monkeypatch.setattr(
            "mnemosyne.cli.ingest.ollama.Client", lambda *args, **kwargs: mock_ollama
        )
        monkeypatch.setattr(
            "mnemosyne.aletheia.obsidian_ingestor.WeaviateSchemaManager.ensure_collection_exists",
            lambda *args, **kwargs: None,
        )

        config = IngestionConfig()
        ingestor = create_ingestor(config)

        assert isinstance(ingestor.chunker, TextChunker)

    def test_contextual_defaults_to_small_model_for_fastapi(self, monkeypatch, tmp_path):
        """Should use a smaller contextual model by default for fastapi."""
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
        monkeypatch.setenv("CHUNKING_AUGMENTATION", "contextual")
        monkeypatch.delenv("CONTEXTUAL_LLM_MODEL", raising=False)
        monkeypatch.delenv("CONTEXTUAL_LLM_PROVIDER", raising=False)

        mock_weaviate = MagicMock()
        monkeypatch.setattr(
            "mnemosyne.aletheia.obsidian_ingestor.WeaviateSchemaManager.ensure_collection_exists",
            lambda *args, **kwargs: None,
        )

        config = IngestionConfig()
        provider_config = ProviderConfig(llm_provider="fastapi", embedding_provider="fastapi")
        ingestor = create_ingestor(config, provider_config, weaviate_client=mock_weaviate)

        assert ingestor.contextual_llm_model == "Qwen3_8B"
