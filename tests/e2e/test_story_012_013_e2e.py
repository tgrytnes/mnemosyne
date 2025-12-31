"""E2E for Stories 012/013: notifications + discovery feed with Postgres + stub outbox."""

from datetime import datetime, time

import pytest


class _StubOutbox:
    def __init__(self):
        self.sent = []

    def send(self, message):
        self.sent.append(message)


@pytest.mark.e2e
def test_notifications_and_feed_flow(postgres_connection, tmp_path):
    from mnemosyne.hermes.feed import DiscoveryFeedManager
    from mnemosyne.hermes.notifications import (
        DiscoveryNotification,
        NotificationPreferences,
        NotificationPreferencesRepository,
        NotificationService,
    )

    repo = NotificationPreferencesRepository(postgres_connection)
    prefs = NotificationPreferences(
        user_id="user-feed",
        enabled=True,
        quiet_hours=(time(0, 0), time(0, 0)),
        max_daily_notifications=5,
        batch_mode="immediate",
        per_type_thresholds={"project_candidate": 0.5, "weak_link": 0.2},
        per_type_enabled={"project_candidate": True, "weak_link": True},
    )
    repo.upsert(prefs)

    outbox = _StubOutbox()
    notifier = NotificationService(repo, outbox)

    discoveries = [
        DiscoveryNotification(
            discovery_id="disc-feed-1",
            discovery_job_key="latent-radar-job",
            pattern_type="project_candidate",
            confidence=0.82,
            title="Home lab project",
            description="Signals of a home lab project in your vault.",
        ),
        DiscoveryNotification(
            discovery_id="disc-feed-2",
            discovery_job_key="latent-radar-job",
            pattern_type="weak_link",
            confidence=0.61,
            title="Docker ↔ Home automation link",
            description="Connection between docker lab and home automation notes.",
        ),
    ]

    notifier.process(discoveries, now=datetime(2024, 2, 1, 9, 0))
    assert len(outbox.sent) == 2
    assert {msg["discovery_id"] for msg in outbox.sent} == {"disc-feed-1", "disc-feed-2"}

    feed = DiscoveryFeedManager()
    feed.ingest(
        [
            {
                "discovery_id": d.discovery_id,
                "title": d.title,
                "pattern_type": d.pattern_type,
                "confidence": d.confidence,
                "detected_at": "2024-02-01T09:00:00Z",
                "status": "new",
                "clusters": [],
                "description": d.description,
            }
            for d in discoveries
        ]
    )

    listing = feed.list(filters={"status": "new"}, page=1, per_page=10)
    assert listing.total == 2

    detail = feed.view("disc-feed-1")
    assert detail.discovery_id == "disc-feed-1"
    assert feed.get_status("disc-feed-1") == "reviewed"

    exported = feed.export_markdown("disc-feed-2", destination=tmp_path / "disc-feed-2.md")
    assert "disc-feed-2" in exported["content"]
    assert exported["path"].endswith("disc-feed-2.md")
