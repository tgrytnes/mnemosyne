"""Unit tests for Story 029 gatekeeper intent routing to PM."""

from __future__ import annotations

from datetime import UTC, datetime

from mnemosyne.alexandria.sql_gatekeeper import GatekeeperConfig, SQLProjectGatekeeper


class _FakeCursor:
    def __init__(self):
        self.executed: list[tuple] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, *args, **kwargs) -> None:
        self.executed.append((args, kwargs))

    def fetchone(self):
        return None


class _FakeDB:
    def __init__(self):
        self.cursor_obj = _FakeCursor()

    def cursor(self):
        return self.cursor_obj

    def commit(self) -> None:
        return None


class _FakeProposalQueue:
    def __init__(self, proposals: list[dict]):
        self._proposals = {p["discovery_id"]: p for p in proposals}

    def list_by_status(self, status: str) -> list[dict]:
        return [p for p in self._proposals.values() if p["status"] == status]

    def update_status(self, discovery_id: str, status: str) -> None:
        self._proposals[discovery_id]["status"] = status


class _FakeIntentQueue:
    def __init__(self):
        self.intents: list[dict] = []

    def enqueue_intent(
        self,
        intent_type: str,
        payload: dict,
        message_id: str,
        originating_agent: str | None = None,
        context_id: str | None = None,
        expects_response: bool = False,
    ) -> None:
        self.intents.append(
            {
                "intent_type": intent_type,
                "payload": payload,
                "message_id": message_id,
                "originating_agent": originating_agent,
                "context_id": context_id,
                "expects_response": expects_response,
            }
        )


def test_gatekeeper_enqueues_pm_intent_for_manual_approval():
    proposal = {
        "discovery_id": "disc-1",
        "discovery_job_key": "job-1",
        "candidate_key": "candidate-1",
        "confidence_score": 0.72,
        "detected_at": datetime.now(UTC),
        "cluster_ids": ["c1"],
        "status": "pending",
    }
    db = _FakeDB()
    queue = _FakeProposalQueue([proposal])
    intents = _FakeIntentQueue()

    gatekeeper = SQLProjectGatekeeper(
        db,
        queue,
        intents,
        GatekeeperConfig(auto_reject_threshold=0.6, auto_approve_threshold=0.9),
    )

    counts = gatekeeper.process_pending()

    assert counts["awaiting_approval"] == 1
    assert queue.list_by_status("awaiting_approval")
    assert len(intents.intents) == 1
    intent = intents.intents[0]
    assert intent["intent_type"] == "project_approval_request"
    assert intent["message_id"] == "project_approval:disc-1"
    assert intent["originating_agent"] == "gatekeeper"
    assert intent["context_id"] == "discovery:disc-1"
    assert intent["expects_response"] is True
