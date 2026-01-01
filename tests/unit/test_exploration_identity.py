"""
Unit tests for radar exploration identity/dedup/state (Story 011).
"""

import json
from pathlib import Path

import pytest


def test_make_candidate_key_orders_cluster_ids():
    from mnemosyne.argus.scout.radar_explorer import make_candidate_key

    key = make_candidate_key(
        discovery_job_key="job-abc",
        cluster_ids=["cluster-b", "cluster-a"],
        link_type="weak_link",
    )
    assert key == "job-abc|cluster-a|cluster-b|weak_link"


def test_exploration_state_persists_and_skips(tmp_path: Path):
    from mnemosyne.argus.scout.radar_explorer import ExplorationState

    state_path = tmp_path / "exploration_state.json"
    state = ExplorationState(state_path)

    first_pairs = {("a", "b"), ("b", "c")}
    state.mark_explored(first_pairs)
    assert state.has_been_explored(("a", "b"))
    assert not state.has_been_explored(("a", "c"))

    # Persist to disk and reload to ensure incremental runs resume without reprocessing
    state.save()
    raw = json.loads(state_path.read_text())
    assert raw["explored_pairs"]

    resumed = ExplorationState(state_path)
    assert resumed.has_been_explored(("b", "a"))  # order-independent
    # Marking an already explored pair should be idempotent
    resumed.mark_explored({("b", "a")})
    resumed.save()
