import json
import os

import pytest
import requests


@pytest.mark.e2e
def test_tabbyapi_strict_json_schema_response():
    base_url = os.getenv("TEST_TABBYAPI_BASE_URL") or os.getenv("TABBYAPI_BASE_URL")
    model = os.getenv("TEST_TABBYAPI_LLM_MODEL") or os.getenv("TABBYAPI_LLM_MODEL")

    if not base_url or not model:
        pytest.skip("TabbyAPI env vars are not configured.")

    try:
        response = requests.get(f"{base_url}/v1/models", timeout=5)
        response.raise_for_status()
    except Exception as exc:
        pytest.skip(f"TabbyAPI is not reachable: {exc}")

    from mnemosyne.config.providers import ProviderConfig
    from mnemosyne.providers.tabbyapi import TabbyAPILLMProvider

    config = ProviderConfig(tabbyapi_base_url=base_url, tabbyapi_llm_model=model)
    provider = TabbyAPILLMProvider(config)
    schema = {
        "name": "health_check",
        "schema": {
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
            "additionalProperties": False,
        },
    }

    result = provider.generate(
        model=model,
        prompt='Return {"ok": true} as JSON only.',
        options={"json_schema": schema},
    )

    data = json.loads(result["response"])
    assert data.get("ok") is True
