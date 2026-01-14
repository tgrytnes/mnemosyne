from pathlib import Path

import click

from mnemosyne.config.providers import ProviderConfig
from mnemosyne.providers.factory import create_embedding_provider, create_llm_provider


@click.group("config")
def config_cli():
    """Manage Mnemosyne provider configuration."""
    pass


@config_cli.command("show")
def show_config():
    """Display current provider configuration."""
    try:
        config = ProviderConfig.from_env()
        click.echo("Current Mnemosyne Provider Configuration:")
        click.echo(f"  Current LLM Profile: {config.llm_profile}")
        click.echo(f"  LLM Provider: {config.llm_provider}")
        click.echo(f"  Embedding Provider: {config.embedding_provider}")
        click.echo("-" * 20)
        click.echo("Provider Details:")
        if config.llm_provider == "ollama" or config.embedding_provider == "ollama":
            click.echo(f"  Ollama Base URL: {config.ollama_base_url}")
            click.echo(f"  Ollama LLM Model: {config.ollama_llm_model}")
            click.echo(f"  Ollama Embedding Model: {config.ollama_embedding_model}")
        if config.llm_provider == "groq":
            click.echo(f"  Groq API Key: {'*' * 8 if config.groq_api_key else 'Not Set'}")
            click.echo(f"  Groq LLM Model: {config.groq_llm_model}")
        if config.llm_provider == "fastapi" or config.embedding_provider == "fastapi":
            click.echo(f"  FastAPI Base URL: {config.fastapi_base_url}")
            click.echo(f"  FastAPI LLM Model: {config.fastapi_llm_model}")
            click.echo(f"  FastAPI Embedding Model: {config.fastapi_embedding_model}")
        if config.llm_provider == "vllm":
            click.echo(f"  vLLM Base URL: {config.vllm_base_url}")
            click.echo(f"  vLLM LLM Model: {config.vllm_llm_model}")
    except Exception as e:
        click.echo(f"Error reading configuration: {e}", err=True)


@config_cli.command("list-profiles")
def list_profiles():
    """List available configuration profiles."""
    profiles = ["local", "groq", "mac-metal"]
    click.echo("Available profiles:")
    for profile in profiles:
        click.echo(f"- {profile}")


def _update_env_file(key, value):
    env_file = Path.home() / ".config" / "mnemosyne" / ".env"
    if not env_file.parent.exists():
        env_file.parent.mkdir(parents=True)
    if not env_file.exists():
        env_file.touch()

    lines = env_file.read_text().splitlines()
    new_lines = []
    key_found = False
    for line in lines:
        if line.strip().startswith(f"{key}="):
            new_lines.append(f"{key}={value}")
            key_found = True
        else:
            new_lines.append(line)

    if not key_found:
        new_lines.append(f"{key}={value}")

    env_file.write_text("\n".join(new_lines))


@config_cli.command("set-profile")
@click.argument("profile")
def set_profile(profile: str):
    """Set the active LLM profile."""
    profiles = ["local", "groq", "mac-metal"]
    if profile not in profiles:
        click.echo(
            f"Error: Invalid profile '{profile}'. " f"Choose from: {', '.join(profiles)}",
            err=True,
        )
        return

    try:
        _update_env_file("LLM_PROFILE", profile)
        click.echo(f"LLM_PROFILE set to {profile} in ~/.config/mnemosyne/.env")
    except Exception as e:
        click.echo(f"Error updating config file: {e}", err=True)


@config_cli.command("set")
@click.argument("key")
@click.argument("value")
def set_value(key: str, value: str):
    """Set a specific configuration value."""
    try:
        _update_env_file(key.upper(), value)
        click.echo(f"{key.upper()} set to {value} in ~/.config/mnemosyne/.env")
    except Exception as e:
        click.echo(f"Error updating config file: {e}", err=True)


@config_cli.command("test-provider")
@click.argument("provider_name")
@click.option(
    "--embedding",
    is_flag=True,
    help="Test the embedding provider instead of the LLM provider.",
)
def test_provider(provider_name: str, embedding: bool):
    """Test connection to a specified provider."""
    try:
        if embedding:
            click.echo(f"Testing embedding provider: {provider_name}...")
            config = ProviderConfig(embedding_provider=provider_name)
            provider = create_embedding_provider(config)
            provider.embed(model="", text="test")
            click.echo(f"Successfully connected to {provider_name} embedding provider.")
        else:
            click.echo(f"Testing LLM provider: {provider_name}...")
            config = ProviderConfig(llm_provider=provider_name)
            provider = create_llm_provider(config)
            provider.generate(model="", prompt="test")
            click.echo(f"Successfully connected to {provider_name}.")

    except Exception as e:
        provider_type = " embedding provider" if embedding else ""
        click.echo(f"Failed to connect to {provider_name}{provider_type}: {e}", err=True)
        click.get_current_context().exit(1)
