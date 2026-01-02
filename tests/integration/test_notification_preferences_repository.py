from __future__ import annotations

import pytest

from mnemosyne.hermes.notification_preferences import NotificationPreferences
from mnemosyne.hermes.notification_preferences_repository import (
    NotificationPreferencesRepository,
)


@pytest.mark.integration
@pytest.mark.postgres
def test_save_and_load_notification_preferences(postgres_connection):
    repo = NotificationPreferencesRepository(postgres_connection)
    repo.ensure_table()

    prefs = NotificationPreferences(
        user_id="user-123",
        enabled=True,
        quiet_start_hour=21,
        quiet_end_hour=7,
        max_daily_notifications=5,
        notify_orphaned_clusters=True,
        min_confidence_project=0.6,
        batch_mode="daily_digest",
        digest_time=9,
    )

    repo.save(prefs)
    loaded = repo.get("user-123")

    assert loaded is not None
    assert loaded.user_id == "user-123"
    assert loaded.enabled is True
    assert loaded.quiet_start_hour == 21
    assert loaded.quiet_end_hour == 7
    assert loaded.max_daily_notifications == 5
    assert loaded.notify_orphaned_clusters is True
    assert loaded.min_confidence_project == 0.6
    assert loaded.batch_mode == "daily_digest"
    assert loaded.digest_time == 9


@pytest.mark.integration
@pytest.mark.postgres
def test_update_notification_preferences(postgres_connection):
    repo = NotificationPreferencesRepository(postgres_connection)
    repo.ensure_table()

    prefs = NotificationPreferences(user_id="user-321")
    repo.save(prefs)

    updated = NotificationPreferences(
        user_id="user-321",
        enabled=False,
        quiet_start_hour=23,
        quiet_end_hour=6,
        max_daily_notifications=2,
        notify_contradictions=False,
        batch_mode="weekly_digest",
        digest_time=8,
    )
    repo.save(updated)

    loaded = repo.get("user-321")
    assert loaded is not None
    assert loaded.enabled is False
    assert loaded.quiet_start_hour == 23
    assert loaded.quiet_end_hour == 6
    assert loaded.max_daily_notifications == 2
    assert loaded.notify_contradictions is False
    assert loaded.batch_mode == "weekly_digest"
    assert loaded.digest_time == 8
