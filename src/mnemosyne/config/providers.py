import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass
class ProviderConfig:
    llm_profile: str = field(default_factory=lambda: os.getenv("LLM_PROFILE", "local"))
    llm_provider: str | None = field(default_factory=lambda: os.getenv("LLM_PROVIDER"))
    embedding_provider: str | None = field(default_factory=lambda: os.getenv("EMBEDDING_PROVIDER"))

    # Ollama settings
    ollama_base_url: str = field(
        default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    )
    ollama_embedding_model: str = field(
        default_factory=lambda: os.getenv("OLLAMA_EMBEDDING_MODEL", "qwen3-embedding:0.6b")
    )
    ollama_llm_model: str = field(
        default_factory=lambda: os.getenv("OLLAMA_LLM_MODEL", "qwen3:0.6b")
    )

    # Groq settings
    groq_api_key: str | None = field(default_factory=lambda: os.getenv("GROQ_API_KEY"))
    groq_llm_model: str = field(
        default_factory=lambda: os.getenv("GROQ_LLM_MODEL", "llama-3.3-70b-versatile")
    )

    # FastAPI settings
    fastapi_base_url: str = field(
        default_factory=lambda: os.getenv("FASTAPI_BASE_URL", "http://localhost:8000")
    )
    fastapi_llm_model: str = field(
        default_factory=lambda: os.getenv("FASTAPI_LLM_MODEL", "llama3.1:8b")
    )
    fastapi_embedding_model: str = field(
        default_factory=lambda: os.getenv("FASTAPI_EMBEDDING_MODEL", "nomic-embed-text")
    )

    def __post_init__(self):
        if self.llm_provider is None:
            if self.llm_profile == "local":
                self.llm_provider = "ollama"
            elif self.llm_profile == "groq":
                self.llm_provider = "groq"
            elif self.llm_profile == "mac-metal":
                self.llm_provider = "fastapi"
            else:
                self.llm_provider = "ollama"  # Default fallback

        if self.embedding_provider is None:
            if self.llm_profile == "local":
                self.embedding_provider = "ollama"
            elif self.llm_profile == "groq":
                # Groq doesn't have a dedicated embedding provider, fallback to ollama
                self.embedding_provider = "ollama"
            elif self.llm_profile == "mac-metal":
                self.embedding_provider = "fastapi"
            else:
                self.embedding_provider = "ollama"  # Default fallback

    @classmethod
    def from_env(cls):
        return cls()
