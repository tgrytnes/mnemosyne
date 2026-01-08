"""CLI helpers for inspecting and managing the message outbox (Story 027)."""

from __future__ import annotations

from mnemosyne.alexandria.message_outbox import (
    MessageOutbox,
    OutboxMessage,
    _parse_timestamp,
)


class OutboxCLI:
    def __init__(self, outbox: MessageOutbox) -> None:
        self._outbox = outbox

    def status(self) -> dict[str, int]:
        cursor = self._outbox.db.cursor()
        cursor.execute("SELECT status, COUNT(*) FROM message_outbox GROUP BY status")
        rows = cursor.fetchall() or []
        counts = {row[0]: int(row[1]) for row in rows}
        for status in ("pending", "delivered", "failed", "awaiting_response"):
            counts.setdefault(status, 0)
        return counts

    def inspect(self, message_id: str) -> OutboxMessage | None:
        return self._outbox.get_by_message_id(message_id)

    def requeue(self, message_id: str) -> None:
        self._outbox.requeue(message_id)

    def clear_delivered(self, before_iso: str) -> int:
        cursor = self._outbox.db.cursor()
        cutoff = _parse_timestamp(before_iso)
        if cutoff is None:
            return 0

        cursor.execute(
            "SELECT message_id, delivered_at FROM message_outbox WHERE status = 'delivered'"
        )
        rows = cursor.fetchall() or []
        deleted = 0
        for message_id, delivered_at in rows:
            delivered_ts = _parse_timestamp(delivered_at)
            if delivered_ts and delivered_ts < cutoff:
                cursor.execute(
                    "DELETE FROM message_outbox WHERE message_id = ?",
                    (message_id,),
                )
                deleted += cursor.rowcount or 0
        self._outbox.db.commit()
        return int(deleted)
