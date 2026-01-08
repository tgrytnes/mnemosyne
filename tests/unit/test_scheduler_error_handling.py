"""Unit tests for standardized scheduler task error handling."""

from __future__ import annotations

import pytest

import mnemosyne.cli.scheduler as scheduler


class _FakeClusterConfig:
    n_clusters_muses = 2
    n_clusters_lethe = 3


def test_run_clustering_task_propagates_errors(monkeypatch):
    def _boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(scheduler, "run_clustering", _boom)
    monkeypatch.setattr(scheduler, "ClusteringConfig", _FakeClusterConfig)

    with pytest.raises(RuntimeError, match="boom"):
        scheduler.run_clustering_task()
