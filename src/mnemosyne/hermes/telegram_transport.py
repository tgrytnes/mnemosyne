from __future__ import annotations

from dataclasses import dataclass

from mnemosyne.hermes.outbox_store import OutboxStore


@dataclass
class TelegramMessagePayload:
    chat_id: str
    text: str
    buttons: list
    parse_mode: str | None


class TelegramOutboxConsumer:
    def __init__(self, outbox: OutboxStore, telegram_client):
        self._outbox = outbox
        self._client = telegram_client

    def deliver_pending(self, *, limit: int = 10) -> None:
        pending = self._outbox.fetch_pending(limit=limit)
        for row in pending:
            payload = self._build_payload(row)
            try:
                message_id = self._client.send_message(
                    chat_id=payload.chat_id,
                    text=payload.text,
                    buttons=payload.buttons,
                    parse_mode=payload.parse_mode,
                )
                self._outbox.mark_delivered(
                    message_id=row["message_id"],
                    chat_id=payload.chat_id,
                    telegram_message_id=message_id,
                )
            except Exception as exc:  # pragma: no cover - error path
                self._outbox.mark_failed(message_id=row["message_id"], error=str(exc))

    def _build_payload(self, row) -> TelegramMessagePayload:
        data = row["payload_json"]
        if isinstance(data, str):
            import json

            data = json.loads(data)
        return TelegramMessagePayload(
            chat_id=str(data["chat_id"]),
            text=str(data.get("text", "")),
            buttons=data.get("buttons", []),
            parse_mode=data.get("parse_mode"),
        )


class TelegramReplyRouter:
    def __init__(self, outbox: OutboxStore):
        self._outbox = outbox

    def handle_text_reply(
        self,
        *,
        chat_id: str,
        reply_to_message_id: int,
        text: str,
        parsed_response: dict,
    ) -> bool:
        if not parsed_response:
            return False
        return self._outbox.record_response_from_reply(
            chat_id=chat_id,
            reply_to_message_id=reply_to_message_id,
            response_json=parsed_response,
        )
