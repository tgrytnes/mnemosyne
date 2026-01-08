"""Unit tests for Story 029 PM intent processing."""

from __future__ import annotations

from unittest.mock import Mock

import pytest


@pytest.fixture
def mock_db_conn():
    conn = Mock()
    cursor = Mock()
    cursor.__enter__ = Mock(return_value=cursor)
    cursor.__exit__ = Mock(return_value=None)
    conn.cursor.return_value = cursor
    return conn


class _FakeIntentQueue:
    def __init__(self, intents: list[dict]):
        self._intents = intents
        self.handled: list[str] = []

    def list_pending(self, limit: int = 10) -> list[dict]:
        return self._intents[:limit]

    def mark_handled(self, message_id: str) -> None:
        self.handled.append(message_id)


def test_pm_processes_gatekeeper_intent_to_outbox(mock_db_conn):
    from mnemosyne.aletheia.agents.project_manager import ProjectManagerAgent

    outbox = Mock()
    outbox.enqueue = Mock()
    intents = _FakeIntentQueue(
        [
            {
                "message_id": "project_approval:disc-1",
                "intent_type": "project_approval_request",
                "originating_agent": "gatekeeper",
                "context_id": "discovery:disc-1",
                "payload": {
                    "candidate_key": "demo",
                    "confidence": 0.72,
                },
            }
        ]
    )

    agent = ProjectManagerAgent(mock_db_conn, outbox, intent_queue=intents)
    agent.process_intents(limit=5)

    outbox.enqueue.assert_called_once()
    call_args = outbox.enqueue.call_args[1]
    assert call_args["message_type"] == "question"
    assert call_args["expects_response"] is True
    assert call_args["originating_agent"] == "project_manager"
    assert call_args["context_id"] == "discovery:disc-1"
    assert "approve" in call_args["payload"]["text"].lower()
    assert intents.handled == ["project_approval:disc-1"]


def test_pm_processes_monitor_escalation_to_outbox(mock_db_conn):
    from mnemosyne.aletheia.agents.project_manager import ProjectManagerAgent

    outbox = Mock()
    outbox.enqueue = Mock()
    intents = _FakeIntentQueue(
        [
            {
                "message_id": "proposal_escalation:disc-9",
                "intent_type": "proposal_escalation",
                "originating_agent": "monitor",
                "context_id": "discovery:disc-9",
                "payload": {
                    "candidate_key": "demo",
                    "confidence": 0.52,
                },
            }
        ]
    )

    agent = ProjectManagerAgent(mock_db_conn, outbox, intent_queue=intents)
    agent.process_intents(limit=5)

    outbox.enqueue.assert_called_once()
    call_args = outbox.enqueue.call_args[1]
    assert call_args["message_type"] == "escalation"
    assert call_args["expects_response"] is False
    assert call_args["originating_agent"] == "project_manager"
    assert call_args["context_id"] == "discovery:disc-9"
    assert "proposal" in call_args["payload"]["text"].lower()
    assert intents.handled == ["proposal_escalation:disc-9"]
