import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration]


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
    repo_root = Path(__file__).resolve().parents[2]
    env_file = repo_root / f".env.{env_name}"
    content = env_file.read_text(encoding="utf-8")
    assert "IMAGE_TAG=" in content
