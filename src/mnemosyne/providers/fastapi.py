import logging
from typing import Any

import requests

from mnemosyne.config.providers import ProviderConfig
from mnemosyne.providers.base import EmbeddingProvider, LLMProvider

logger = logging.getLogger(__name__)


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

    def embed_late(
        self,
        model: str,
        text: str,
        chunk_spans: list[tuple[int, int]],
        options: dict[str, Any] | None = None,
    ) -> list[list[float]]:
        url = f"{self.config.fastapi_base_url}/api/embeddings"
        merged_options = {"late_chunking": True, "chunk_spans": chunk_spans}
        if options:
            merged_options.update(options)
        payload = {
            "model": model or self.config.fastapi_embedding_model,
            "prompt": text,
            "options": merged_options,
        }
        response = requests.post(url, json=payload)
        response.raise_for_status()
        json_response = response.json()
        embeddings = json_response.get("embeddings")
        if not isinstance(embeddings, list):
            raise ValueError("Late chunking response missing embeddings")
        return embeddings

    def embed_query(self, model: str, text: str) -> list[float]:
        url = f"{self.config.fastapi_base_url}/api/embeddings"
        adapter = self.config.query_embedding_adapter
        payload: dict[str, Any] = {
            "model": model or self.config.fastapi_embedding_model,
            "prompt": text,
        }
        if adapter:
            payload["options"] = {"adapter": adapter}
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            json_response = response.json()
            embedding = json_response.get("embedding")
            if not isinstance(embedding, list):
                raise ValueError("Query embedding missing in response")
            return embedding
        except Exception:
            if adapter:
                logger.warning("Query adapter failed; falling back to standard embedding.")
                payload.pop("options", None)
                response = requests.post(url, json=payload)
                response.raise_for_status()
                json_response = response.json()
                return json_response["embedding"]
            raise
