from __future__ import annotations

from datetime import datetime

from mnemosyne.hermes.notification_rate_limiter import NotificationRateLimiter
from mnemosyne.hermes.outbox_store import OutboxStore


def test_rate_limiter_blocks_when_limit_reached(tmp_path):
    outbox = OutboxStore(str(tmp_path / "outbox.db"))
    limiter = NotificationRateLimiter(outbox)

    for idx in range(3):
        message_id = f"msg-{idx}"
        outbox.enqueue(
            message_id=message_id,
            message_type="discovery_project_candidate",
            payload_json={"title": f"Project {idx}"},
            expects_response=False,
            originating_agent="latent_scout",
            context_id=f"disc-{idx}",
        )
        outbox.mark_delivered(
            message_id=message_id,
            chat_id="chat-1",
            telegram_message_id=200 + idx,
        )

    assert limiter.can_send(chat_id="chat-1", max_daily_notifications=3) is False


def test_rate_limiter_allows_below_limit(tmp_path):
    outbox = OutboxStore(str(tmp_path / "outbox.db"))
    limiter = NotificationRateLimiter(outbox)

    outbox.enqueue(
        message_id="msg-1",
        message_type="discovery_project_candidate",
        payload_json={"title": "Project 1"},
        expects_response=False,
        originating_agent="latent_scout",
        context_id="disc-1",
    )
    outbox.mark_delivered(message_id="msg-1", chat_id="chat-1", telegram_message_id=201)

    assert (
        limiter.can_send(chat_id="chat-1", max_daily_notifications=3, now=datetime.utcnow()) is True
    )
