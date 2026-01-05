"""
Unit tests for compose env overrides.
"""

from pathlib import Path


def test_compose_overrides_reference_local_env_files():
    repo_root = Path(__file__).resolve().parents[2]

    for env_name in ["dev", "staging", "prod"]:
        compose_file = repo_root / f"docker-compose.{env_name}.yml"
        content = compose_file.read_text(encoding="utf-8")
        assert f".env.{env_name}.local" in content
