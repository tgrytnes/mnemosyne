"""
Unit tests for ignored local env files.
"""

from pathlib import Path


def test_gitignore_ignores_local_env_files():
    repo_root = Path(__file__).resolve().parents[2]
    gitignore = repo_root / ".gitignore"
    content = gitignore.read_text(encoding="utf-8")
    assert ".env.*.local" in content
