from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from typing import Any

from mnemosyne.alexandria.message_outbox import MessageOutbox


@dataclass
class TelegramMessagePayload:
    chat_id: str | None
    text: str
    buttons: list
    parse_mode: str | None


class TelegramOutboxConsumer:
    def __init__(
        self,
        outbox: MessageOutbox,
        telegram_client,
        default_chat_id: str | None = None,
    ):
        self._outbox = outbox
        self._client = telegram_client
        self._default_chat_id = default_chat_id

    def deliver_pending(self, *, limit: int = 10) -> None:
        pending = self._outbox.fetch_pending(limit=limit)
        for row in pending:
            if row.originating_agent and row.originating_agent != "project_manager":
                continue
            payload = self._build_payload(row)
            if not payload.chat_id:
                self._outbox.mark_failed(
                    message_id=row.message_id,
                    error="missing chat_id for delivery",
                )
                continue
            try:
                message_id = _resolve_maybe_async(
                    self._client.send_message(
                        chat_id=payload.chat_id,
                        text=payload.text,
                        buttons=payload.buttons,
                        parse_mode=payload.parse_mode,
                    )
                )
                if hasattr(message_id, "message_id"):
                    message_id = message_id.message_id
                self._outbox.mark_delivered(
                    message_id=row.message_id,
                    chat_id=payload.chat_id,
                    telegram_message_id=message_id,
                )
            except Exception as exc:  # pragma: no cover - error path
                self._outbox.mark_failed(message_id=row.message_id, error=str(exc))

    def _build_payload(self, row) -> TelegramMessagePayload:
        data = row.payload if hasattr(row, "payload") else row["payload_json"]
        if isinstance(data, str):
            import json

            data = json.loads(data)
        return TelegramMessagePayload(
            chat_id=str(data["chat_id"]) if data.get("chat_id") else self._default_chat_id,
            text=str(data.get("text", "")),
            buttons=data.get("buttons", []),
            parse_mode=data.get("parse_mode"),
        )


class TelegramReplyRouter:
    def __init__(self, outbox: MessageOutbox):
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
        agent = self._outbox.record_response_from_reply(
            chat_id=chat_id,
            reply_to_message_id=reply_to_message_id,
            response_json=parsed_response,
        )
        return agent is not None


def _resolve_maybe_async(result: Any) -> Any:
    if not inspect.isawaitable(result):
        return result
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(result)
    if loop.is_running():
        raise RuntimeError("Async Telegram client requires a non-running event loop.")
    return loop.run_until_complete(result)
