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
    from mnemosyne.hermes.outbox_store import OutboxStore

    return OutboxStore(str(tmp_path / "outbox.db"))


def test_delivers_pending_outbox_messages(tmp_path):
    from mnemosyne.hermes.telegram_transport import TelegramOutboxConsumer

    store = _make_store(tmp_path)
    store.enqueue(
        message_id="msg-10",
        message_type="discovery_notification",
        payload_json={"chat_id": "chat-1", "text": "Hello", "buttons": [], "parse_mode": "Markdown"},
        expects_response=False,
        originating_agent="latent_scout",
        context_id="disc-10",
    )

    client = FakeTelegramClient()
    consumer = TelegramOutboxConsumer(store, client)
    consumer.deliver_pending(limit=5)

    row = store.get_by_message_id("msg-10")
    assert row["status"] == "delivered"
    assert row["telegram_message_id"] == 101
    assert row["chat_id"] == "chat-1"


def test_marks_failed_when_send_errors(tmp_path):
    from mnemosyne.hermes.telegram_transport import TelegramOutboxConsumer

    store = _make_store(tmp_path)
    store.enqueue(
        message_id="msg-11",
        message_type="discovery_notification",
        payload_json={"chat_id": "chat-2", "text": "Oops", "buttons": [], "parse_mode": "Markdown"},
        expects_response=False,
        originating_agent="latent_scout",
        context_id="disc-11",
    )

    client = FakeTelegramClient()
    client.fail = True
    consumer = TelegramOutboxConsumer(store, client)
    consumer.deliver_pending(limit=5)

    row = store.get_by_message_id("msg-11")
    assert row["status"] == "failed"
    assert row["last_error"] is not None


def test_reply_router_maps_reply_to_outbox(tmp_path):
    from mnemosyne.hermes.telegram_transport import TelegramReplyRouter

    store = _make_store(tmp_path)
    store.enqueue(
        message_id="msg-12",
        message_type="question",
        payload_json={"chat_id": "chat-3", "text": "Urgency?", "buttons": [], "parse_mode": None},
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
    assert row["response_json"] is not None


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
