from typing import Any

from groq import Groq

from mnemosyne.config.providers import ProviderConfig
from mnemosyne.providers.base import LLMProvider


class GroqLLMProvider(LLMProvider):
    def __init__(self, config: ProviderConfig):
        if not config.groq_api_key:
            raise ValueError("Groq API key is not set")
        self.config = config
        self.client = Groq(api_key=config.groq_api_key)

    def generate(
        self,
        model: str,
        prompt: str,
        format: str | None = None,  # Groq API doesn't have a direct format equivalent
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        chat_completion = self.client.chat.completions.create(
            model=model or self.config.groq_llm_model,
            messages=[{"role": "user", "content": prompt}],
        )
        response_content = chat_completion.choices[0].message.content
        return {"response": response_content}
