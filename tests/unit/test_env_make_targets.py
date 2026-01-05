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
