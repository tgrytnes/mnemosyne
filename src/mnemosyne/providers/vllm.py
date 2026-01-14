from typing import Any

import requests

from mnemosyne.config.providers import ProviderConfig
from mnemosyne.providers.base import LLMProvider


class VLLMLLMProvider(LLMProvider):
    def __init__(self, config: ProviderConfig):
        self.config = config

    def supports_structured_output(self) -> bool:
        return True

    def generate(
        self,
        model: str,
        prompt: str,
        format: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.config.vllm_base_url}/v1/chat/completions"
        model_id = model or self.config.vllm_llm_model
        if not model_id:
            raise ValueError("vLLM model is required (set VLLM_LLM_MODEL or pass model).")
        payload: dict[str, Any] = {
            "model": model_id,
            "messages": [{"role": "user", "content": prompt}],
        }

        if options:
            for key in ("temperature", "top_p", "max_tokens", "stream", "seed", "stop"):
                if key in options:
                    payload[key] = options[key]

        response_format = None
        guided_json = None
        if options and "response_format" in options:
            response_format = options["response_format"]
        elif options and "json_schema" in options:
            guided_json = options["json_schema"]
            if isinstance(guided_json, dict) and "schema" in guided_json:
                guided_json = guided_json["schema"]
        elif format == "json":
            response_format = {"type": "json_object"}

        if guided_json is not None:
            payload["guided_json"] = guided_json
        elif response_format:
            payload["response_format"] = response_format

        headers: dict[str, str] = {}
        if self.config.vllm_api_key:
            headers["Authorization"] = f"Bearer {self.config.vllm_api_key}"

        response = requests.post(
            url,
            headers=headers or None,
            json=payload,
            timeout=self.config.vllm_timeout,
        )
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices", [])
        message = choices[0].get("message", {}) if choices else {}
        content = message.get("content", "")
        return {"response": content, "raw": data}
