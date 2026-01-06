"""Unit tests for environment isolation config (compose project + data roots)."""

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _env_text(name: str) -> str:
    return (_repo_root() / f".env.{name}").read_text(encoding="utf-8")


def test_env_files_define_compose_project_name():
    for name in ("dev", "staging", "prod"):
        content = _env_text(name)
        assert "COMPOSE_PROJECT_NAME=" in content


def test_env_files_use_expected_data_root_paths():
    expected = {
        "dev": "/home/tgrytnes/projects/Mnemosyne/data/dev",
        "staging": "/home/tgrytnes/projects/Mnemosyne/data/staging",
        "prod": "/home/tgrytnes/projects/Mnemosyne/data/prod",
    }
    for name, path in expected.items():
        content = _env_text(name)
        assert f"DATA_ROOT={path}" in content


def test_env_compose_files_avoid_fixed_container_names():
    repo_root = _repo_root()
    compose_files = [
        "docker-compose.yml",
        "docker-compose.dev.yml",
        "docker-compose.staging.yml",
        "docker-compose.prod.yml",
    ]
    for filename in compose_files:
        path = repo_root / filename
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        assert "container_name:" not in content
