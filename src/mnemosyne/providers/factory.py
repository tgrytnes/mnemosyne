from mnemosyne.config.providers import ProviderConfig
from mnemosyne.providers.base import EmbeddingProvider, LLMProvider
from mnemosyne.providers.fastapi import FastAPIEmbeddingProvider, FastAPILLMProvider
from mnemosyne.providers.groq import GroqLLMProvider
from mnemosyne.providers.lmstudio import LMStudioEmbeddingProvider, LMStudioLLMProvider
from mnemosyne.providers.ollama import OllamaEmbeddingProvider, OllamaLLMProvider
from mnemosyne.providers.vllm import VLLMLLMProvider


class LLMProviderFactory:
    _providers: dict[str, LLMProvider] = {}
    _provider_classes: dict[str, type[LLMProvider]] = {
        "ollama": OllamaLLMProvider,
        "groq": GroqLLMProvider,
        "fastapi": FastAPILLMProvider,
        "vllm": VLLMLLMProvider,
        "lmstudio": LMStudioLLMProvider,
    }

    @classmethod
    def get_provider(cls, config: ProviderConfig) -> LLMProvider:
        provider_name = config.llm_provider
        if provider_name not in cls._providers:
            if provider_name in cls._provider_classes:
                cls._providers[provider_name] = cls._provider_classes[provider_name](config)
            else:
                raise ValueError(f"Unsupported LLM provider: {provider_name}")
        return cls._providers[provider_name]


class EmbeddingProviderFactory:
    _providers: dict[str, EmbeddingProvider] = {}
    _provider_classes: dict[str, type[EmbeddingProvider]] = {
        "ollama": OllamaEmbeddingProvider,
        "fastapi": FastAPIEmbeddingProvider,
        "lmstudio": LMStudioEmbeddingProvider,
    }

    @classmethod
    def get_provider(cls, config: ProviderConfig) -> EmbeddingProvider:
        provider_name = config.embedding_provider
        if provider_name not in cls._providers:
            if provider_name in cls._provider_classes:
                cls._providers[provider_name] = cls._provider_classes[provider_name](config)
            else:
                raise ValueError(f"Unsupported embedding provider: {provider_name}")
        return cls._providers[provider_name]


def create_llm_provider(config: ProviderConfig) -> LLMProvider:
    return LLMProviderFactory.get_provider(config)


def create_embedding_provider(config: ProviderConfig) -> EmbeddingProvider:
    return EmbeddingProviderFactory.get_provider(config)
