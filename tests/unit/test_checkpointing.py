"""
Unit tests for checkpointing storage.
"""

import tempfile
from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from mnemosyne.argus.checkpointing import CheckpointStore, ResearchState


class TestCheckpointStore:
    """Test save/load/delete and cleanup behavior."""

    def _make_state(self, query_id: str) -> ResearchState:
        return ResearchState(
            query_id=query_id,
            original_query="What is LangGraph?",
            current_node="search",
            conversation_history=[{"role": "user", "content": "Hi"}],
            intermediate_results=[{"step": "extract", "data": "notes"}],
            search_results=[{"title": "Result", "url": "https://example.com"}],
            synthesis_draft="Draft",
            metadata={"source": "test"},
        )

    def test_save_and_load_roundtrip(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            store = CheckpointStore(tmp.name)
            state = self._make_state("q-1")

            store.save(state)
            loaded = store.load("q-1")

            assert loaded is not None
            assert loaded.query_id == state.query_id
            assert loaded.current_node == "search"
            assert loaded.conversation_history == state.conversation_history
            assert loaded.intermediate_results == state.intermediate_results
            assert loaded.search_results == state.search_results
            assert loaded.metadata == state.metadata

            store.close()

    def test_delete_removes_checkpoint(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            store = CheckpointStore(tmp.name)
            state = self._make_state("q-2")
            store.save(state)

            store.delete("q-2")

            assert store.load("q-2") is None
            store.close()

    def test_cleanup_removes_old_entries(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            store = CheckpointStore(tmp.name)
            state = self._make_state("q-3")
            store.save(state)

            old_timestamp = (datetime.utcnow() - timedelta(days=31)).isoformat()
            store._conn.execute(
                f"UPDATE {store.table_name} SET updated_at = ? WHERE query_id = ?",
                (old_timestamp, "q-3"),
            )
            store._conn.commit()

            removed = store.cleanup(max_age_days=30)

            assert removed == 1
            assert store.load("q-3") is None
            store.close()

    def test_list_query_history_orders_by_timestamp(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            store = CheckpointStore(tmp.name)
            state_one = self._make_state("q-4")
            state_one.current_node = "semantic_extraction"
            store.save(state_one)

            state_two = self._make_state("q-4")
            state_two.current_node = "synthesis"
            store.save(state_two)

            update_sql = (
                f"UPDATE {store.table_name} SET updated_at = ? "
                "WHERE query_id = ? AND current_node = ?"
            )
            store._conn.execute(
                update_sql, ("2020-01-01T00:00:00", "q-4", "semantic_extraction")
            )
            store._conn.execute(update_sql, ("2020-01-02T00:00:00", "q-4", "synthesis"))
            store._conn.commit()

            history = store.list_query_history("q-4")
            assert [item.current_node for item in history] == [
                "semantic_extraction",
                "synthesis",
            ]
            store.close()

    def test_list_checkpoints_returns_latest_per_query(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            store = CheckpointStore(tmp.name)
            state_one = self._make_state("q-5")
            state_one.current_node = "search"
            store.save(state_one)

            state_two = self._make_state("q-5")
            state_two.current_node = "synthesis"
            store.save(state_two)

            update_sql = (
                f"UPDATE {store.table_name} SET updated_at = ? "
                "WHERE query_id = ? AND current_node = ?"
            )
            store._conn.execute(update_sql, ("2020-01-01T00:00:00", "q-5", "search"))
            store._conn.execute(update_sql, ("2020-01-02T00:00:00", "q-5", "synthesis"))
            store._conn.commit()

            checkpoints = store.list_checkpoints()
            assert len(checkpoints) == 1
            assert checkpoints[0].current_node == "synthesis"
            store.close()


def test_research_state_requires_query_id():
    with pytest.raises(ValidationError):
        ResearchState(
            query_id="",
            original_query="Missing id",
            current_node="start",
        )
