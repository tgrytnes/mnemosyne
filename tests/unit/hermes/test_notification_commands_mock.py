from unittest.mock import MagicMock

from mnemosyne.hermes.notification_commands import NotificationCommandHandler
from mnemosyne.hermes.notification_preferences import NotificationPreferences


def test_handle_notify_settings_creates_defaults_with_mock_repo():
    repo = MagicMock()
    repo.get.return_value = None
    handler = NotificationCommandHandler(repo, MagicMock())

    message = handler.handle_notify_settings(user_id="user-123")

    repo.save.assert_called_once()
    saved = repo.save.call_args[0][0]
    assert isinstance(saved, NotificationPreferences)
    assert "Notification settings" in message


def test_handle_quiet_hours_updates_existing_preferences():
    prefs = NotificationPreferences(user_id="user-1")
    repo = MagicMock()
    repo.get.return_value = prefs
    handler = NotificationCommandHandler(repo, MagicMock())

    handler.handle_quiet_hours(user_id="user-1", start_hour=20, end_hour=7)

    repo.save.assert_called_once()
    updated = repo.save.call_args[0][0]
    assert updated.quiet_start_hour == 20
    assert updated.quiet_end_hour == 7


def test_handle_discoveries_returns_from_outbox_history():
    outbox = MagicMock()
    outbox.list_recent_by_chat.return_value = [
        MagicMock(
            message_id="a",
            message_type="notification",
            payload={"title": "Test", "discovery_id": "disc-1"},
        )
    ]
    handler = NotificationCommandHandler(MagicMock(), outbox)

    message = handler.handle_discoveries(chat_id="chat-1", limit=3)
    assert "Test" in message
