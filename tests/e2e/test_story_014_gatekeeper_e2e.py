"""E2E for Story 014: SQL Project Gatekeeper with real Postgres and queue/outbox."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from mnemosyne.alexandria.communication_intents import PMIntentQueue
from mnemosyne.alexandria.sql_gatekeeper import GatekeeperConfig, SQLProjectGatekeeper
from mnemosyne.argus.scout.monitor_agent import DiscoveryRecord, ProposalQueue


def _make_record(discovery_id: str, confidence: float, cluster_ids: list[str]) -> DiscoveryRecord:
    return DiscoveryRecord(
        discovery_id=discovery_id,
        discovery_job_key="job-e2e",
        candidate_key=discovery_id,
        pattern_type="project_candidate",
        cluster_ids=cluster_ids,
        confidence_score=confidence,
        detected_at=datetime.now(UTC),
        title="E2E Project",
        description="End-to-end project candidate",
    )


def _reset_gatekeeper_tables(postgres_connection) -> None:
    cursor = postgres_connection.cursor()
    cursor.execute("DELETE FROM proposal_queue")
    cursor.execute("DELETE FROM pm_intent_queue")
    postgres_connection.commit()


@pytest.mark.e2e
@pytest.mark.postgres
def test_story_014_gatekeeper_auto_approve_and_rollback(postgres_connection, ananke_test_db):
    queue = ProposalQueue(postgres_connection)
    intent_queue = PMIntentQueue(postgres_connection)
    _reset_gatekeeper_tables(postgres_connection)
    gatekeeper = SQLProjectGatekeeper(
        postgres_connection,
        queue,
        intent_queue,
        GatekeeperConfig(
            auto_reject_threshold=0.6,
            auto_approve_threshold=0.9,
            rollback_window_days=30,
        ),
    )

    record = _make_record("disc-e2e", 0.95, ["101"])
    queue.upsert(record)

    result = gatekeeper.process_pending()
    assert result["auto_approved"] == 1
    assert not intent_queue.list_pending(
        limit=5
    ), "Auto-approved path should not enqueue approval intents"

    cur = postgres_connection.cursor()
    cur.execute(
        "SELECT id, title, verified_by_user FROM projects WHERE discovery_id = %s",
        (record.discovery_id,),
    )
    row = cur.fetchone()
    assert row is not None
    project_id, title, verified = row
    assert "Project" in title
    assert verified is True
    assert queue.list_by_status("approved")

    token = gatekeeper.request_rollback(project_id)
    gatekeeper.confirm_rollback(project_id, token)
    cur.execute("SELECT COUNT(*) FROM projects WHERE id = %s", (project_id,))
    assert cur.fetchone()[0] == 0
