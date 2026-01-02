from datetime import datetime
from unittest.mock import MagicMock

from mnemosyne.hermes.notification_rate_limiter import NotificationRateLimiter


def test_rate_limiter_blocks_when_count_ge_limit():
    outbox = MagicMock()
    outbox.count_delivered_since.return_value = 3
    limiter = NotificationRateLimiter(outbox)

    assert limiter.can_send(chat_id="chat-42", max_daily_notifications=3) is False
    outbox.count_delivered_since.assert_called_once()


def test_rate_limiter_allows_when_below_limit():
    outbox = MagicMock()
    outbox.count_delivered_since.return_value = 1
    limiter = NotificationRateLimiter(outbox)

    now = datetime(2025, 1, 1, 12, 0)
    assert limiter.can_send(chat_id="chat-5", max_daily_notifications=3, now=now) is True
    outbox.count_delivered_since.assert_called_once()
