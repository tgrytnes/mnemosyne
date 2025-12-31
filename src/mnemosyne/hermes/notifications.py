"""
Notification preferences and delivery for Stories 012/013.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from datetime import datetime, time


@dataclass
class DiscoveryNotification:
    discovery_id: str
    discovery_job_key: str
    pattern_type: str
    confidence: float
    title: str
    description: str | None = None


@dataclass
class NotificationPreferences:
    user_id: str
    enabled: bool = True
    quiet_hours: tuple[time, time] = (time(22, 0), time(7, 0))
    max_daily_notifications: int = 3
    batch_mode: str = "daily_digest"
    per_type_thresholds: dict[str, float] = field(default_factory=dict)
    per_type_enabled: dict[str, bool] = field(default_factory=dict)


class NotificationPreferencesRepository:
    """Persist preferences in Postgres (using psycopg2 connection)."""

    def __init__(self, conn):
        self.conn = conn
        self._ensure_table()

    def _ensure_table(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS notification_preferences (
                user_id TEXT PRIMARY KEY,
                enabled BOOLEAN,
                quiet_start TEXT,
                quiet_end TEXT,
                max_daily INTEGER,
                batch_mode TEXT,
                per_type_thresholds JSONB,
                per_type_enabled JSONB
            )
            """
        )
        self.conn.commit()
        cur.close()

    def upsert(self, prefs: NotificationPreferences) -> None:
        cur = self.conn.cursor()
        # Keep a single active preference row for simplicity
        cur.execute("DELETE FROM notification_preferences WHERE user_id <> %s", (prefs.user_id,))
        cur.execute(
            """
            INSERT INTO notification_preferences
            (user_id, enabled, quiet_start, quiet_end, max_daily, batch_mode, per_type_thresholds, per_type_enabled)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                enabled=EXCLUDED.enabled,
                quiet_start=EXCLUDED.quiet_start,
                quiet_end=EXCLUDED.quiet_end,
                max_daily=EXCLUDED.max_daily,
                batch_mode=EXCLUDED.batch_mode,
                per_type_thresholds=EXCLUDED.per_type_thresholds,
                per_type_enabled=EXCLUDED.per_type_enabled
            """,
            (
                prefs.user_id,
                prefs.enabled,
                prefs.quiet_hours[0].isoformat(),
                prefs.quiet_hours[1].isoformat(),
                prefs.max_daily_notifications,
                prefs.batch_mode,
                json.dumps(prefs.per_type_thresholds),
                json.dumps(prefs.per_type_enabled),
            ),
        )
        self.conn.commit()
        cur.close()

    def get(self, user_id: str) -> NotificationPreferences | None:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT user_id, enabled, quiet_start, quiet_end, max_daily, batch_mode, per_type_thresholds, per_type_enabled FROM notification_preferences WHERE user_id=%s",
            (user_id,),
        )
        row = cur.fetchone()
        cur.close()
        if not row:
            return None
        thresholds_raw = row[6]
        enabled_raw = row[7]
        if not isinstance(thresholds_raw, (str, bytes, bytearray)):
            thresholds = thresholds_raw or {}
        else:
            thresholds = json.loads(thresholds_raw) if thresholds_raw else {}
        if not isinstance(enabled_raw, (str, bytes, bytearray)):
            per_type_enabled = enabled_raw or {}
        else:
            per_type_enabled = json.loads(enabled_raw) if enabled_raw else {}
        return NotificationPreferences(
            user_id=row[0],
            enabled=row[1],
            quiet_hours=(time.fromisoformat(row[2]), time.fromisoformat(row[3])),
            max_daily_notifications=row[4],
            batch_mode=row[5],
            per_type_thresholds=thresholds,
            per_type_enabled=per_type_enabled,
        )

    def get_first(self) -> NotificationPreferences | None:
        cur = self.conn.cursor()
        cur.execute("SELECT user_id FROM notification_preferences ORDER BY user_id ASC LIMIT 1")
        row = cur.fetchone()
        cur.close()
        if not row:
            return None
        return self.get(row[0])


class NotificationService:
    def __init__(self, repo: NotificationPreferencesRepository, outbox):
        self.repo = repo
        self.outbox = outbox
        self._daily_counts: dict[tuple[str, datetime.date], int] = {}

    def process(self, discoveries: list[DiscoveryNotification], now: datetime) -> None:
        prefs = self.repo.get_first()
        if not prefs or not prefs.enabled:
            return

        if prefs.batch_mode == "daily_digest":
            filtered = [d for d in discoveries if self._passes_filters(d, prefs)]
            if not filtered:
                return
            payload = {
                "mode": "daily_digest",
                "discoveries": [d.discovery_id for d in filtered],
                "actions": {"dismiss": [d.discovery_id for d in filtered]},
            }
            self.outbox.send(payload)
            return

        # immediate mode
        for disc in discoveries:
            if not self._passes_filters(disc, prefs):
                continue
            if self._is_quiet(now, prefs.quiet_hours) and disc.pattern_type != "contradiction":
                continue
            if self._hit_rate_limit(prefs, now.date()):
                continue
            message = {
                "discovery_id": disc.discovery_id,
                "template_type": disc.pattern_type,
                "title": disc.title,
                "confidence": disc.confidence,
                "discovery_job_key": disc.discovery_job_key,
            }
            self.outbox.send(message)
            self._increment(prefs, now.date())

    def _passes_filters(self, disc: DiscoveryNotification, prefs: NotificationPreferences) -> bool:
        if not prefs.per_type_enabled.get(disc.pattern_type, True):
            return False
        threshold = prefs.per_type_thresholds.get(disc.pattern_type, 0.0)
        return disc.confidence >= threshold

    def _is_quiet(self, now: datetime, quiet_hours: tuple[time, time]) -> bool:
        start, end = quiet_hours
        current = now.time()
        if start <= end:
            return start <= current < end
        # Wrap around midnight
        return current >= start or current < end

    def _hit_rate_limit(self, prefs: NotificationPreferences, day) -> bool:
        return self._daily_counts.get((prefs.user_id, day), 0) >= prefs.max_daily_notifications

    def _increment(self, prefs: NotificationPreferences, day) -> None:
        key = (prefs.user_id, day)
        self._daily_counts[key] = self._daily_counts.get(key, 0) + 1
