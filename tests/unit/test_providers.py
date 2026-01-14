from unittest.mock import MagicMock, patch

import pytest

from mnemosyne.config.providers import ProviderConfig

# To be created imports
from mnemosyne.providers.factory import (
    EmbeddingProviderFactory,
    LLMProviderFactory,
    create_embedding_provider,
    create_llm_provider,
)
from mnemosyne.providers.fastapi import FastAPIEmbeddingProvider, FastAPILLMProvider
from mnemosyne.providers.groq import GroqLLMProvider
from mnemosyne.providers.ollama import OllamaEmbeddingProvider, OllamaLLMProvider
from mnemosyne.providers.vllm import VLLMLLMProvider


# Test LLM Provider Factory
def test_create_ollama_llm_provider():
    config = ProviderConfig(llm_provider="ollama")
    provider = create_llm_provider(config)
    assert isinstance(provider, OllamaLLMProvider)


def test_create_groq_llm_provider():
    config = ProviderConfig(llm_provider="groq", groq_api_key="fake_key")
    provider = create_llm_provider(config)
    assert isinstance(provider, GroqLLMProvider)


def test_create_fastapi_llm_provider():
    config = ProviderConfig(llm_provider="fastapi")
    provider = create_llm_provider(config)
    assert isinstance(provider, FastAPILLMProvider)


def test_create_vllm_llm_provider():
    config = ProviderConfig(llm_provider="vllm", vllm_base_url="http://vllm.local")
    provider = create_llm_provider(config)
    assert isinstance(provider, VLLMLLMProvider)


def test_llm_provider_factory_singleton():
    config = ProviderConfig(llm_provider="ollama")
    provider1 = LLMProviderFactory.get_provider(config)
    provider2 = LLMProviderFactory.get_provider(config)
    assert provider1 is provider2


# Test Embedding Provider Factory
def test_create_ollama_embedding_provider():
    config = ProviderConfig(embedding_provider="ollama")
    provider = create_embedding_provider(config)
    assert isinstance(provider, OllamaEmbeddingProvider)


def test_create_fastapi_embedding_provider():
    config = ProviderConfig(embedding_provider="fastapi")
    provider = create_embedding_provider(config)
    assert isinstance(provider, FastAPIEmbeddingProvider)


def test_embedding_provider_factory_singleton():
    config = ProviderConfig(embedding_provider="ollama")
    provider1 = EmbeddingProviderFactory.get_provider(config)
    provider2 = EmbeddingProviderFactory.get_provider(config)
    assert provider1 is provider2


# Test Ollama Providers
def test_ollama_llm_provider_generate():
    with patch("mnemosyne.providers.ollama.ollama.Client") as mock_client:
        mock_instance = mock_client.return_value
        mock_instance.generate.return_value = {"response": "test response"}
        config = ProviderConfig(
            ollama_base_url="http://localhost:11434", ollama_llm_model="test_model"
        )
        provider = OllamaLLMProvider(config)
        response = provider.generate("test_model", "test prompt")
        assert response["response"] == "test response"
        mock_instance.generate.assert_called_with(
            model="test_model", prompt="test prompt", format=None, options=None
        )


def test_ollama_embedding_provider_embed():
    with patch("mnemosyne.providers.ollama.ollama.Client") as mock_client:
        mock_instance = mock_client.return_value
        mock_instance.embeddings.return_value = {"embedding": [1.0, 2.0, 3.0]}
        config = ProviderConfig(
            ollama_base_url="http://localhost:11434",
            ollama_embedding_model="test_embedding_model",
        )
        provider = OllamaEmbeddingProvider(config)
        embedding = provider.embed("test_embedding_model", "test text")
        assert embedding == [1.0, 2.0, 3.0]
        mock_instance.embeddings.assert_called_with(
            model="test_embedding_model", prompt="test text"
        )


# Test Groq Provider
def test_groq_llm_provider_generate():
    with patch("mnemosyne.providers.groq.Groq") as mock_groq:
        mock_instance = mock_groq.return_value
        mock_chat_completion = MagicMock()
        mock_chat_completion.choices[0].message.content = "groq response"
        mock_instance.chat.completions.create.return_value = mock_chat_completion

        config = ProviderConfig(groq_api_key="fake_key", groq_llm_model="groq_model")
        provider = GroqLLMProvider(config)
        response = provider.generate("groq_model", "test prompt")

        assert response["response"] == "groq response"
        mock_instance.chat.completions.create.assert_called_with(
            model="groq_model", messages=[{"role": "user", "content": "test prompt"}]
        )


# Test FastAPI Providers
def test_fastapi_llm_provider_generate():
    with patch("mnemosyne.providers.fastapi.requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "fastapi response"}
        mock_post.return_value = mock_response

        config = ProviderConfig(
            fastapi_base_url="http://localhost:8000",
            fastapi_llm_model="fastapi_model",
        )
        provider = FastAPILLMProvider(config)
        response = provider.generate("fastapi_model", "test prompt")

        assert response["response"] == "fastapi response"
        mock_post.assert_called_with(
            "http://localhost:8000/api/generate",
            json={
                "model": "fastapi_model",
                "prompt": "test prompt",
                "format": None,
                "options": None,
            },
        )


def test_fastapi_embedding_provider_embed():
    with patch("mnemosyne.providers.fastapi.requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = {"embedding": [4.0, 5.0, 6.0]}
        mock_post.return_value = mock_response

        config = ProviderConfig(
            fastapi_base_url="http://localhost:8000",
            fastapi_embedding_model="fastapi_embedding_model",
        )
        provider = FastAPIEmbeddingProvider(config)
        embedding = provider.embed("fastapi_embedding_model", "test text")

        assert embedding == [4.0, 5.0, 6.0]
        mock_post.assert_called_with(
            "http://localhost:8000/api/embeddings",
            json={"model": "fastapi_embedding_model", "prompt": "test text"},
        )


# Test for invalid provider
def test_invalid_llm_provider():
    with pytest.raises(ValueError):
        config = ProviderConfig(llm_provider="invalid_provider")
        create_llm_provider(config)


def test_invalid_embedding_provider():
    with pytest.raises(ValueError):
        config = ProviderConfig(embedding_provider="invalid_provider")
        create_embedding_provider(config)
