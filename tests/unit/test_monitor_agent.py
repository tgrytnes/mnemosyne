"""
Unit tests for Monitor Agent reconciliation logic.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from mnemosyne.argus.scout.monitor_agent import (
    DiscoveryRecord,
    MonitorAgent,
    MonitorConfig,
)


@dataclass
class _FakeDiscoveryReader:
    discoveries: list[DiscoveryRecord]

    def fetch_project_candidates(self, threshold: float, limit: int) -> list[DiscoveryRecord]:
        return [d for d in self.discoveries if d.confidence_score >= threshold][:limit]


@dataclass
class _FakeProjectRepository:
    existing_ids: set[str]

    def exists_by_discovery_id(self, discovery_id: str) -> bool:
        return discovery_id in self.existing_ids


class _InMemoryIntentQueue:
    def __init__(self):
        self.intents: list[dict[str, str]] = []

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
                "message_id": message_id,
                "originating_agent": originating_agent,
                "context_id": context_id,
                "expects_response": expects_response,
                "payload": payload,
            }
        )


class _InMemoryProposalQueue:
    def __init__(self):
        self._proposals: dict[str, dict] = {}

    def upsert(self, discovery: DiscoveryRecord) -> None:
        self._proposals[discovery.discovery_id] = {
            "proposal_id": discovery.discovery_id,
            "discovery_id": discovery.discovery_id,
            "discovery_job_key": discovery.discovery_job_key,
            "candidate_key": discovery.candidate_key,
            "cluster_ids": discovery.cluster_ids,
            "confidence_score": discovery.confidence_score,
            "detected_at": discovery.detected_at,
            "status": "pending",
        }

    def get_by_discovery_id(self, discovery_id: str) -> dict | None:
        return self._proposals.get(discovery_id)

    def update_status(self, discovery_id: str, status: str) -> None:
        proposal = self._proposals.get(discovery_id)
        if proposal:
            proposal["status"] = status

    def list_by_status(self, status: str) -> list[dict]:
        return [proposal for proposal in self._proposals.values() if proposal["status"] == status]


class _InMemoryStateStore:
    def __init__(self):
        self._state: dict[str, dict] = {}

    def get_state(self, discovery_id: str) -> dict | None:
        return self._state.get(discovery_id)

    def record_ask(self, discovery_id: str) -> None:
        entry = self._state.setdefault(discovery_id, {"ask_count": 0})
        entry["ask_count"] = int(entry.get("ask_count") or 0) + 1

    def record_rejection(
        self,
        discovery_id: str,
        rejected_at: datetime,
        rejected_confidence: float,
        ask_count: int | None = None,
    ) -> None:
        entry = self._state.setdefault(discovery_id, {})
        entry["rejected_at"] = rejected_at
        entry["rejected_confidence"] = rejected_confidence
        if ask_count is not None:
            entry["ask_count"] = ask_count

    def archive(self, discovery_id: str) -> None:
        entry = self._state.setdefault(discovery_id, {})
        entry["archived_at"] = datetime.now(UTC)


def _sample_discovery(
    confidence: float = 0.8,
    discovery_id: str = "private_projects:house_painting",
    candidate_key: str = "house_painting",
) -> DiscoveryRecord:
    return DiscoveryRecord(
        discovery_id=discovery_id,
        discovery_job_key=discovery_id.split(":", 1)[0],
        candidate_key=candidate_key,
        pattern_type="project_candidate",
        cluster_ids=["c1"],
        confidence_score=confidence,
        detected_at=datetime.now(UTC),
    )


def test_monitor_creates_proposal_for_new_discovery():
    discovery = _sample_discovery()
    reader = _FakeDiscoveryReader([discovery])
    projects = _FakeProjectRepository(existing_ids=set())

    proposal_queue = _InMemoryProposalQueue()
    state_store = _InMemoryStateStore()
    intent_queue = _InMemoryIntentQueue()

    agent = MonitorAgent(
        discovery_reader=reader,
        project_repository=projects,
        proposal_queue=proposal_queue,
        state_store=state_store,
        intent_queue=intent_queue,
        config=MonitorConfig(confidence_threshold=0.7),
    )

    agent.run()

    proposal = proposal_queue.get_by_discovery_id(discovery.discovery_id)
    assert proposal is not None
    assert proposal["status"] == "pending"
    assert proposal["discovery_job_key"] == discovery.discovery_job_key
    assert proposal["candidate_key"] == discovery.candidate_key

    state = state_store.get_state(discovery.discovery_id)
    assert state is not None
    assert state["ask_count"] == 1


def test_monitor_skips_discovery_already_in_sql():
    discovery = _sample_discovery()
    reader = _FakeDiscoveryReader([discovery])
    projects = _FakeProjectRepository(existing_ids={discovery.discovery_id})

    proposal_queue = _InMemoryProposalQueue()
    state_store = _InMemoryStateStore()
    intent_queue = _InMemoryIntentQueue()

    agent = MonitorAgent(
        discovery_reader=reader,
        project_repository=projects,
        proposal_queue=proposal_queue,
        state_store=state_store,
        intent_queue=intent_queue,
        config=MonitorConfig(confidence_threshold=0.7),
    )

    agent.run()

    assert proposal_queue.get_by_discovery_id(discovery.discovery_id) is None


def test_monitor_respects_reask_policy():
    discovery = _sample_discovery(confidence=0.82)
    reader = _FakeDiscoveryReader([discovery])
    projects = _FakeProjectRepository(existing_ids=set())

    proposal_queue = _InMemoryProposalQueue()
    state_store = _InMemoryStateStore()
    intent_queue = _InMemoryIntentQueue()

    rejected_at = datetime.now(UTC) - timedelta(days=1)
    state_store.record_rejection(
        discovery_id=discovery.discovery_id,
        rejected_at=rejected_at,
        rejected_confidence=0.8,
        ask_count=1,
    )

    agent = MonitorAgent(
        discovery_reader=reader,
        project_repository=projects,
        proposal_queue=proposal_queue,
        state_store=state_store,
        intent_queue=intent_queue,
        config=MonitorConfig(
            confidence_threshold=0.7,
            cooldown_days=14,
            max_asks=3,
            confidence_delta=0.15,
        ),
    )

    agent.run()

    assert proposal_queue.get_by_discovery_id(discovery.discovery_id) is None


def test_monitor_escalation_records_intent():
    discovery = _sample_discovery(confidence=0.95)
    reader = _FakeDiscoveryReader([])
    projects = _FakeProjectRepository(existing_ids=set())

    proposal_queue = _InMemoryProposalQueue()
    state_store = _InMemoryStateStore()
    intent_queue = _InMemoryIntentQueue()

    proposal_queue.upsert(discovery)
    proposal_queue.update_status(discovery.discovery_id, "rejected")

    agent = MonitorAgent(
        discovery_reader=reader,
        project_repository=projects,
        proposal_queue=proposal_queue,
        state_store=state_store,
        intent_queue=intent_queue,
        config=MonitorConfig(confidence_threshold=0.7),
    )

    agent.run()

    assert intent_queue.intents
    intent = intent_queue.intents[0]
    assert intent["intent_type"] == "proposal_escalation"
    assert intent["message_id"] == f"proposal_escalation:{discovery.discovery_id}"
    assert intent["originating_agent"] == "monitor"
    assert intent["context_id"] == f"discovery:{discovery.discovery_id}"
    assert intent["expects_response"] is False


def test_monitor_logs_summary_counts(caplog):
    d_existing = _sample_discovery(
        discovery_id="private_projects:existing",
        candidate_key="existing",
    )
    d_snoozed = _sample_discovery(
        discovery_id="private_projects:snoozed",
        candidate_key="snoozed",
    )
    d_max_asks = _sample_discovery(
        discovery_id="private_projects:max_asks",
        candidate_key="max_asks",
    )
    d_cooldown = _sample_discovery(
        discovery_id="private_projects:cooldown",
        candidate_key="cooldown",
    )
    d_ready = _sample_discovery(
        discovery_id="private_projects:ready",
        candidate_key="ready",
    )
    d_rejected = _sample_discovery(
        discovery_id="private_projects:rejected",
        candidate_key="rejected",
    )

    reader = _FakeDiscoveryReader([d_existing, d_snoozed, d_max_asks, d_cooldown, d_ready])
    projects = _FakeProjectRepository(existing_ids={d_existing.discovery_id})

    proposal_queue = _InMemoryProposalQueue()
    state_store = _InMemoryStateStore()
    intent_queue = _InMemoryIntentQueue()

    future = datetime.now(UTC) + timedelta(days=3)
    state_store._state[d_snoozed.discovery_id] = {
        "snoozed_until": future,
        "ask_count": 1,
    }

    state_store.record_ask(d_max_asks.discovery_id)
    state_store.record_ask(d_max_asks.discovery_id)
    state_store.record_rejection(
        discovery_id=d_cooldown.discovery_id,
        rejected_at=datetime.now(UTC) - timedelta(days=1),
        rejected_confidence=0.7,
        ask_count=1,
    )

    proposal_queue.upsert(d_rejected)
    proposal_queue.update_status(d_rejected.discovery_id, "rejected")

    agent = MonitorAgent(
        discovery_reader=reader,
        project_repository=projects,
        proposal_queue=proposal_queue,
        state_store=state_store,
        intent_queue=intent_queue,
        config=MonitorConfig(
            confidence_threshold=0.7,
            max_asks=2,
            cooldown_days=14,
            confidence_delta=0.15,
        ),
    )

    with caplog.at_level(logging.INFO):
        agent.run()

    log_text = caplog.text
    assert "Monitor run complete" in log_text
    assert "scanned=5" in log_text
    assert "queued=1" in log_text
    assert "skipped_already_project=1" in log_text
    assert "skipped_snoozed=1" in log_text
    assert "skipped_max_asks=1" in log_text
    assert "skipped_cooldown=1" in log_text
    assert "escalated=1" in log_text
