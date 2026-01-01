"""
Integration tests for Story 012: proactive insight notifications with preferences, quiet hours, and batching.
"""

from datetime import datetime, time, timedelta

import pytest


class _InMemoryOutbox:
    def __init__(self):
        self.sent = []

    def send(self, message):
        self.sent.append(message)


@pytest.mark.integration
def test_notifications_respect_quiet_hours_and_rate_limits(postgres_connection):
    """
    Uses real Postgres connection (preferences persisted) but stub outbox (no real Telegram).
    """
    from mnemosyne.hermes.notifications import (
        DiscoveryNotification,
        NotificationPreferences,
        NotificationPreferencesRepository,
        NotificationService,
    )

    repo = NotificationPreferencesRepository(postgres_connection)
    prefs = NotificationPreferences(
        user_id="user-1",
        enabled=True,
        quiet_hours=(time(22, 0), time(7, 0)),
        max_daily_notifications=1,
        batch_mode="immediate",
        per_type_thresholds={"weak_link": 0.2},
        per_type_enabled={"weak_link": True, "contradiction": True},
    )
    repo.upsert(prefs)

    outbox = _InMemoryOutbox()
    service = NotificationService(repo, outbox)

    discoveries = [
        DiscoveryNotification(
            discovery_id="disc-1",
            discovery_job_key="latent-radar-job",
            pattern_type="weak_link",
            confidence=0.9,
            title="Unexpected connection",
        ),
        DiscoveryNotification(
            discovery_id="disc-2",
            discovery_job_key="latent-radar-job",
            pattern_type="weak_link",
            confidence=0.85,
            title="Another connection",
        ),
    ]

    # Quiet hours should suppress send
    service.process(discoveries[:1], now=datetime(2024, 1, 1, 23, 30))
    assert outbox.sent == []

    # Outside quiet hours, first notification goes through
    service.process(discoveries[:1], now=datetime(2024, 1, 2, 8, 0))
    assert len(outbox.sent) == 1
    assert outbox.sent[0]["discovery_id"] == "disc-1"
    assert outbox.sent[0]["template_type"] == "weak_link"

    # Rate limit prevents the second immediate send the same day
    service.process(discoveries[1:], now=datetime(2024, 1, 2, 9, 0))
    assert len(outbox.sent) == 1

    # Next day should allow sending again
    service.process(discoveries[1:], now=datetime(2024, 1, 3, 9, 0))
    assert len(outbox.sent) == 2
    assert outbox.sent[1]["discovery_id"] == "disc-2"


@pytest.mark.integration
def test_daily_digest_batches_and_includes_feedback_hooks(postgres_connection):
    from mnemosyne.hermes.notifications import (
        DiscoveryNotification,
        NotificationPreferences,
        NotificationPreferencesRepository,
        NotificationService,
    )

    repo = NotificationPreferencesRepository(postgres_connection)
    prefs = NotificationPreferences(
        user_id="user-2",
        enabled=True,
        quiet_hours=(time(0, 0), time(0, 0)),
        max_daily_notifications=10,
        batch_mode="daily_digest",
        per_type_thresholds={"project_candidate": 0.5, "weak_link": 0.2},
        per_type_enabled={"project_candidate": True, "weak_link": True},
    )
    repo.upsert(prefs)

    outbox = _InMemoryOutbox()
    service = NotificationService(repo, outbox)

    discoveries = [
        DiscoveryNotification(
            discovery_id="disc-10",
            discovery_job_key="latent-radar-job",
            pattern_type="project_candidate",
            confidence=0.8,
            title="Home lab project",
        ),
        DiscoveryNotification(
            discovery_id="disc-11",
            discovery_job_key="latent-radar-job",
            pattern_type="weak_link",
            confidence=0.6,
            title="Docker + home automation connection",
        ),
    ]

    service.process(discoveries, now=datetime(2024, 1, 2, 7, 0))
    assert len(outbox.sent) == 1
    digest = outbox.sent[0]
    assert digest["mode"] == "daily_digest"
    assert "disc-10" in digest["discoveries"]
    assert "disc-11" in digest["discoveries"]
    assert digest["actions"]["dismiss"] == ["disc-10", "disc-11"]
