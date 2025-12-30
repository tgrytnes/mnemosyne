"""
Integration tests for checkpoint persistence.
"""

import time
import tempfile
from pathlib import Path

import pytest

from mnemosyne.argus.checkpointing import CheckpointStore, ResearchState
from mnemosyne.argus.research_graph import ResearchGraph


@pytest.mark.integration
def test_checkpoint_persistence_across_store_instances():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        state = ResearchState(
            query_id="resume-1",
            original_query="Find research notes",
            current_node="extract",
            conversation_history=[{"role": "user", "content": "Start"}],
            metadata={"iteration": 1},
        )

        store = CheckpointStore(tmp.name)
        store.save(state)
        store.close()

        new_store = CheckpointStore(tmp.name)
        loaded = new_store.load("resume-1")

        assert loaded is not None
        assert loaded.current_node == "extract"
        new_store.close()


@pytest.mark.integration
def test_list_checkpoints_returns_recent_first():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        store = CheckpointStore(tmp.name)
        store.save(
            ResearchState(
                query_id="q-1",
                original_query="A",
                current_node="node-1",
            )
        )
        store.save(
            ResearchState(
                query_id="q-2",
                original_query="B",
                current_node="node-2",
            )
        )

        results = store.list_checkpoints()
        assert results[0].query_id == "q-2"
        assert results[0].current_node == "node-2"
        store.close()


@pytest.mark.integration
def test_langgraph_persists_key_nodes():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        graph = ResearchGraph(checkpoint_db_path=tmp.name)
        state = {
            "query_id": "graph-1",
            "original_query": "Find notes",
            "current_node": "start",
            "conversation_history": [{"role": "user", "content": "Start"}],
        }

        graph.run(state)

        history = graph.store.list_query_history("graph-1")
        nodes = [item.current_node for item in history]

        assert nodes == ["semantic_extraction", "search", "synthesis"]
        assert graph.langgraph_db_path
        assert Path(graph.langgraph_db_path).exists()
        graph.close()


@pytest.mark.integration
def test_graph_resume_returns_latest_state():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        graph = ResearchGraph(checkpoint_db_path=tmp.name)
        state = {
            "query_id": "graph-2",
            "original_query": "Resume test",
            "current_node": "start",
            "conversation_history": [{"role": "user", "content": "Resume"}],
        }

        graph.run(state)
        resumed = graph.resume("graph-2")

        assert resumed is not None
        assert resumed.current_node == "synthesis"
        assert resumed.conversation_history
        assert resumed.search_results
        graph.close()


@pytest.mark.performance
def test_checkpoint_save_load_under_threshold():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        store = CheckpointStore(tmp.name)
        state = ResearchState(
            query_id="perf-1",
            original_query="Perf check",
            current_node="search",
            conversation_history=[{"role": "user", "content": "Ping"}],
        )

        start = time.monotonic()
        store.save(state)
        loaded = store.load("perf-1")
        elapsed = time.monotonic() - start

        assert loaded is not None
        assert elapsed < 0.5, f"Checkpoint save/load took {elapsed:.3f}s"
        store.close()
