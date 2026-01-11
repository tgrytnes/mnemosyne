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


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, model: str, text: str) -> list[float]:
        pass
