"""
E2E tests for Story 004 - Checkpointed Knowledge with REAL SQLite + LangGraph.
"""

import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from mnemosyne.argus.research_graph import ResearchGraph


def _run_cli(args: list[str], db_path: Path) -> str:
    repo_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["CHECKPOINT_DB_PATH"] = str(db_path)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(repo_root / "src"), env.get("PYTHONPATH", "")]
    ).strip(os.pathsep)

    result = subprocess.run(
        [sys.executable, "-m", "mnemosyne.cli.checkpoints", *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@pytest.mark.e2e
def test_story_004_resume_flow_with_real_sqlite(tmp_path: Path):
    """
    REAL E2E TEST: Run LangGraph, then resume via CLI from persisted checkpoints.
    """
    db_path = tmp_path / "checkpoints.db"

    graph = ResearchGraph(checkpoint_db_path=str(db_path))
    state = {
        "query_id": "e2e-004",
        "original_query": "Summarize recent research",
        "current_node": "start",
        "conversation_history": [{"role": "user", "content": "Start"}],
    }
    graph.run(state)
    graph.close()

    list_output = _run_cli(["list"], db_path)
    assert "e2e-004" in list_output

    resume_output = _run_cli(["resume", "e2e-004"], db_path)
    resumed = json.loads(resume_output)

    assert resumed["current_node"] == "synthesis"
    assert resumed["conversation_history"]
    assert resumed["intermediate_results"]
    assert resumed["search_results"]
    assert resumed["synthesis_draft"]

    _run_cli(["delete", "e2e-004"], db_path)
    list_after_delete = _run_cli(["list"], db_path)
    assert "e2e-004" not in list_after_delete


@pytest.mark.e2e
def test_story_004_cleanup_removes_old_checkpoints(tmp_path: Path):
    """
    REAL E2E TEST: Cleanup job removes checkpoints older than 30 days.
    """
    db_path = tmp_path / "checkpoints.db"

    graph = ResearchGraph(checkpoint_db_path=str(db_path))
    state = {
        "query_id": "e2e-004-old",
        "original_query": "Cleanup test",
        "current_node": "start",
        "conversation_history": [{"role": "user", "content": "Old"}],
    }
    graph.run(state)
    graph.close()

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE mnemosyne_checkpoints SET updated_at = ? WHERE query_id = ?",
            ((datetime.utcnow() - timedelta(days=31)).isoformat(), "e2e-004-old"),
        )
        conn.commit()

    cleanup_output = _run_cli(["cleanup", "--max-age-days", "30"], db_path)
    removed_match = cleanup_output.split("Removed ")[-1].split(" checkpoints")[0]
    removed_count = int(removed_match) if removed_match.isdigit() else 0
    assert removed_count >= 1

    list_output = _run_cli(["list"], db_path)
    assert "e2e-004-old" not in list_output
