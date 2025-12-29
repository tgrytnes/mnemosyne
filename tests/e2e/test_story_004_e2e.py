"""
E2E tests for Story 004 checkpointed knowledge.
"""

import tempfile
import time

import pytest
from fastapi.testclient import TestClient

from mnemosyne.api.app import create_app
from mnemosyne.argus.checkpointing import CheckpointStore, ResearchState
from mnemosyne.argus.research_graph import ResearchGraph


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


@pytest.mark.e2e
def test_story_004_resume_via_api():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        graph = ResearchGraph(checkpoint_db_path=tmp.name)
        graph.run(
            {
                "query_id": "api-1",
                "original_query": "Resume query",
                "current_node": "start",
            }
        )

        app = create_app(checkpoint_db_path=tmp.name)
        client = TestClient(app)

        response = client.get("/checkpoints/api-1")
        assert response.status_code == 200
        payload = response.json()
        assert payload["query_id"] == "api-1"
        assert payload["current_node"] == "synthesis"

        list_response = client.get("/checkpoints")
        assert list_response.status_code == 200
        assert any(item["query_id"] == "api-1" for item in list_response.json())

        delete_response = client.delete("/checkpoints/api-1")
        assert delete_response.status_code == 200

        missing = client.get("/checkpoints/api-1")
        assert missing.status_code == 404

        graph.close()
