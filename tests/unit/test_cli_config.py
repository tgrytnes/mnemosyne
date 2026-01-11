from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

# To be created import
from mnemosyne.cli.config import config_cli


@pytest.fixture
def runner():
    return CliRunner()


def test_config_show(runner):
    with patch("mnemosyne.cli.config.ProviderConfig") as mock_config:
        mock_instance = mock_config.from_env.return_value
        mock_instance.llm_profile = "test_profile"
        mock_instance.llm_provider = "ollama"
        mock_instance.embedding_provider = "test_embedding_provider"
        mock_instance.ollama_base_url = "http://test_url"

        result = runner.invoke(config_cli, ["show"])
        assert result.exit_code == 0
        assert "Current LLM Profile: test_profile" in result.output
        assert "LLM Provider: ollama" in result.output
        assert "Embedding Provider: test_embedding_provider" in result.output
        assert "Ollama Base URL: http://test_url" in result.output


def test_config_list_profiles(runner):
    result = runner.invoke(config_cli, ["list-profiles"])
    assert result.exit_code == 0
    assert "local" in result.output
    assert "groq" in result.output
    assert "mac-metal" in result.output


@patch("pathlib.Path.home")
def test_config_set_profile(mock_home, runner):
    mock_home.return_value.joinpath.return_value.exists.return_value = True
    with patch("builtins.open", new_callable=MagicMock()):
        result = runner.invoke(config_cli, ["set-profile", "groq"])
        assert result.exit_code == 0
        assert "LLM_PROFILE set to groq" in result.output


@patch("pathlib.Path.home")
def test_config_set(mock_home, runner):
    mock_home.return_value.joinpath.return_value.exists.return_value = True
    with patch("builtins.open", new_callable=MagicMock()):
        result = runner.invoke(config_cli, ["set", "GROQ_API_KEY", "new_key"])
        assert result.exit_code == 0
        assert "GROQ_API_KEY set to new_key" in result.output


@patch("mnemosyne.cli.config.create_llm_provider")
def test_config_test_provider_llm_success(mock_create, runner):
    mock_provider = MagicMock()
    mock_provider.generate.return_value = {"response": "Success"}
    mock_create.return_value = mock_provider

    result = runner.invoke(config_cli, ["test-provider", "ollama"])
    assert result.exit_code == 0
    assert "Successfully connected to ollama" in result.output


@patch("mnemosyne.cli.config.create_llm_provider")
def test_config_test_provider_llm_failure(mock_create, runner):
    mock_create.side_effect = Exception("Connection error")

    result = runner.invoke(config_cli, ["test-provider", "ollama"])
    assert result.exit_code == 1
    assert "Failed to connect to ollama" in result.output


@patch("mnemosyne.cli.config.create_embedding_provider")
def test_config_test_provider_embedding_success(mock_create, runner):
    mock_provider = MagicMock()
    mock_provider.embed.return_value = [1.0, 2.0]
    mock_create.return_value = mock_provider

    result = runner.invoke(config_cli, ["test-provider", "ollama", "--embedding"])
    assert result.exit_code == 0
    assert "Successfully connected to ollama embedding provider" in result.output


@patch("mnemosyne.cli.config.create_embedding_provider")
def test_config_test_provider_embedding_failure(mock_create, runner):
    mock_create.side_effect = Exception("Connection error")

    result = runner.invoke(config_cli, ["test-provider", "ollama", "--embedding"])
    assert result.exit_code == 1
    assert "Failed to connect to ollama embedding provider" in result.output
