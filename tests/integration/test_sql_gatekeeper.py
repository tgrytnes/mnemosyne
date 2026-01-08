from __future__ import annotations

from datetime import UTC, datetime

import pytest

from mnemosyne.alexandria.communication_intents import PMIntentQueue
from mnemosyne.alexandria.sql_gatekeeper import GatekeeperConfig, SQLProjectGatekeeper
from mnemosyne.argus.scout.monitor_agent import DiscoveryRecord, ProposalQueue


def _make_record(discovery_id: str, confidence: float, cluster_ids: list[str]) -> DiscoveryRecord:
    return DiscoveryRecord(
        discovery_id=discovery_id,
        discovery_job_key="job",
        candidate_key=discovery_id,
        pattern_type="project_candidate",
        cluster_ids=cluster_ids,
        confidence_score=confidence,
        detected_at=datetime.now(UTC),
        title=None,
        description=None,
    )


def _reset_gatekeeper_tables(postgres_connection) -> None:
    cursor = postgres_connection.cursor()
    cursor.execute("DELETE FROM proposal_queue")
    cursor.execute("DELETE FROM pm_intent_queue")
    postgres_connection.commit()


@pytest.mark.integration
@pytest.mark.postgres
def test_auto_reject_updates_queue_and_audit(postgres_connection, ananke_test_db):
    queue = ProposalQueue(postgres_connection)
    intent_queue = PMIntentQueue(postgres_connection)
    _reset_gatekeeper_tables(postgres_connection)
    gatekeeper = SQLProjectGatekeeper(
        postgres_connection,
        queue,
        intent_queue,
        GatekeeperConfig(auto_reject_threshold=0.6, auto_approve_threshold=0.9),
    )

    record = _make_record("disc-low", 0.5, ["1"])
    queue.upsert(record)

    result = gatekeeper.process_pending()
    assert result["rejected"] == 1
    assert queue.list_by_status("rejected")

    cur = postgres_connection.cursor()
    cur.execute("SELECT approved FROM gatekeeper_audit WHERE approval_id = %s", ("disc-low",))
    row = cur.fetchone()
    assert row and row[0] is False


@pytest.mark.integration
@pytest.mark.postgres
def test_auto_approve_inserts_project(postgres_connection, ananke_test_db):
    queue = ProposalQueue(postgres_connection)
    intent_queue = PMIntentQueue(postgres_connection)
    _reset_gatekeeper_tables(postgres_connection)
    gatekeeper = SQLProjectGatekeeper(
        postgres_connection,
        queue,
        intent_queue,
        GatekeeperConfig(auto_reject_threshold=0.6, auto_approve_threshold=0.9),
    )

    record = _make_record("disc-high", 0.95, ["2"])
    queue.upsert(record)

    result = gatekeeper.process_pending()
    assert result["auto_approved"] == 1

    cur = postgres_connection.cursor()
    cur.execute("SELECT COUNT(*) FROM projects WHERE discovery_id = %s", ("disc-high",))
    assert cur.fetchone()[0] == 1
    assert queue.list_by_status("approved")


@pytest.mark.integration
@pytest.mark.postgres
def test_requires_approval_enqueues_intent(postgres_connection, ananke_test_db):
    queue = ProposalQueue(postgres_connection)
    intent_queue = PMIntentQueue(postgres_connection)
    _reset_gatekeeper_tables(postgres_connection)
    gatekeeper = SQLProjectGatekeeper(
        postgres_connection,
        queue,
        intent_queue,
        GatekeeperConfig(auto_reject_threshold=0.6, auto_approve_threshold=0.9),
    )

    record = _make_record("disc-mid", 0.7, ["3"])
    queue.upsert(record)

    result = gatekeeper.process_pending()
    assert result["awaiting_approval"] == 1
    intents = intent_queue.list_pending(limit=10)
    assert intents[0]["intent_type"] == "project_approval_request"
    assert queue.list_by_status("awaiting_approval")


@pytest.mark.integration
@pytest.mark.postgres
def test_manual_approval_flow(postgres_connection, ananke_test_db):
    queue = ProposalQueue(postgres_connection)
    intent_queue = PMIntentQueue(postgres_connection)
    _reset_gatekeeper_tables(postgres_connection)
    gatekeeper = SQLProjectGatekeeper(
        postgres_connection,
        queue,
        intent_queue,
        GatekeeperConfig(auto_reject_threshold=0.6, auto_approve_threshold=0.95),
    )

    record = _make_record("disc-manual", 0.7, ["4"])
    queue.upsert(record)
    gatekeeper.process_pending()
    project_id = gatekeeper.approve("disc-manual")

    assert project_id != -1
    cur = postgres_connection.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM gatekeeper_audit WHERE approval_id = %s AND approved = TRUE",
        ("disc-manual",),
    )
    assert cur.fetchone()[0] == 1


@pytest.mark.integration
@pytest.mark.postgres
def test_rollback_with_token(postgres_connection, ananke_test_db):
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

    record = _make_record("disc-rb", 0.95, ["5"])
    queue.upsert(record)
    gatekeeper.process_pending()

    cur = postgres_connection.cursor()
    cur.execute("SELECT id FROM projects WHERE discovery_id = %s", ("disc-rb",))
    project_id = cur.fetchone()[0]

    token = gatekeeper.request_rollback(project_id)
    assert token

    gatekeeper.confirm_rollback(project_id, token)
    cur.execute("SELECT COUNT(*) FROM projects WHERE id = %s", (project_id,))
    assert cur.fetchone()[0] == 0
