import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration]


def _read_env_file(env_name: str) -> dict[str, str]:
    repo_root = Path(__file__).resolve().parents[2]
    env_file = repo_root / f".env.{env_name}"
    content = env_file.read_text(encoding="utf-8").splitlines()
    values: dict[str, str] = {}
    for line in content:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def _compose_config(env_name: str) -> subprocess.CompletedProcess:
    repo_root = Path(__file__).resolve().parents[2]
    env_file = repo_root / f".env.{env_name}"
    compose_file = repo_root / f"docker-compose.{env_name}.yml"

    assert env_file.exists(), f"Missing env file: {env_file}"
    assert compose_file.exists(), f"Missing compose override: {compose_file}"

    if shutil.which("docker") is None:
        pytest.skip("docker CLI not available")

    result = subprocess.run(
        [
            "docker",
            "compose",
            "-p",
            f"mnemosyne-{env_name}",
            "--env-file",
            str(env_file),
            "-f",
            "docker-compose.yml",
            "-f",
            str(compose_file),
            "config",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        env=os.environ.copy(),
    )
    return result


@pytest.mark.parametrize("env_name", ["dev", "staging", "prod"])
def test_compose_config_validates(env_name):
    result = _compose_config(env_name)
    assert result.returncode == 0, result.stderr
    assert "container_name" not in result.stdout


@pytest.mark.parametrize("env_name", ["dev", "staging", "prod"])
def test_env_file_contains_image_tag(env_name):
    values = _read_env_file(env_name)
    assert values.get("IMAGE_TAG") is not None


@pytest.mark.parametrize("env_name", ["dev", "staging", "prod"])
def test_env_file_contains_data_root(env_name):
    values = _read_env_file(env_name)
    assert values.get("DATA_ROOT") is not None


@pytest.mark.parametrize("env_name", ["dev", "staging", "prod"])
def test_compose_config_includes_data_root(env_name):
    values = _read_env_file(env_name)
    data_root = values.get("DATA_ROOT")
    assert data_root

    result = _compose_config(env_name)
    assert result.returncode == 0, result.stderr
    assert data_root in result.stdout
