"""Telegram command handlers for notification settings and history."""

from __future__ import annotations

from dataclasses import dataclass

from mnemosyne.hermes.notification_preferences import NotificationPreferences
from mnemosyne.hermes.outbox_store import OutboxStore


@dataclass
class NotificationCommandHandler:
    preferences_repo: object
    outbox: OutboxStore

    def _get_or_create(self, user_id: str) -> NotificationPreferences:
        existing = self.preferences_repo.get(user_id)
        if existing is not None:
            return existing
        prefs = NotificationPreferences(user_id=user_id)
        self.preferences_repo.save(prefs)
        return prefs

    def handle_notify_settings(self, *, user_id: str) -> str:
        prefs = self._get_or_create(user_id)
        return (
            "Notification settings:\n"
            f"- Enabled: {prefs.enabled}\n"
            f"- Quiet hours: {prefs.quiet_start_hour}-{prefs.quiet_end_hour}\n"
            f"- Max daily notifications: {prefs.max_daily_notifications}\n"
            f"- Batch mode: {prefs.batch_mode}\n"
            f"- Digest time: {prefs.digest_time}:00"
        )

    def handle_quiet_hours(self, *, user_id: str, start_hour: int, end_hour: int) -> str:
        prefs = self._get_or_create(user_id)
        updated = prefs.model_copy(
            update={"quiet_start_hour": start_hour, "quiet_end_hour": end_hour}
        )
        self.preferences_repo.save(updated)
        return f"Quiet hours updated: {start_hour}-{end_hour}"

    def handle_discoveries(self, *, chat_id: str, limit: int = 5) -> str:
        rows = self.outbox.list_recent_by_chat(
            chat_id=chat_id,
            limit=limit,
            message_type_prefix="discovery_",
        )
        if not rows:
            return "No discovery notifications yet."

        lines = ["Recent discoveries:"]
        for row in rows:
            payload = row.payload_json
            title = payload.get("title") or payload.get("summary") or row.message_type
            lines.append(f"- {title}")
        return "\n".join(lines)
