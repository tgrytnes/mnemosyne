from __future__ import annotations

import json
import time
from collections.abc import Callable

from mnemosyne.hermes.telegram_transport import (
    TelegramOutboxConsumer,
    TelegramReplyRouter,
    _resolve_maybe_async,
)


class TelegramApiClient:
    """Thin wrapper around python-telegram-bot for the poller interface."""

    def __init__(self, token: str) -> None:
        from telegram import Bot

        self._bot = Bot(token=token)

    def send_message(
        self,
        *,
        chat_id: str,
        text: str,
        buttons: list,
        parse_mode: str | None,
    ) -> int:
        reply_markup = _build_reply_markup(buttons)
        message = _resolve_maybe_async(
            self._bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
        )
        return message.message_id

    def get_updates(self, *, offset: int | None = None, timeout: int | None = None):
        return self._bot.get_updates(offset=offset, timeout=timeout)


class TelegramOutboxPoller:
    def __init__(
        self,
        outbox,
        telegram_client,
        *,
        default_chat_id: str | None = None,
        poll_interval_seconds: int = 30,
        reply_timeout_seconds: int = 25,
        send_limit: int = 10,
        response_router: Callable[[str, dict], None] | None = None,
    ) -> None:
        self._outbox = outbox
        self._client = telegram_client
        self._consumer = TelegramOutboxConsumer(
            outbox,
            telegram_client,
            default_chat_id=default_chat_id,
        )
        self._reply_router = TelegramReplyRouter(outbox)
        self._poll_interval_seconds = poll_interval_seconds
        self._reply_timeout_seconds = reply_timeout_seconds
        self._send_limit = send_limit
        self._response_router = response_router
        self._last_update_id: int | None = None

    def deliver_pending(self) -> None:
        self._consumer.deliver_pending(limit=self._send_limit)

    def poll_replies(self) -> None:
        updates = _resolve_maybe_async(
            self._client.get_updates(
                offset=self._next_update_offset(),
                timeout=self._reply_timeout_seconds,
            )
        )
        for update in updates:
            self._handle_update(update)
            self._advance_offset(update)

    def run_forever(self, *, stop_signal: Callable[[], bool]) -> None:
        while not stop_signal():
            start = time.monotonic()
            self.deliver_pending()
            self.poll_replies()
            elapsed = time.monotonic() - start
            sleep_for = max(0.0, self._poll_interval_seconds - elapsed)
            if sleep_for:
                time.sleep(sleep_for)

    def _next_update_offset(self) -> int | None:
        if self._last_update_id is None:
            return None
        return self._last_update_id + 1

    def _advance_offset(self, update) -> None:
        update_id = getattr(update, "update_id", None)
        if update_id is None:
            return
        self._last_update_id = update_id

    def _handle_update(self, update) -> None:
        message = getattr(update, "message", None)
        if not message:
            return
        reply_to = getattr(message, "reply_to_message", None)
        if not reply_to:
            return
        reply_to_message_id = getattr(reply_to, "message_id", None)
        if reply_to_message_id is None:
            return
        chat_id = str(getattr(message, "chat_id", ""))
        text = getattr(message, "text", "") or ""
        context_id, question_type = self._find_outbox_context(chat_id, reply_to_message_id)
        if not context_id:
            return
        parsed_response = _parse_response(text, context_id, question_type)
        if not parsed_response:
            return
        agent = self._reply_router.handle_text_reply(
            chat_id=chat_id,
            reply_to_message_id=reply_to_message_id,
            text=text,
            parsed_response=parsed_response,
        )
        if agent and self._response_router:
            self._response_router(context_id, parsed_response)

    def _find_outbox_context(
        self, chat_id: str, reply_to_message_id: int
    ) -> tuple[str | None, str | None]:
        cursor = self._outbox.db.cursor()
        cursor.execute(
            """
            SELECT context_id, payload_json
            FROM message_outbox
            WHERE chat_id = ?
            AND telegram_message_id = ?
            AND expects_response = 1
            AND status = 'awaiting_response'
            LIMIT 1
            """,
            (chat_id, reply_to_message_id),
        )
        row = cursor.fetchone()
        if not row:
            return None, None
        payload = json.loads(row["payload_json"]) if row["payload_json"] else {}
        return row["context_id"], payload.get("question_type")


def _build_reply_markup(buttons: list):
    if not buttons:
        return None
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    except Exception:  # pragma: no cover - optional at runtime
        return None
    rows: list[list[InlineKeyboardButton]] = []
    if buttons and isinstance(buttons[0], dict):
        buttons = [buttons]
    for row in buttons:
        row_buttons: list[InlineKeyboardButton] = []
        for button in row:
            if isinstance(button, dict):
                text = button.get("text")
                data = button.get("callback_data") or button.get("data")
            elif isinstance(button, (list, tuple)) and len(button) >= 2:
                text, data = button[0], button[1]
            else:
                text = None
                data = None
            if not text or data is None:
                continue
            row_buttons.append(InlineKeyboardButton(text=str(text), callback_data=str(data)))
        if row_buttons:
            rows.append(row_buttons)
    return InlineKeyboardMarkup(rows) if rows else None


def _parse_response(text: str, context_id: str, question_type: str | None) -> dict | None:
    cleaned = text.strip()
    if not cleaned:
        return None

    if context_id.startswith("discovery:"):
        decision = _parse_decision(cleaned)
        if decision:
            return {"decision": decision}

    if question_type == "approval":
        decision = _parse_decision(cleaned)
        if decision:
            return {"decision": decision}

    if question_type in {"importance", "urgency"}:
        try:
            value = int(cleaned)
        except ValueError:
            return None
        return {"question_type": question_type, "value": value}

    if question_type in {"deadline", "description"}:
        return {"question_type": question_type, "value": cleaned}

    return None


def _parse_decision(text: str) -> str | None:
    normalized = text.strip().lower()
    if normalized in {"approve", "approved", "yes", "y"}:
        return "approve"
    if normalized in {"reject", "rejected", "no", "n"}:
        return "reject"
    return None
