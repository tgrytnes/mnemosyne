"""
Unit tests for Monitor CLI env configuration.
"""

from mnemosyne.cli.monitor import MonitorCLIConfig


def test_monitor_cli_config_reads_env(monkeypatch, tmp_path):
    monkeypatch.setenv("MONITOR_CONFIDENCE_THRESHOLD", "0.55")
    monkeypatch.setenv("MONITOR_SCAN_LIMIT", "150")
    monkeypatch.setenv("MONITOR_COOLDOWN_DAYS", "10")
    monkeypatch.setenv("MONITOR_MAX_ASKS", "2")
    monkeypatch.setenv("MONITOR_CONFIDENCE_DELTA", "0.2")
    monkeypatch.setenv("MONITOR_QUEUE_DB_PATH", str(tmp_path / "queue.db"))
    monkeypatch.setenv("MONITOR_STATE_DB_PATH", str(tmp_path / "state.db"))
    monkeypatch.setenv("MONITOR_OUTBOX_DB_PATH", str(tmp_path / "outbox.db"))
    monkeypatch.setenv("WEAVIATE_HTTP_HOST", "weaviate")
    monkeypatch.setenv("WEAVIATE_HTTP_PORT", "9090")
    monkeypatch.setenv("WEAVIATE_GRPC_PORT", "50052")
    monkeypatch.setenv("POSTGRES_HOST", "postgres")
    monkeypatch.setenv("POSTGRES_PORT", "5440")
    monkeypatch.setenv("POSTGRES_DB", "ananke_test")
    monkeypatch.setenv("POSTGRES_USER", "test_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")

    config = MonitorCLIConfig()

    assert config.confidence_threshold == 0.55
    assert config.scan_limit == 150
    assert config.cooldown_days == 10
    assert config.max_asks == 2
    assert config.confidence_delta == 0.2
    assert config.queue_db_path == str(tmp_path / "queue.db")
    assert config.state_db_path == str(tmp_path / "state.db")
    assert config.outbox_db_path == str(tmp_path / "outbox.db")
    assert config.weaviate_host == "weaviate"
    assert config.weaviate_port == 9090
    assert config.weaviate_grpc_port == 50052
    assert config.postgres_host == "postgres"
    assert config.postgres_port == 5440
    assert config.postgres_db == "ananke_test"
    assert config.postgres_user == "test_user"
    assert config.postgres_password == "test_password"
