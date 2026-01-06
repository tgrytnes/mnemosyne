"""
Unit tests for scheduler/ingestor operational controls.
"""

from pathlib import Path

import mnemosyne.cli.ingest as ingest
import mnemosyne.cli.scheduler as scheduler


def test_scheduler_enabled_env_flag(monkeypatch):
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    assert scheduler.is_scheduler_enabled() is False


def test_ingestor_watch_enabled_env_flag(monkeypatch):
    monkeypatch.setenv("INGESTOR_WATCH_ENABLED", "false")
    assert ingest.is_watch_enabled() is False


def test_dockerfiles_include_procps():
    repo_root = Path(__file__).resolve().parents[2]
    dockerfile = (repo_root / "Dockerfile").read_text(encoding="utf-8")
    dockerfile_release = (repo_root / "Dockerfile.release").read_text(encoding="utf-8")

    assert "procps" in dockerfile
    assert "procps" in dockerfile_release


def test_compose_healthchecks_for_scheduler_ingestor():
    repo_root = Path(__file__).resolve().parents[2]
    compose = (repo_root / "docker-compose.yml").read_text(encoding="utf-8")

    assert "mnemosyne_ingestor" in compose
    assert "mnemosyne_scheduler" in compose
    assert "healthcheck" in compose
    assert "mnemosyne.cli.ingest watch" in compose
    assert "mnemosyne.cli.scheduler" in compose


def test_start_ingestion_respects_watch_flag():
    repo_root = Path(__file__).resolve().parents[2]
    script = (repo_root / "scripts" / "start_ingestion.sh").read_text(encoding="utf-8")
    assert "INGESTOR_WATCH_ENABLED" in script
