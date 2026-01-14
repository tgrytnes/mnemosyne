from unittest.mock import MagicMock, patch

from mnemosyne.config.providers import ProviderConfig
from mnemosyne.providers.vllm import VLLMLLMProvider


def test_vllm_provider_sends_json_schema():
    config = ProviderConfig(
        llm_provider="vllm",
        vllm_base_url="http://vllm.local",
        vllm_api_key="token",
        vllm_llm_model="test-model",
    )
    provider = VLLMLLMProvider(config)

    schema = {
        "name": "test_schema",
        "schema": {
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
            "additionalProperties": False,
        },
    }

    with patch("mnemosyne.providers.vllm.requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": '{"ok": true}'}}]}
        mock_post.return_value = mock_response

        response = provider.generate(
            model="",
            prompt="test prompt",
            format="json",
            options={"temperature": 0.2, "json_schema": schema},
        )

        assert response["response"] == '{"ok": true}'
        mock_post.assert_called_with(
            "http://vllm.local/v1/chat/completions",
            headers={"Authorization": "Bearer token"},
            json={
                "model": "test-model",
                "messages": [{"role": "user", "content": "test prompt"}],
                "temperature": 0.2,
                "guided_json": schema["schema"],
            },
            timeout=30.0,
        )
