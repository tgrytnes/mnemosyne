"""LM Studio provider implementation.

LM Studio exposes an OpenAI-compatible API for local LLM inference.
Supports both chat completions and embeddings.
"""

import logging
from typing import Any

import requests

from mnemosyne.config.providers import ProviderConfig
from mnemosyne.providers.base import EmbeddingProvider, LLMProvider

logger = logging.getLogger(__name__)


class LMStudioLLMProvider(LLMProvider):
    """LLM provider for LM Studio using OpenAI-compatible API."""

    def __init__(self, config: ProviderConfig):
        self.config = config

    def supports_structured_output(self) -> bool:
        """LM Studio supports structured JSON output via response_format."""
        return True

    def generate(
        self,
        model: str,
        prompt: str,
        format: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.config.lmstudio_base_url}/v1/chat/completions"
        model_id = model or self.config.lmstudio_llm_model
        if not model_id:
            raise ValueError("LM Studio model is required (set LMSTUDIO_LLM_MODEL or pass model).")

        payload: dict[str, Any] = {
            "model": model_id,
            "messages": [{"role": "user", "content": prompt}],
        }

        if options:
            for key in ("temperature", "top_p", "max_tokens", "stream", "seed", "stop"):
                if key in options:
                    payload[key] = options[key]

        # Handle JSON schema for structured output
        if options and "json_schema" in options:
            schema = options["json_schema"]
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": schema,
            }
        elif format == "json":
            payload["response_format"] = {"type": "json_object"}

        headers: dict[str, str] | None = None
        if self.config.lmstudio_api_key:
            headers = {"Authorization": f"Bearer {self.config.lmstudio_api_key}"}

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=self.config.lmstudio_timeout,
        )
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices", [])
        message = choices[0].get("message", {}) if choices else {}
        content = message.get("content", "")
        return {"response": content, "raw": data}


class LMStudioEmbeddingProvider(EmbeddingProvider):
    """Embedding provider for LM Studio using OpenAI-compatible API."""

    def __init__(self, config: ProviderConfig):
        self.config = config

    def embed(self, model: str, text: str) -> list[float]:
        url = f"{self.config.lmstudio_base_url}/v1/embeddings"
        model_id = model or self.config.lmstudio_embedding_model

        payload = {
            "model": model_id,
            "input": text,
        }

        headers: dict[str, str] | None = None
        if self.config.lmstudio_api_key:
            headers = {"Authorization": f"Bearer {self.config.lmstudio_api_key}"}

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=self.config.lmstudio_timeout,
        )
        response.raise_for_status()
        data = response.json()
        return data["data"][0]["embedding"]

    def embed_late(
        self,
        model: str,
        text: str,
        chunk_spans: list[tuple[int, int]],
        options: dict[str, Any] | None = None,
    ) -> list[list[float]]:
        raise NotImplementedError("Late chunking is not supported by LM Studio embeddings.")

    def embed_query(self, model: str, text: str) -> list[float]:
        """Return an embedding for query text.

        LM Studio does not support query adapters, so this delegates to embed().
        """
        return self.embed(model=model, text=text)
