from __future__ import annotations

from datetime import datetime

from mnemosyne.alexandria.message_outbox import MessageOutbox
from mnemosyne.hermes.notification_rate_limiter import NotificationRateLimiter


def test_rate_limiter_blocks_when_limit_reached(tmp_path):
    outbox = MessageOutbox(str(tmp_path / "outbox.db"))
    limiter = NotificationRateLimiter(outbox)

    for idx in range(3):
        message_id = f"msg-{idx}"
        outbox.enqueue(
            message_type="notification",
            payload={"title": f"Project {idx}"},
            message_id=message_id,
            expects_response=False,
            originating_agent="project_manager",
            context_id=f"disc-{idx}",
        )
        outbox.mark_delivered(
            message_id=message_id,
            chat_id="chat-1",
            telegram_message_id=200 + idx,
        )

    assert limiter.can_send(chat_id="chat-1", max_daily_notifications=3) is False


def test_rate_limiter_allows_below_limit(tmp_path):
    outbox = MessageOutbox(str(tmp_path / "outbox.db"))
    limiter = NotificationRateLimiter(outbox)

    outbox.enqueue(
        message_type="notification",
        payload={"title": "Project 1"},
        message_id="msg-1",
        expects_response=False,
        originating_agent="project_manager",
        context_id="disc-1",
    )
    outbox.mark_delivered(message_id="msg-1", chat_id="chat-1", telegram_message_id=201)

    assert (
        limiter.can_send(chat_id="chat-1", max_daily_notifications=3, now=datetime.utcnow()) is True
    )
