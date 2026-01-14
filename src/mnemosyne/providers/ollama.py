import logging
from typing import Any

import ollama

from mnemosyne.config.providers import ProviderConfig
from mnemosyne.providers.base import EmbeddingProvider, LLMProvider

logger = logging.getLogger(__name__)


class OllamaLLMProvider(LLMProvider):
    def __init__(self, config: ProviderConfig):
        self.config = config
        self.client = ollama.Client(host=config.ollama_base_url)

    def generate(
        self,
        model: str,
        prompt: str,
        format: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.client.generate(
            model=model or self.config.ollama_llm_model,
            prompt=prompt,
            format=format,
            options=options,
        )


class OllamaEmbeddingProvider(EmbeddingProvider):
    def __init__(self, config: ProviderConfig):
        self.config = config
        self.client = ollama.Client(host=config.ollama_base_url)

    def embed(self, model: str, text: str) -> list[float]:
        response = self.client.embeddings(
            model=model or self.config.ollama_embedding_model, prompt=text
        )
        return response["embedding"]

    def embed_late(
        self,
        model: str,
        text: str,
        chunk_spans: list[tuple[int, int]],
        options: dict[str, Any] | None = None,
    ) -> list[list[float]]:
        raise NotImplementedError("Late chunking is not supported by Ollama embeddings.")

    def embed_query(self, model: str, text: str) -> list[float]:
        adapter = self.config.query_embedding_adapter
        if adapter:
            logger.warning(
                "Ollama embeddings do not support adapters; "
                "falling back to standard query embedding."
            )
        return self.embed(model=model, text=text)
