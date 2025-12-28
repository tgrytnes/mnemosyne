"""
E2E tests for Story 004 checkpointed knowledge.
"""

import tempfile
import time

import pytest

from mnemosyne.argus.checkpointing import CheckpointStore, ResearchState


@pytest.mark.e2e
def test_story_004_resume_flow_under_latency_target():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        store = CheckpointStore(tmp.name)
        state = ResearchState(
            query_id="resume-2",
            original_query="Resume my research",
            current_node="semantic_extraction",
            conversation_history=[{"role": "user", "content": "Resume"}],
        )

        start_save = time.monotonic()
        store.save(state)
        save_time = time.monotonic() - start_save

        start_load = time.monotonic()
        loaded = store.load("resume-2")
        load_time = time.monotonic() - start_load

        assert loaded is not None
        assert loaded.current_node == "semantic_extraction"
        assert save_time < 0.5
        assert load_time < 0.5

        store.close()
