"""Unit tests for LM Studio provider.

Tests for LMStudioLLMProvider and LMStudioEmbeddingProvider.
Following TDD: these tests are written before the implementation.
"""

from unittest.mock import MagicMock, patch

import pytest

from mnemosyne.config.providers import ProviderConfig
from mnemosyne.providers.lmstudio import LMStudioEmbeddingProvider, LMStudioLLMProvider


class TestLMStudioLLMProvider:
    """Tests for LMStudioLLMProvider."""

    def test_generate_basic(self):
        """Should generate a response using OpenAI-compatible API."""
        config = ProviderConfig(
            llm_provider="lmstudio",
            lmstudio_base_url="http://192.168.178.212:1234",
            lmstudio_llm_model="qwen/qwen3-4b-2507",
        )
        provider = LMStudioLLMProvider(config)

        with patch("mnemosyne.providers.lmstudio.requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {"choices": [{"message": {"content": "Hello!"}}]}
            mock_post.return_value = mock_response

            response = provider.generate(
                model="qwen/qwen3-4b-2507",
                prompt="Say hello",
            )

            assert response["response"] == "Hello!"
            mock_post.assert_called_with(
                "http://192.168.178.212:1234/v1/chat/completions",
                headers=None,
                json={
                    "model": "qwen/qwen3-4b-2507",
                    "messages": [{"role": "user", "content": "Say hello"}],
                },
                timeout=30.0,
            )

    def test_generate_with_options(self):
        """Should pass temperature, top_p, max_tokens, and other options."""
        config = ProviderConfig(
            llm_provider="lmstudio",
            lmstudio_base_url="http://localhost:1234",
            lmstudio_llm_model="test-model",
        )
        provider = LMStudioLLMProvider(config)

        with patch("mnemosyne.providers.lmstudio.requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {"choices": [{"message": {"content": "response"}}]}
            mock_post.return_value = mock_response

            provider.generate(
                model="test-model",
                prompt="test",
                options={"temperature": 0.7, "top_p": 0.9, "max_tokens": 100},
            )

            call_args = mock_post.call_args
            payload = call_args.kwargs["json"]
            assert payload["temperature"] == 0.7
            assert payload["top_p"] == 0.9
            assert payload["max_tokens"] == 100

    def test_generate_uses_default_model(self):
        """Should use default model from config when model param is empty."""
        config = ProviderConfig(
            llm_provider="lmstudio",
            lmstudio_base_url="http://localhost:1234",
            lmstudio_llm_model="default-model",
        )
        provider = LMStudioLLMProvider(config)

        with patch("mnemosyne.providers.lmstudio.requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
            mock_post.return_value = mock_response

            provider.generate(model="", prompt="test")

            call_args = mock_post.call_args
            payload = call_args.kwargs["json"]
            assert payload["model"] == "default-model"

    def test_supports_structured_output(self):
        """Should return True for supports_structured_output."""
        config = ProviderConfig(
            llm_provider="lmstudio",
            lmstudio_base_url="http://localhost:1234",
            lmstudio_llm_model="test-model",
        )
        provider = LMStudioLLMProvider(config)
        assert provider.supports_structured_output() is True

    def test_generate_with_json_schema(self):
        """Should send json_schema via response_format for strict JSON."""
        config = ProviderConfig(
            llm_provider="lmstudio",
            lmstudio_base_url="http://localhost:1234",
            lmstudio_llm_model="test-model",
        )
        provider = LMStudioLLMProvider(config)

        schema = {
            "name": "test_schema",
            "schema": {
                "type": "object",
                "properties": {"boundaries": {"type": "array", "items": {"type": "integer"}}},
                "required": ["boundaries"],
                "additionalProperties": False,
            },
        }

        with patch("mnemosyne.providers.lmstudio.requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "choices": [{"message": {"content": '{"boundaries": [0, 100, 200]}'}}]
            }
            mock_post.return_value = mock_response

            response = provider.generate(
                model="test-model",
                prompt="Return boundaries",
                format="json",
                options={"temperature": 0.2, "json_schema": schema},
            )

            assert response["response"] == '{"boundaries": [0, 100, 200]}'
            call_args = mock_post.call_args
            payload = call_args.kwargs["json"]
            # LM Studio uses OpenAI-compatible response_format with json_schema
            assert "response_format" in payload
            assert payload["response_format"]["type"] == "json_schema"
            assert payload["response_format"]["json_schema"] == schema

    def test_generate_with_basic_json_format(self):
        """Should use json_object response_format when format='json' without schema."""
        config = ProviderConfig(
            llm_provider="lmstudio",
            lmstudio_base_url="http://localhost:1234",
            lmstudio_llm_model="test-model",
        )
        provider = LMStudioLLMProvider(config)

        with patch("mnemosyne.providers.lmstudio.requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "choices": [{"message": {"content": '{"key": "value"}'}}]
            }
            mock_post.return_value = mock_response

            provider.generate(
                model="test-model",
                prompt="Return JSON",
                format="json",
            )

            call_args = mock_post.call_args
            payload = call_args.kwargs["json"]
            assert payload["response_format"] == {"type": "json_object"}

    def test_generate_raises_on_missing_model(self):
        """Should raise ValueError when no model specified and no default."""
        config = ProviderConfig(
            llm_provider="lmstudio",
            lmstudio_base_url="http://localhost:1234",
            lmstudio_llm_model="",
        )
        provider = LMStudioLLMProvider(config)

        with pytest.raises(ValueError, match="model is required"):
            provider.generate(model="", prompt="test")


class TestLMStudioEmbeddingProvider:
    """Tests for LMStudioEmbeddingProvider."""

    def test_embed_basic(self):
        """Should generate embeddings using OpenAI-compatible API."""
        config = ProviderConfig(
            embedding_provider="lmstudio",
            lmstudio_base_url="http://192.168.178.212:1234",
            lmstudio_embedding_model="text-embedding-nomic-embed-text-v1.5",
        )
        provider = LMStudioEmbeddingProvider(config)

        with patch("mnemosyne.providers.lmstudio.requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {"data": [{"embedding": [0.1, 0.2, 0.3, 0.4]}]}
            mock_post.return_value = mock_response

            embedding = provider.embed(
                model="text-embedding-nomic-embed-text-v1.5",
                text="Hello world",
            )

            assert embedding == [0.1, 0.2, 0.3, 0.4]
            mock_post.assert_called_with(
                "http://192.168.178.212:1234/v1/embeddings",
                headers=None,
                json={
                    "model": "text-embedding-nomic-embed-text-v1.5",
                    "input": "Hello world",
                },
                timeout=30.0,
            )

    def test_embed_uses_default_model(self):
        """Should use default model from config when model param is empty."""
        config = ProviderConfig(
            embedding_provider="lmstudio",
            lmstudio_base_url="http://localhost:1234",
            lmstudio_embedding_model="default-embedding-model",
        )
        provider = LMStudioEmbeddingProvider(config)

        with patch("mnemosyne.providers.lmstudio.requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {"data": [{"embedding": [1.0, 2.0]}]}
            mock_post.return_value = mock_response

            provider.embed(model="", text="test")

            call_args = mock_post.call_args
            payload = call_args.kwargs["json"]
            assert payload["model"] == "default-embedding-model"

    def test_embed_query(self):
        """Should call embed for query text (no special adapter support)."""
        config = ProviderConfig(
            embedding_provider="lmstudio",
            lmstudio_base_url="http://localhost:1234",
            lmstudio_embedding_model="embedding-model",
        )
        provider = LMStudioEmbeddingProvider(config)

        with patch("mnemosyne.providers.lmstudio.requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {"data": [{"embedding": [0.5, 0.6]}]}
            mock_post.return_value = mock_response

            embedding = provider.embed_query(model="", text="query text")

            assert embedding == [0.5, 0.6]

    def test_embed_late_not_implemented(self):
        """Should raise NotImplementedError for late chunking."""
        config = ProviderConfig(
            embedding_provider="lmstudio",
            lmstudio_base_url="http://localhost:1234",
            lmstudio_embedding_model="embedding-model",
        )
        provider = LMStudioEmbeddingProvider(config)

        with pytest.raises(NotImplementedError):
            provider.embed_late(
                model="embedding-model",
                text="some text",
                chunk_spans=[(0, 10), (10, 20)],
            )


class TestLMStudioProviderFactory:
    """Tests for factory registration of LM Studio providers."""

    def test_create_lmstudio_llm_provider(self):
        """Should create LMStudioLLMProvider via factory."""
        from mnemosyne.providers.factory import create_llm_provider

        config = ProviderConfig(
            llm_provider="lmstudio",
            lmstudio_base_url="http://localhost:1234",
        )
        provider = create_llm_provider(config)
        assert isinstance(provider, LMStudioLLMProvider)

    def test_create_lmstudio_embedding_provider(self):
        """Should create LMStudioEmbeddingProvider via factory."""
        from mnemosyne.providers.factory import create_embedding_provider

        config = ProviderConfig(
            embedding_provider="lmstudio",
            lmstudio_base_url="http://localhost:1234",
        )
        provider = create_embedding_provider(config)
        assert isinstance(provider, LMStudioEmbeddingProvider)
