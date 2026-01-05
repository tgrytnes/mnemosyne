"""
Unit tests for environment Makefile targets.
"""

from pathlib import Path


def test_makefile_has_env_targets():
    repo_root = Path(__file__).resolve().parents[2]
    makefile = repo_root / "Makefile"
    content = makefile.read_text(encoding="utf-8")

    required_targets = [
        "env-dev-up:",
        "env-staging-up:",
        "env-prod-up:",
        "env-down:",
        "env-status:",
    ]

    for target in required_targets:
        assert target in content, f"Missing Makefile target: {target}"


def test_makefile_references_local_env_files():
    repo_root = Path(__file__).resolve().parents[2]
    makefile = repo_root / "Makefile"
    content = makefile.read_text(encoding="utf-8")

    for env_name in ["dev", "staging", "prod"]:
        assert f".env.{env_name}.local" in content
    assert ".env.$(ENV).local" in content


def test_makefile_creates_local_env_files_when_missing():
    repo_root = Path(__file__).resolve().parents[2]
    makefile = repo_root / "Makefile"
    content = makefile.read_text(encoding="utf-8")

    for env_name in ["dev", "staging", "prod"]:
        assert f"touch .env.{env_name}.local" in content
    assert "touch .env.$(ENV).local" in content
