"""
E2E tests for Story 004 - Checkpointed Knowledge with REAL SQLite + LangGraph.
"""

import json
import os
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from mnemosyne.aletheia.ingestion_state import IngestionStateTracker
from mnemosyne.aletheia.obsidian_ingestor import ObsidianIngestor
from mnemosyne.argus.research_graph import ResearchGraph
from mnemosyne.config.providers import ProviderConfig
from mnemosyne.providers.factory import create_embedding_provider, create_llm_provider


def _run_cli(args: list[str], db_path: Path) -> str:
    repo_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["CHECKPOINT_DB_PATH"] = str(db_path)
    env["PYTHONPATH"] = os.pathsep.join([str(repo_root / "src"), env.get("PYTHONPATH", "")]).strip(
        os.pathsep
    )

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
            ((datetime.now(UTC) - timedelta(days=31)).isoformat(), "e2e-004-old"),
        )
        conn.commit()

    cleanup_output = _run_cli(["cleanup", "--max-age-days", "30"], db_path)
    removed_match = cleanup_output.split("Removed ")[-1].split(" checkpoints")[0]
    removed_count = int(removed_match) if removed_match.isdigit() else 0
    assert removed_count >= 1

    list_output = _run_cli(["list"], db_path)
    assert "e2e-004-old" not in list_output


@pytest.mark.e2e
@pytest.mark.weaviate
def test_story_004_system_resume_with_real_services(
    tmp_path: Path,
    weaviate_client,
    fake_vault_path: Path,
    clean_weaviate_collection,
):
    """
    REAL E2E TEST: Ingest real vault data, run checkpointed graph, then resume.
    """
    state_tracker = IngestionStateTracker(str(tmp_path / "ingestion_state.db"))

    config = ProviderConfig(
        llm_provider="ollama",
        llm_model="qwen3:0.6b",
        embedding_provider="ollama",
        embedding_model="nomic-embed-text:latest",
        ollama_base_url="http://localhost:11434",
    )
    llm_provider = create_llm_provider(config)
    embedding_provider = create_embedding_provider(config)

    ingestor = ObsidianIngestor(
        vault_path=str(fake_vault_path),
        weaviate_client=weaviate_client,
        llm_provider=llm_provider,
        embedding_provider=embedding_provider,
        state_tracker=state_tracker,
        chunking_strategy="recursive",
        chunk_size=400,
        chunk_overlap=100,
    )

    stats = ingestor.ingest_vault()
    assert stats["total_chunks"] > 0

    collection = weaviate_client.collections.get("TheMuses")
    results = collection.query.fetch_objects(limit=1)
    assert results.objects, "No chunks stored in TheMuses"

    props = results.objects[0].properties
    source_file = props.get("sourceFile")
    chunk_index = props.get("chunkIndex")
    chunk_text = props.get("text")

    assert source_file
    assert chunk_index is not None
    assert chunk_text

    db_path = tmp_path / "checkpoints.db"
    graph = ResearchGraph(checkpoint_db_path=str(db_path))
    query_id = "e2e-004-system"
    state = {
        "query_id": query_id,
        "original_query": f"Resume notes from {source_file}",
        "current_node": "start",
        "conversation_history": [{"role": "user", "content": "Start"}],
        "intermediate_results": [{"source_file": source_file, "text": chunk_text[:200]}],
        "search_results": [{"source_file": source_file, "chunk_index": chunk_index}],
    }
    graph.run(state)
    graph.close()
    state_tracker.close()

    resume_output = _run_cli(["resume", query_id], db_path)
    resumed = json.loads(resume_output)

    assert resumed["current_node"] == "synthesis"
    assert any(item.get("source_file") == source_file for item in resumed["intermediate_results"])
    assert any(item.get("chunk_index") == chunk_index for item in resumed["search_results"])
