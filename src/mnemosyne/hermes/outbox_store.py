from __future__ import annotations

from mnemosyne.alexandria.message_outbox import MessageOutbox


class OutboxStore(MessageOutbox):
    """Backward-compatible wrapper for the unified MessageOutbox."""

    def enqueue(
        self,
        *,
        message_id: str,
        message_type: str,
        payload_json: dict,
        expects_response: bool,
        originating_agent: str,
        context_id: str,
    ) -> None:
        super().enqueue(
            message_type=message_type,
            payload=payload_json,
            message_id=message_id,
            expects_response=expects_response,
            originating_agent=originating_agent,
            context_id=context_id,
        )
