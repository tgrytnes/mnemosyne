from typing import Any

import requests

from mnemosyne.config.providers import ProviderConfig
from mnemosyne.providers.base import EmbeddingProvider, LLMProvider


class FastAPILLMProvider(LLMProvider):
    def __init__(self, config: ProviderConfig):
        self.config = config

    def generate(
        self,
        model: str,
        prompt: str,
        format: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.config.fastapi_base_url}/api/generate"
        payload = {
            "model": model or self.config.fastapi_llm_model,
            "prompt": prompt,
            "format": format,
            "options": options,
        }
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()


class FastAPIEmbeddingProvider(EmbeddingProvider):
    def __init__(self, config: ProviderConfig):
        self.config = config

    def embed(self, model: str, text: str) -> list[float]:
        url = f"{self.config.fastapi_base_url}/api/embeddings"
        payload = {
            "model": model or self.config.fastapi_embedding_model,
            "prompt": text,
        }
        response = requests.post(url, json=payload)
        response.raise_for_status()
        json_response = response.json()
        return json_response["embedding"]
