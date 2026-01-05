"""
Unit tests for Monitor Agent reconciliation logic.
"""

from __future__ import annotations

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


def _sample_discovery(confidence: float = 0.8) -> DiscoveryRecord:
    return DiscoveryRecord(
        discovery_id="private_projects:house_painting",
        discovery_job_key="private_projects",
        candidate_key="house_painting",
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
    outbox = _InMemoryOutbox()

    agent = MonitorAgent(
        discovery_reader=reader,
        project_repository=projects,
        proposal_queue=proposal_queue,
        state_store=state_store,
        outbox=outbox,
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
    outbox = _InMemoryOutbox()

    agent = MonitorAgent(
        discovery_reader=reader,
        project_repository=projects,
        proposal_queue=proposal_queue,
        state_store=state_store,
        outbox=outbox,
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
    outbox = _InMemoryOutbox()

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
        outbox=outbox,
        config=MonitorConfig(
            confidence_threshold=0.7,
            cooldown_days=14,
            max_asks=3,
            confidence_delta=0.15,
        ),
    )

    agent.run()

    assert proposal_queue.get_by_discovery_id(discovery.discovery_id) is None
