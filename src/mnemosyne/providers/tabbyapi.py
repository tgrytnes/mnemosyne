from typing import Any

import requests

from mnemosyne.config.providers import ProviderConfig
from mnemosyne.providers.base import LLMProvider


class TabbyAPILLMProvider(LLMProvider):
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
        url = f"{self.config.tabbyapi_base_url}/v1/chat/completions"
        model_id = model or self.config.tabbyapi_llm_model
        if not model_id:
            raise ValueError("TabbyAPI model is required (set TABBYAPI_LLM_MODEL or pass model).")

        payload: dict[str, Any] = {
            "model": model_id,
            "messages": [{"role": "user", "content": prompt}],
        }

        if options:
            for key in ("temperature", "top_p", "max_tokens", "stream", "seed", "stop"):
                if key in options:
                    payload[key] = options[key]

        if options and "json_schema" in options:
            schema = options["json_schema"]
            if isinstance(schema, dict) and "name" in schema:
                schema_payload = schema
            else:
                schema_payload = {"name": "response", "schema": schema}
            payload["response_format"] = {"type": "json_schema", "json_schema": schema_payload}
        elif format == "json":
            payload["response_format"] = {"type": "json_object"}

        headers: dict[str, str] = {}
        if self.config.tabbyapi_api_key:
            headers["Authorization"] = f"Bearer {self.config.tabbyapi_api_key}"

        response = requests.post(
            url,
            headers=headers or None,
            json=payload,
            timeout=self.config.tabbyapi_timeout,
        )
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices", [])
        message = choices[0].get("message", {}) if choices else {}
        content = message.get("content", "")
        return {"response": content, "raw": data}
