from __future__ import annotations

from mnemosyne.alexandria.message_outbox import MessageOutbox
from mnemosyne.hermes.notification_commands import NotificationCommandHandler
from mnemosyne.hermes.notification_preferences import NotificationPreferences


class InMemoryPreferencesRepo:
    def __init__(self):
        self._store: dict[str, NotificationPreferences] = {}

    def get(self, user_id: str) -> NotificationPreferences | None:
        return self._store.get(user_id)

    def save(self, preferences: NotificationPreferences) -> None:
        self._store[preferences.user_id] = preferences


def _make_handler(tmp_path):
    repo = InMemoryPreferencesRepo()
    outbox = MessageOutbox(str(tmp_path / "outbox.db"))
    return NotificationCommandHandler(repo, outbox), repo


def test_handle_notify_settings_creates_defaults(tmp_path):
    handler, repo = _make_handler(tmp_path)

    message = handler.handle_notify_settings(user_id="user-1")

    assert "Max daily notifications" in message
    assert repo.get("user-1") is not None


def test_handle_quiet_hours_updates_preferences(tmp_path):
    handler, repo = _make_handler(tmp_path)

    message = handler.handle_quiet_hours(user_id="user-1", start_hour=22, end_hour=6)

    prefs = repo.get("user-1")
    assert prefs is not None
    assert prefs.quiet_start_hour == 22
    assert prefs.quiet_end_hour == 6
    assert "Quiet hours" in message


def test_handle_discoveries_returns_empty_message(tmp_path):
    handler, _ = _make_handler(tmp_path)

    message = handler.handle_discoveries(chat_id="chat-1", limit=5)

    assert "No discovery notifications yet" in message


def test_handle_discoveries_lists_recent(tmp_path):
    handler, _ = _make_handler(tmp_path)
    outbox = handler.outbox

    outbox.enqueue(
        message_type="notification",
        payload={"title": "Kitchen Remodel", "discovery_id": "disc-1"},
        message_id="msg-1",
        expects_response=False,
        originating_agent="project_manager",
        context_id="discovery:disc-1",
    )
    outbox.mark_delivered(message_id="msg-1", chat_id="chat-1", telegram_message_id=101)

    message = handler.handle_discoveries(chat_id="chat-1", limit=5)

    assert "Kitchen Remodel" in message
