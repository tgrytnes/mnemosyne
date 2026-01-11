from typing import Any

import ollama

from mnemosyne.config.providers import ProviderConfig
from mnemosyne.providers.base import EmbeddingProvider, LLMProvider


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
