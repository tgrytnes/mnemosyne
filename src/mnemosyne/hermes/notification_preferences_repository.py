"""PostgreSQL repository for notification preferences."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mnemosyne.hermes.notification_preferences import NotificationPreferences


@dataclass
class NotificationPreferencesRepository:
    connection: Any

    def ensure_table(self) -> None:
        cursor = self.connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS notification_preferences (
                user_id TEXT PRIMARY KEY,
                enabled BOOLEAN NOT NULL,
                quiet_start_hour INTEGER NOT NULL,
                quiet_end_hour INTEGER NOT NULL,
                max_daily_notifications INTEGER NOT NULL,
                notify_emerging_themes BOOLEAN NOT NULL,
                notify_orphaned_clusters BOOLEAN NOT NULL,
                notify_contradictions BOOLEAN NOT NULL,
                notify_project_candidates BOOLEAN NOT NULL,
                notify_weak_links BOOLEAN NOT NULL,
                min_confidence_emerging FLOAT NOT NULL,
                min_confidence_contradiction FLOAT NOT NULL,
                min_confidence_project FLOAT NOT NULL,
                min_confidence_weak_link FLOAT NOT NULL,
                batch_mode TEXT NOT NULL,
                digest_time INTEGER NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW()
            )
            """
        )
        self.connection.commit()

    def save(self, preferences: NotificationPreferences) -> None:
        cursor = self.connection.cursor()
        cursor.execute(
            """
            INSERT INTO notification_preferences (
                user_id,
                enabled,
                quiet_start_hour,
                quiet_end_hour,
                max_daily_notifications,
                notify_emerging_themes,
                notify_orphaned_clusters,
                notify_contradictions,
                notify_project_candidates,
                notify_weak_links,
                min_confidence_emerging,
                min_confidence_contradiction,
                min_confidence_project,
                min_confidence_weak_link,
                batch_mode,
                digest_time,
                updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
            )
            ON CONFLICT (user_id) DO UPDATE SET
                enabled = EXCLUDED.enabled,
                quiet_start_hour = EXCLUDED.quiet_start_hour,
                quiet_end_hour = EXCLUDED.quiet_end_hour,
                max_daily_notifications = EXCLUDED.max_daily_notifications,
                notify_emerging_themes = EXCLUDED.notify_emerging_themes,
                notify_orphaned_clusters = EXCLUDED.notify_orphaned_clusters,
                notify_contradictions = EXCLUDED.notify_contradictions,
                notify_project_candidates = EXCLUDED.notify_project_candidates,
                notify_weak_links = EXCLUDED.notify_weak_links,
                min_confidence_emerging = EXCLUDED.min_confidence_emerging,
                min_confidence_contradiction = EXCLUDED.min_confidence_contradiction,
                min_confidence_project = EXCLUDED.min_confidence_project,
                min_confidence_weak_link = EXCLUDED.min_confidence_weak_link,
                batch_mode = EXCLUDED.batch_mode,
                digest_time = EXCLUDED.digest_time,
                updated_at = NOW()
            """,
            (
                preferences.user_id,
                preferences.enabled,
                preferences.quiet_start_hour,
                preferences.quiet_end_hour,
                preferences.max_daily_notifications,
                preferences.notify_emerging_themes,
                preferences.notify_orphaned_clusters,
                preferences.notify_contradictions,
                preferences.notify_project_candidates,
                preferences.notify_weak_links,
                preferences.min_confidence_emerging,
                preferences.min_confidence_contradiction,
                preferences.min_confidence_project,
                preferences.min_confidence_weak_link,
                preferences.batch_mode,
                preferences.digest_time,
            ),
        )
        self.connection.commit()

    def get(self, user_id: str) -> NotificationPreferences | None:
        cursor = self.connection.cursor()
        cursor.execute(
            """
            SELECT
                user_id,
                enabled,
                quiet_start_hour,
                quiet_end_hour,
                max_daily_notifications,
                notify_emerging_themes,
                notify_orphaned_clusters,
                notify_contradictions,
                notify_project_candidates,
                notify_weak_links,
                min_confidence_emerging,
                min_confidence_contradiction,
                min_confidence_project,
                min_confidence_weak_link,
                batch_mode,
                digest_time
            FROM notification_preferences
            WHERE user_id = %s
            """,
            (user_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        return NotificationPreferences(
            user_id=row[0],
            enabled=row[1],
            quiet_start_hour=row[2],
            quiet_end_hour=row[3],
            max_daily_notifications=row[4],
            notify_emerging_themes=row[5],
            notify_orphaned_clusters=row[6],
            notify_contradictions=row[7],
            notify_project_candidates=row[8],
            notify_weak_links=row[9],
            min_confidence_emerging=row[10],
            min_confidence_contradiction=row[11],
            min_confidence_project=row[12],
            min_confidence_weak_link=row[13],
            batch_mode=row[14],
            digest_time=row[15],
        )
