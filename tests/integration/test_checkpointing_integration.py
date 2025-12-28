"""
Integration tests for checkpoint persistence.
"""

import tempfile

import pytest

from mnemosyne.argus.checkpointing import CheckpointStore, ResearchState


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
        store.close()
