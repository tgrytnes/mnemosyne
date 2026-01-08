"""Unit tests for Story 034 periodic scheduler orchestration."""

from __future__ import annotations

from datetime import datetime, timedelta

import mnemosyne.cli.scheduler as scheduler


class _FakeClock:
    def __init__(self, now: datetime):
        self._now = now

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> None:
        self._now = self._now + delta


def test_scheduler_config_defaults(monkeypatch):
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

    assert config.cluster_interval_hours == 24
    assert config.scout_interval_hours == 24
    assert config.graph_taxonomy_interval_hours == 24
    assert config.monitor_interval_minutes == 60
    assert config.gatekeeper_interval_minutes == 60
    assert config.pm_check_interval_minutes == 30
    assert config.pm_pressure_update_interval_hours == 1
    assert config.pm_obsidian_sync_interval_minutes == 15
    assert config.cluster_enabled is True
    assert config.scout_enabled is True
    assert config.graph_taxonomy_enabled is True
    assert config.monitor_enabled is True
    assert config.gatekeeper_enabled is True
    assert config.pm_check_enabled is True
    assert config.pm_pressure_update_enabled is True
    assert config.pm_obsidian_sync_enabled is True


def test_scheduler_config_env_overrides(monkeypatch):
    monkeypatch.setenv("CLUSTER_INTERVAL_HOURS", "12")
    monkeypatch.setenv("MONITOR_INTERVAL_MINUTES", "5")
    monkeypatch.setenv("PM_CHECK_INTERVAL_MINUTES", "10")
    monkeypatch.setenv("SCOUT_ENABLED", "false")

    config = scheduler.SchedulerConfig()

    assert config.cluster_interval_hours == 12
    assert config.monitor_interval_minutes == 5
    assert config.pm_check_interval_minutes == 10
    assert config.scout_enabled is False


def test_periodic_scheduler_runs_due_jobs():
    ran: list[str] = []

    def job_a() -> None:
        ran.append("a")

    def job_b() -> None:
        ran.append("b")

    clock = _FakeClock(datetime(2025, 1, 1, 0, 0, 0))
    jobs = [
        scheduler.JobSpec("a", interval_seconds=60, enabled=True, run=job_a),
        scheduler.JobSpec("b", interval_seconds=120, enabled=True, run=job_b),
    ]

    runner = scheduler.PeriodicScheduler(jobs=jobs, now_provider=clock.now)
    runner.run_once()

    assert ran == ["a", "b"]

    runner.run_once()
    assert ran == ["a", "b"]

    clock.advance(timedelta(seconds=61))
    runner.run_once()
    assert ran == ["a", "b", "a"]

    clock.advance(timedelta(seconds=60))
    runner.run_once()
    assert ran == ["a", "b", "a", "b"]


def test_periodic_scheduler_skips_disabled_jobs():
    ran: list[str] = []

    def job_a() -> None:
        ran.append("a")

    jobs = [scheduler.JobSpec("a", interval_seconds=60, enabled=False, run=job_a)]
    runner = scheduler.PeriodicScheduler(jobs=jobs, now_provider=lambda: datetime(2025, 1, 1))
    runner.run_once()

    assert ran == []


def test_periodic_scheduler_isolates_failures():
    ran: list[str] = []

    def job_fail() -> None:
        raise RuntimeError("boom")

    def job_ok() -> None:
        ran.append("ok")

    runner = scheduler.PeriodicScheduler(
        jobs=[
            scheduler.JobSpec("fail", interval_seconds=60, enabled=True, run=job_fail),
            scheduler.JobSpec("ok", interval_seconds=60, enabled=True, run=job_ok),
        ],
        now_provider=lambda: datetime(2025, 1, 1, 0, 0, 0),
    )

    runner.run_once()

    assert ran == ["ok"]


def test_periodic_scheduler_prevents_reentry():
    ran: list[str] = []

    def job_run() -> None:
        ran.append("run")
        if len(ran) == 1:
            runner.run_once()

    runner = scheduler.PeriodicScheduler(
        jobs=[scheduler.JobSpec("job", interval_seconds=60, enabled=True, run=job_run)],
        now_provider=lambda: datetime(2025, 1, 1, 0, 0, 0),
    )

    runner.run_once()

    assert ran == ["run"]
