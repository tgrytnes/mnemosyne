from unittest.mock import MagicMock, patch

from mnemosyne.config.providers import ProviderConfig
from mnemosyne.providers.vllm import VLLMLLMProvider


def test_vllm_generate_uses_guided_json_from_schema_wrapper():
    config = ProviderConfig(vllm_base_url="http://vllm.local", vllm_llm_model="vllm-model")
    provider = VLLMLLMProvider(config)
    schema = {
        "name": "semantic_boundaries",
        "schema": {"type": "object", "properties": {"boundaries": {"type": "array"}}},
    }

    with patch("mnemosyne.providers.vllm.requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "{}"}}]}
        mock_post.return_value = mock_response
        provider.generate("vllm-model", "return json", options={"json_schema": schema})

    payload = mock_post.call_args.kwargs["json"]
    assert payload["guided_json"] == schema["schema"]
    assert "response_format" not in payload
