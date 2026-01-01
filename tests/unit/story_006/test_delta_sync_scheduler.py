"""Unit tests for delta sync scheduler setup."""

from __future__ import annotations

from mnemosyne.argus.delta_sync import start_delta_sync_scheduler


class DummyNode:
    def __init__(self) -> None:
        self.calls = 0

    def run_once(self) -> None:
        self.calls += 1


def test_scheduler_registers_job() -> None:
    scheduler = start_delta_sync_scheduler(DummyNode(), interval_minutes=15)
    jobs = scheduler.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].trigger.interval.total_seconds() == 900
    scheduler.shutdown()
