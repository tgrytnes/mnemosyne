"""Rate limiting helpers for outbound notifications."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from mnemosyne.alexandria.message_outbox import MessageOutbox


@dataclass
class NotificationRateLimiter:
    outbox: MessageOutbox

    def can_send(
        self,
        *,
        chat_id: str,
        max_daily_notifications: int,
        now: datetime | None = None,
    ) -> bool:
        if max_daily_notifications <= 0:
            return False

        current = now or datetime.utcnow()
        start_of_day = current.replace(hour=0, minute=0, second=0, microsecond=0)
        delivered = self.outbox.count_delivered_since(
            chat_id=chat_id,
            since_iso=start_of_day.isoformat(),
        )
        return delivered < max_daily_notifications
