from unittest.mock import MagicMock, patch

from mnemosyne.config.providers import ProviderConfig
from mnemosyne.providers.tabbyapi import TabbyAPILLMProvider


def _mock_chat_response(content: str) -> MagicMock:
    mock_response = MagicMock()
    mock_response.json.return_value = {"choices": [{"message": {"content": content}}]}
    return mock_response


def test_tabbyapi_supports_structured_output():
    config = ProviderConfig(tabbyapi_base_url="http://tabby.local")
    provider = TabbyAPILLMProvider(config)
    assert provider.supports_structured_output() is True


def test_tabbyapi_generate_basic_request():
    config = ProviderConfig(
        tabbyapi_base_url="http://tabby.local", tabbyapi_llm_model="tabby-model"
    )
    provider = TabbyAPILLMProvider(config)

    with patch("mnemosyne.providers.tabbyapi.requests.post") as mock_post:
        mock_post.return_value = _mock_chat_response("hello")
        response = provider.generate("tabby-model", "test prompt")

    assert response["response"] == "hello"
    payload = mock_post.call_args.kwargs["json"]
    assert payload["model"] == "tabby-model"
    assert payload["messages"] == [{"role": "user", "content": "test prompt"}]
    assert "response_format" not in payload


def test_tabbyapi_generate_json_schema_wraps_name():
    config = ProviderConfig(
        tabbyapi_base_url="http://tabby.local", tabbyapi_llm_model="tabby-model"
    )
    provider = TabbyAPILLMProvider(config)
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}

    with patch("mnemosyne.providers.tabbyapi.requests.post") as mock_post:
        mock_post.return_value = _mock_chat_response('{"ok": true}')
        provider.generate("tabby-model", "return ok", options={"json_schema": schema})

    response_format = mock_post.call_args.kwargs["json"]["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["name"] == "response"
    assert response_format["json_schema"]["schema"] == schema


def test_tabbyapi_generate_json_schema_keeps_named_schema():
    config = ProviderConfig(
        tabbyapi_base_url="http://tabby.local", tabbyapi_llm_model="tabby-model"
    )
    provider = TabbyAPILLMProvider(config)
    schema = {
        "name": "semantic_boundaries",
        "schema": {"type": "object", "properties": {"boundaries": {"type": "array"}}},
    }

    with patch("mnemosyne.providers.tabbyapi.requests.post") as mock_post:
        mock_post.return_value = _mock_chat_response('{"boundaries": []}')
        provider.generate("tabby-model", "return boundaries", options={"json_schema": schema})

    response_format = mock_post.call_args.kwargs["json"]["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"] == schema
