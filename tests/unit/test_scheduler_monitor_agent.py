"""
Unit tests for scheduler monitor-agent wiring and env config.
"""

from __future__ import annotations

import mnemosyne.cli.scheduler as scheduler


class _FakeWeaviateClient:
    def __init__(self):
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakeWeaviateModule:
    def __init__(self):
        self.client = _FakeWeaviateClient()

    def connect_to_local(self, **_kwargs):
        return self.client


class _FakeConnection:
    def __init__(self):
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakePsycopg2:
    def __init__(self):
        self.connection = _FakeConnection()

    def connect(self, **_kwargs):
        return self.connection


class _FakeProposalQueue:
    def __init__(self, _conn):
        self._pending = [{"id": 1}, {"id": 2}]

    def list_by_status(self, status: str):
        if status == "pending":
            return self._pending
        return []


class _FakeStateStore:
    def __init__(self, _conn):
        pass


class _FakeOutbox:
    def __init__(self, _conn):
        pass


class _FakeReader:
    def __init__(self, _client):
        pass


class _FakeProjects:
    def __init__(self, _conn):
        pass


class _FakeAgent:
    def __init__(self, **kwargs):
        self.config = kwargs.get("config")

    def run(self) -> None:
        return None


def test_run_monitor_agent_task_reads_env(monkeypatch):
    monkeypatch.setenv("MONITOR_CONFIDENCE_THRESHOLD", "0.42")
    monkeypatch.setenv("MONITOR_SCAN_LIMIT", "123")

    monkeypatch.setattr(scheduler, "weaviate", _FakeWeaviateModule())
    monkeypatch.setattr(scheduler, "psycopg2", _FakePsycopg2())
    monkeypatch.setattr(scheduler, "ProposalQueue", _FakeProposalQueue)
    monkeypatch.setattr(scheduler, "MonitorStateStore", _FakeStateStore)
    monkeypatch.setattr(scheduler, "MessageOutbox", _FakeOutbox)
    monkeypatch.setattr(scheduler, "WeaviateDiscoveryReader", _FakeReader)
    monkeypatch.setattr(scheduler, "PostgresProjectRepository", _FakeProjects)
    monkeypatch.setattr(scheduler, "MonitorAgent", _FakeAgent)

    result = scheduler.run_monitor_agent_task()

    assert result["pending_proposals"] == 2
    assert result["config"].confidence_threshold == 0.42
    assert result["config"].scan_limit == 123

    monkeypatch.delenv("MONITOR_CONFIDENCE_THRESHOLD", raising=False)
    monkeypatch.delenv("MONITOR_SCAN_LIMIT", raising=False)
