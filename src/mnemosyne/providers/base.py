from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    @abstractmethod
    def generate(
        self,
        model: str,
        prompt: str,
        format: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        pass

    def supports_structured_output(self) -> bool:
        """Return True when provider can enforce JSON schema output."""
        return False


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, model: str, text: str) -> list[float]:
        pass

    @abstractmethod
    def embed_late(
        self,
        model: str,
        text: str,
        chunk_spans: list[tuple[int, int]],
        options: dict[str, Any] | None = None,
    ) -> list[list[float]]:
        """Return per-chunk embeddings using late chunking if supported."""
        pass

    @abstractmethod
    def embed_query(self, model: str, text: str) -> list[float]:
        """Return an embedding for query text (adapter-aware when supported)."""
        pass
