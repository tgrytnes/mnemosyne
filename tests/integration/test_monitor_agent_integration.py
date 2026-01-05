"""
Integration tests for Monitor Agent with real services.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from mnemosyne.alexandria.weaviate_schema import Discoveries, WeaviateSchemaManager
from mnemosyne.argus.scout.monitor_agent import (
    MonitorAgent,
    MonitorConfig,
    MonitorStateStore,
    PostgresProjectRepository,
    ProposalQueue,
    WeaviateDiscoveryReader,
)


class _InMemoryOutbox:
    def __init__(self):
        self.messages: list[dict[str, str]] = []

    def enqueue(self, message_type: str, payload: dict, message_id: str) -> None:
        self.messages.append(
            {
                "message_type": message_type,
                "message_id": message_id,
            }
        )


@pytest.mark.integration
@pytest.mark.weaviate
@pytest.mark.postgres
def test_monitor_creates_proposal_from_weaviate_discovery(
    weaviate_client, postgres_connection, ananke_test_db
):
    if weaviate_client.collections.exists(Discoveries.collection_name):
        weaviate_client.collections.delete(Discoveries.collection_name)

    WeaviateSchemaManager(weaviate_client).ensure_collection_exists(Discoveries.collection_name)
    collection = weaviate_client.collections.get(Discoveries.collection_name)

    discovery_id = "private_projects:house_painting"
    collection.data.insert(
        properties={
            "patternType": "project_candidate",
            "clusterIds": ["c1"],
            "confidenceScore": 0.82,
            "detectedAt": datetime.now(UTC),
            "discoveryId": discovery_id,
            "discoveryJobKey": "private_projects",
            "candidateKey": "house_painting",
        },
        vector=[0.1, 0.2],
    )

    proposal_queue = ProposalQueue(postgres_connection)
    state_store = MonitorStateStore(postgres_connection)
    cursor = postgres_connection.cursor()
    cursor.execute("DELETE FROM proposal_queue")
    cursor.execute("DELETE FROM monitor_state")
    postgres_connection.commit()
    outbox = _InMemoryOutbox()

    reader = WeaviateDiscoveryReader(weaviate_client)
    projects = PostgresProjectRepository(postgres_connection)
    agent = MonitorAgent(
        discovery_reader=reader,
        project_repository=projects,
        proposal_queue=proposal_queue,
        state_store=state_store,
        outbox=outbox,
        config=MonitorConfig(confidence_threshold=0.7),
    )

    agent.run()

    proposal = proposal_queue.get_by_discovery_id(discovery_id)
    assert proposal is not None
    assert proposal["status"] == "pending"
    assert proposal["discovery_job_key"] == "private_projects"
    assert proposal["candidate_key"] == "house_painting"
