"""
Unit tests for Story 034 scheduler jobs (gatekeeper + PM + Obsidian sync).
"""

from __future__ import annotations

import mnemosyne.cli.scheduler as scheduler


class _FakeConnection:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakePsycopg2:
    def __init__(self) -> None:
        self.connection = _FakeConnection()

    def connect(self, **_kwargs):
        return self.connection


class _FakeProposalQueue:
    def __init__(self, conn) -> None:
        self.conn = conn


class _FakeIntentQueue:
    def __init__(self, conn) -> None:
        self.conn = conn


class _FakeGatekeeper:
    called = False
    init_args = None

    def __init__(self, db_conn, proposal_queue, intent_queue, config=None) -> None:
        type(self).init_args = (db_conn, proposal_queue, intent_queue, config)

    def process_pending(self) -> dict[str, int]:
        type(self).called = True
        return {"auto_approved": 1, "awaiting_approval": 2, "rejected": 3}


class _FakeOutbox:
    def __init__(self, _path) -> None:
        self.path = _path

    def close(self) -> None:
        return None


class _FakeProjectManager:
    ran_check_cycle = False
    ran_pressure_update = False
    ran_intents = False
    init_args = None

    def __init__(self, db_conn, message_outbox, gatekeeper=None, intent_queue=None) -> None:
        type(self).init_args = {
            "db_conn": db_conn,
            "message_outbox": message_outbox,
            "gatekeeper": gatekeeper,
            "intent_queue": intent_queue,
        }

    def run_pm_check_cycle(self) -> None:
        type(self).ran_check_cycle = True

    def _update_pressure_scores(self) -> None:
        type(self).ran_pressure_update = True

    def process_intents(self, limit: int = 10) -> None:
        type(self).ran_intents = True


class _FakeSyncManager:
    synced_projects = None
    init_args = None

    def __init__(
        self,
        db_conn,
        vault_path: str,
        projects_folder: str = "Projects",
        sync_cooldown_seconds: int = 30,
        conflict_strategy: str = "sql_wins",
        dry_run: bool = False,
        gatekeeper=None,
    ) -> None:
        type(self).init_args = {
            "db_conn": db_conn,
            "vault_path": vault_path,
            "projects_folder": projects_folder,
            "sync_cooldown_seconds": sync_cooldown_seconds,
            "conflict_strategy": conflict_strategy,
            "dry_run": dry_run,
            "gatekeeper": gatekeeper,
        }

    def sync_all_projects_to_obsidian(self, projects):
        type(self).synced_projects = projects
        return [{"action": "updated"}]


def test_build_jobs_includes_story_034_tasks(monkeypatch):
    for var in (
        "CLUSTER_INTERVAL_HOURS",
        "SCOUT_INTERVAL_HOURS",
        "GRAPH_TAXONOMY_INTERVAL_HOURS",
        "MONITOR_INTERVAL_MINUTES",
        "GATEKEEPER_INTERVAL_MINUTES",
        "PM_CHECK_INTERVAL_MINUTES",
        "PM_PRESSURE_UPDATE_INTERVAL_HOURS",
        "PM_OBSIDIAN_SYNC_INTERVAL_MINUTES",
        "CLUSTER_ENABLED",
        "SCOUT_ENABLED",
        "GRAPH_TAXONOMY_ENABLED",
        "MONITOR_ENABLED",
        "GATEKEEPER_ENABLED",
        "PM_CHECK_ENABLED",
        "PM_PRESSURE_UPDATE_ENABLED",
        "PM_OBSIDIAN_SYNC_ENABLED",
    ):
        monkeypatch.delenv(var, raising=False)

    config = scheduler.SchedulerConfig()

    jobs = scheduler.build_jobs(config)
    job_map = {job.name: job for job in jobs}

    assert {
        "cluster",
        "scout",
        "graph_taxonomy",
        "monitor",
        "gatekeeper",
        "pm_check",
        "pm_pressure_update",
        "pm_obsidian_sync",
    }.issubset(job_map.keys())
    assert job_map["gatekeeper"].interval_seconds == config.gatekeeper_interval_minutes * 60
    assert job_map["pm_check"].interval_seconds == config.pm_check_interval_minutes * 60
    assert (
        job_map["pm_pressure_update"].interval_seconds
        == config.pm_pressure_update_interval_hours * 3600
    )
    assert (
        job_map["pm_obsidian_sync"].interval_seconds
        == config.pm_obsidian_sync_interval_minutes * 60
    )


def test_run_gatekeeper_task_processes_pending(monkeypatch):
    monkeypatch.setattr(scheduler, "psycopg2", _FakePsycopg2())
    monkeypatch.setattr(scheduler, "ProposalQueue", _FakeProposalQueue)
    monkeypatch.setattr(scheduler, "PMIntentQueue", _FakeIntentQueue)
    monkeypatch.setattr(scheduler, "SQLProjectGatekeeper", _FakeGatekeeper)

    result = scheduler.run_gatekeeper_task()

    assert _FakeGatekeeper.called is True
    assert result == {"auto_approved": 1, "awaiting_approval": 2, "rejected": 3}
    assert _FakeGatekeeper.init_args[0].closed is True


def test_run_pm_check_cycle_task_calls_agent(monkeypatch):
    monkeypatch.setenv("MESSAGE_OUTBOX_PATH", "message_outbox.db")
    monkeypatch.setattr(scheduler, "psycopg2", _FakePsycopg2())
    monkeypatch.setattr(scheduler, "MessageOutbox", _FakeOutbox)
    monkeypatch.setattr(scheduler, "ProposalQueue", _FakeProposalQueue)
    monkeypatch.setattr(scheduler, "PMIntentQueue", _FakeIntentQueue)
    monkeypatch.setattr(scheduler, "SQLProjectGatekeeper", _FakeGatekeeper)
    monkeypatch.setattr(scheduler, "ProjectManagerAgent", _FakeProjectManager)

    scheduler.run_pm_check_cycle_task()

    assert _FakeProjectManager.ran_check_cycle is True
    assert _FakeProjectManager.ran_intents is True
    assert _FakeProjectManager.init_args["db_conn"].closed is True


def test_run_pm_pressure_update_task_calls_agent(monkeypatch):
    monkeypatch.setenv("MESSAGE_OUTBOX_PATH", "message_outbox.db")
    monkeypatch.setattr(scheduler, "psycopg2", _FakePsycopg2())
    monkeypatch.setattr(scheduler, "MessageOutbox", _FakeOutbox)
    monkeypatch.setattr(scheduler, "ProposalQueue", _FakeProposalQueue)
    monkeypatch.setattr(scheduler, "PMIntentQueue", _FakeIntentQueue)
    monkeypatch.setattr(scheduler, "SQLProjectGatekeeper", _FakeGatekeeper)
    monkeypatch.setattr(scheduler, "ProjectManagerAgent", _FakeProjectManager)

    scheduler.run_pm_pressure_update_task()

    assert _FakeProjectManager.ran_pressure_update is True
    assert _FakeProjectManager.init_args["db_conn"].closed is True


def test_run_pm_obsidian_sync_task_syncs_projects(monkeypatch, tmp_path):
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    monkeypatch.setattr(scheduler, "psycopg2", _FakePsycopg2())
    monkeypatch.setattr(scheduler, "ObsidianSyncManager", _FakeSyncManager)

    projects = [
        {
            "id": 1,
            "title": "Project One",
            "description": "Test project",
            "discovered_by": "latent_scout",
            "discovery_id": "job:1",
            "cluster_ids": ["c1"],
            "confidence_score": 0.9,
            "status": "active",
            "importance": 3,
            "urgency": 4,
            "deadline": None,
            "work_estimate": None,
            "pressure_score": None,
            "verified_by_user": True,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-02T00:00:00Z",
            "obsidian_file_path": None,
            "last_synced_to_obsidian": None,
            "last_synced_from_obsidian": None,
        }
    ]

    monkeypatch.setattr(
        scheduler,
        "_fetch_projects_for_obsidian_sync",
        lambda _conn: projects,
    )

    result = scheduler.run_pm_obsidian_sync_task()

    assert _FakeSyncManager.synced_projects == projects
    assert result["projects_synced"] == 1
