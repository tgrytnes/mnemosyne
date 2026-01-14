"""Unit tests for query embedding adapter usage."""

from unittest.mock import MagicMock, patch

from mnemosyne.config.providers import ProviderConfig
from mnemosyne.providers.fastapi import FastAPIEmbeddingProvider
from mnemosyne.providers.ollama import OllamaEmbeddingProvider


def test_fastapi_embed_query_sends_adapter():
    with patch("mnemosyne.providers.fastapi.requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = {"embedding": [1.0]}
        mock_post.return_value = mock_response

        config = ProviderConfig(
            fastapi_base_url="http://localhost:8000",
            fastapi_embedding_model="fastapi_embedding_model",
        )
        config.query_embedding_adapter = "retrieval.query"
        provider = FastAPIEmbeddingProvider(config)

        provider.embed_query(model="", text="query text")

        mock_post.assert_called_with(
            "http://localhost:8000/api/embeddings",
            json={
                "model": "fastapi_embedding_model",
                "prompt": "query text",
                "options": {"adapter": "retrieval.query"},
            },
        )


def test_ollama_embed_query_falls_back():
    config = ProviderConfig(
        ollama_base_url="http://localhost:11434",
        ollama_embedding_model="test_embedding_model",
    )
    config.query_embedding_adapter = "retrieval.query"
    provider = OllamaEmbeddingProvider(config)
    provider.client = MagicMock()
    provider.client.embeddings.return_value = {"embedding": [0.1, 0.2]}

    embedding = provider.embed_query(model="", text="query text")

    assert embedding == [0.1, 0.2]
