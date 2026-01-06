"""Unit tests for refresh-stack.sh behavior (port conflict handling)."""

from pathlib import Path


def _script_text() -> str:
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "refresh-stack.sh"
    return script_path.read_text(encoding="utf-8")


def test_refresh_stack_checks_for_port_conflicts():
    content = _script_text()
    assert "Checking for port conflicts" in content


def test_refresh_stack_uses_docker_ps_ports():
    content = _script_text()
    assert "docker ps --format" in content
    assert ".Ports" in content


def test_refresh_stack_prompts_on_non_mnemosyne_conflict():
    content = _script_text()
    assert "Stop this container?" in content


def test_refresh_stack_logs_mnemosyne_conflicts():
    content = _script_text()
    assert "Stopping conflicting Mnemosyne container" in content


def test_refresh_stack_defaults_to_latest_without_runtime_tag():
    content = _script_text()
    assert "IMAGE_TAG_OVERRIDE" in content
    assert "IMAGE_TAG=" in content
    assert "latest" in content


def test_refresh_stack_uses_runtime_tag_snapshot():
    content = _script_text()
    assert "RUNTIME_IMAGE_TAG" in content


def test_refresh_stack_supports_prod_stack():
    content = _script_text()
    assert "prod" in content


def test_refresh_stack_reports_container_status():
    content = _script_text()
    assert "docker compose" in content
    assert "ps" in content


def test_refresh_stack_checks_watcher_processes_in_containers():
    content = _script_text()
    assert "docker exec" in content
    assert "pgrep" in content


def test_refresh_stack_uses_compose_project_name():
    content = _script_text()
    assert "COMPOSE_PROJECT_NAME" in content
