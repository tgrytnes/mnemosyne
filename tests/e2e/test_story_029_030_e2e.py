"""E2E tests for Story 029/030 unified conversation flow."""

from __future__ import annotations

import pytest

from mnemosyne.aletheia.agents.project_manager import ProjectManagerAgent
from mnemosyne.alexandria.communication_intents import PMIntentQueue
from mnemosyne.alexandria.message_outbox import MessageOutbox
from mnemosyne.alexandria.sql_gatekeeper import GatekeeperConfig, SQLProjectGatekeeper
from mnemosyne.alexandria.weaviate_schema import Discoveries, WeaviateSchemaManager
from mnemosyne.argus.scout.monitor_agent import (
    MonitorAgent,
    MonitorConfig,
    MonitorStateStore,
    PostgresProjectRepository,
    ProposalQueue,
    WeaviateDiscoveryReader,
)


@pytest.mark.e2e
@pytest.mark.weaviate
@pytest.mark.postgres
def test_story_029_030_approval_flow_end_to_end(
    tmp_path,
    weaviate_client,
    postgres_connection,
    ananke_test_db,
):
    if weaviate_client.collections.exists(Discoveries.collection_name):
        weaviate_client.collections.delete(Discoveries.collection_name)

    WeaviateSchemaManager(weaviate_client).ensure_collection_exists(Discoveries.collection_name)
    collection = weaviate_client.collections.get(Discoveries.collection_name)

    discovery_id = "private_projects:pm_flow"
    collection.data.insert(
        properties={
            "patternType": "project_candidate",
            "clusterIds": ["c1"],
            "confidenceScore": 0.75,
            "detectedAt": "2025-01-01T00:00:00Z",
            "discoveryId": discovery_id,
            "discoveryJobKey": "private_projects",
            "candidateKey": "pm_flow",
        },
        vector={"default": [0.1, 0.2]},
    )

    proposal_queue = ProposalQueue(postgres_connection)
    state_store = MonitorStateStore(postgres_connection)
    intent_queue = PMIntentQueue(postgres_connection)

    cursor = postgres_connection.cursor()
    cursor.execute("DELETE FROM proposal_queue")
    cursor.execute("DELETE FROM monitor_state")
    cursor.execute("DELETE FROM pm_intent_queue")
    postgres_connection.commit()

    reader = WeaviateDiscoveryReader(weaviate_client)
    projects = PostgresProjectRepository(postgres_connection)
    monitor = MonitorAgent(
        discovery_reader=reader,
        project_repository=projects,
        proposal_queue=proposal_queue,
        state_store=state_store,
        intent_queue=intent_queue,
        config=MonitorConfig(confidence_threshold=0.0),
    )

    monitor.run()
    proposals = proposal_queue.list_by_status("pending")
    assert proposals

    gatekeeper = SQLProjectGatekeeper(
        postgres_connection,
        proposal_queue,
        intent_queue,
        GatekeeperConfig(auto_reject_threshold=0.6, auto_approve_threshold=0.9),
    )
    gatekeeper.process_pending()

    intents = intent_queue.list_pending(limit=10)
    assert intents

    outbox = MessageOutbox(str(tmp_path / "outbox.db"))
    pm = ProjectManagerAgent(
        postgres_connection,
        outbox,
        gatekeeper=gatekeeper,
        intent_queue=intent_queue,
    )
    pm.process_intents(limit=10)

    pending = outbox.fetch_pending(limit=5)
    assert pending
    message = pending[0]

    outbox.mark_delivered(
        message.message_id,
        chat_id="chat-1",
        telegram_message_id=9001,
    )
    agent = outbox.record_response(
        context_id=message.context_id,
        response_data={"decision": "approve"},
    )
    assert agent == "project_manager"

    pm.handle_outbox_response(message.context_id, {"decision": "approve"})

    cursor.execute(
        "SELECT COUNT(*) FROM projects WHERE discovery_id = %s",
        (discovery_id,),
    )
    assert cursor.fetchone()[0] == 1
