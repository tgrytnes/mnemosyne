import json


class FakeTelegramClient:
    def __init__(self):
        self.sent = []
        self.fail = False

    def send_message(self, *, chat_id: str, text: str, buttons: list, parse_mode: str | None):
        if self.fail:
            raise RuntimeError("send failed")
        message_id = 101 + len(self.sent)
        self.sent.append(
            {
                "chat_id": chat_id,
                "text": text,
                "buttons": buttons,
                "parse_mode": parse_mode,
                "message_id": message_id,
            }
        )
        return message_id


def _make_store(tmp_path):
    from mnemosyne.alexandria.message_outbox import MessageOutbox

    return MessageOutbox(str(tmp_path / "outbox.db"))


def test_delivers_pending_outbox_messages(tmp_path):
    from mnemosyne.hermes.telegram_transport import TelegramOutboxConsumer

    store = _make_store(tmp_path)
    store.enqueue(
        message_type="notification",
        payload={
            "chat_id": "chat-1",
            "text": "Hello",
            "buttons": [],
            "parse_mode": "Markdown",
        },
        message_id="msg-10",
        expects_response=False,
        originating_agent="project_manager",
        context_id="disc-10",
    )

    client = FakeTelegramClient()
    consumer = TelegramOutboxConsumer(store, client)
    consumer.deliver_pending(limit=5)

    row = store.get_by_message_id("msg-10")
    assert row.status == "delivered"
    assert row.telegram_message_id == 101
    assert row.chat_id == "chat-1"


def test_marks_failed_when_send_errors(tmp_path):
    from mnemosyne.hermes.telegram_transport import TelegramOutboxConsumer

    store = _make_store(tmp_path)
    store.enqueue(
        message_type="notification",
        payload={"chat_id": "chat-2", "text": "Oops", "buttons": [], "parse_mode": "Markdown"},
        message_id="msg-11",
        expects_response=False,
        originating_agent="project_manager",
        context_id="disc-11",
    )

    client = FakeTelegramClient()
    client.fail = True
    consumer = TelegramOutboxConsumer(store, client)
    consumer.deliver_pending(limit=5)

    row = store.get_by_message_id("msg-11")
    assert row.status == "pending"
    assert row.last_error is not None


def test_reply_router_maps_reply_to_outbox(tmp_path):
    from mnemosyne.hermes.telegram_transport import TelegramReplyRouter

    store = _make_store(tmp_path)
    store.enqueue(
        message_type="question",
        payload={"chat_id": "chat-3", "text": "Urgency?", "buttons": [], "parse_mode": None},
        message_id="msg-12",
        expects_response=True,
        originating_agent="project_manager",
        context_id="project-12",
    )
    store.mark_delivered(message_id="msg-12", chat_id="chat-3", telegram_message_id=777)

    router = TelegramReplyRouter(store)
    handled = router.handle_text_reply(
        chat_id="chat-3",
        reply_to_message_id=777,
        text="5",
        parsed_response={"urgency": 5},
    )

    assert handled is True
    row = store.get_by_message_id("msg-12")
    assert row.response is not None


def test_reply_router_ignores_unknown_reply(tmp_path):
    from mnemosyne.hermes.telegram_transport import TelegramReplyRouter

    store = _make_store(tmp_path)
    router = TelegramReplyRouter(store)
    handled = router.handle_text_reply(
        chat_id="chat-4",
        reply_to_message_id=999,
        text="hello",
        parsed_response={"importance": 3},
    )

    assert handled is False


def test_consumer_skips_non_pm_messages(tmp_path):
    from mnemosyne.hermes.telegram_transport import TelegramOutboxConsumer

    store = _make_store(tmp_path)
    cursor = store.db.cursor()
    cursor.execute(
        """
        INSERT INTO message_outbox (
            message_id,
            message_type,
            originating_agent,
            context_id,
            payload_json,
            expects_response,
            status
        ) VALUES (?, ?, ?, ?, ?, ?, 'pending')
        """,
        (
            "msg-gk",
            "notification",
            "gatekeeper",
            "project:1",
            json.dumps(
                {
                    "chat_id": "chat-1",
                    "text": "Gatekeeper",
                    "buttons": [],
                    "parse_mode": None,
                }
            ),
            False,
        ),
    )
    store.db.commit()
    store.enqueue(
        message_type="notification",
        payload={"chat_id": "chat-1", "text": "PM", "buttons": [], "parse_mode": None},
        message_id="msg-pm",
        originating_agent="project_manager",
        context_id="project:1",
        expects_response=False,
    )

    client = FakeTelegramClient()
    consumer = TelegramOutboxConsumer(store, client)
    consumer.deliver_pending(limit=5)

    assert len(client.sent) == 1
    assert client.sent[0]["text"] == "PM"
    gatekeeper_row = store.get_by_message_id("msg-gk")
    assert gatekeeper_row.status == "pending"


def test_consumer_uses_default_chat_id_when_missing(tmp_path):
    from mnemosyne.hermes.telegram_transport import TelegramOutboxConsumer

    store = _make_store(tmp_path)
    store.enqueue(
        message_type="notification",
        payload={"text": "Hello", "buttons": [], "parse_mode": None},
        message_id="msg-default-chat",
        expects_response=False,
        originating_agent="project_manager",
        context_id="project:default",
    )

    client = FakeTelegramClient()
    consumer = TelegramOutboxConsumer(store, client, default_chat_id="chat-default")
    consumer.deliver_pending(limit=5)

    row = store.get_by_message_id("msg-default-chat")
    assert row.status == "delivered"
    assert client.sent[0]["chat_id"] == "chat-default"


def test_consumer_handles_async_send_message(tmp_path):
    from mnemosyne.hermes.telegram_transport import TelegramOutboxConsumer

    class AsyncTelegramClient:
        async def send_message(self, *, chat_id: str, text: str, buttons: list, parse_mode):
            return 4242

    store = _make_store(tmp_path)
    store.enqueue(
        message_type="notification",
        payload={"chat_id": "chat-async", "text": "Hello", "buttons": [], "parse_mode": None},
        message_id="msg-async",
        expects_response=False,
        originating_agent="project_manager",
        context_id="project:async",
    )

    consumer = TelegramOutboxConsumer(store, AsyncTelegramClient())
    consumer.deliver_pending(limit=5)

    row = store.get_by_message_id("msg-async")
    assert row.status == "delivered"
