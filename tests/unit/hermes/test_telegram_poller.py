class FakeMessage:
    def __init__(
        self,
        *,
        chat_id: str,
        text: str,
        reply_to_message_id: int | None = None,
        message_id: int = 500,
    ) -> None:
        self.chat_id = chat_id
        self.text = text
        self.message_id = message_id
        self.reply_to_message = None
        if reply_to_message_id is not None:
            self.reply_to_message = type("Reply", (), {"message_id": reply_to_message_id})


class FakeUpdate:
    def __init__(self, message: FakeMessage) -> None:
        self.message = message


class FakeTelegramClient:
    def __init__(self, updates):
        self.updates = updates

    def get_updates(self, *, offset: int | None = None, timeout: int | None = None):
        return self.updates


def _make_store(tmp_path):
    from mnemosyne.alexandria.message_outbox import MessageOutbox

    return MessageOutbox(str(tmp_path / "outbox.db"))


def test_poller_records_project_reply(tmp_path):
    from mnemosyne.hermes.telegram_poller import TelegramOutboxPoller

    store = _make_store(tmp_path)
    store.enqueue(
        message_type="question",
        payload={"chat_id": "chat-1", "text": "Rate 1-5", "question_type": "importance"},
        message_id="msg-imp",
        expects_response=True,
        originating_agent="project_manager",
        context_id="project:1",
    )
    store.mark_delivered(message_id="msg-imp", chat_id="chat-1", telegram_message_id=900)

    client = FakeTelegramClient(
        updates=[
            FakeUpdate(
                FakeMessage(chat_id="chat-1", text="4", reply_to_message_id=900, message_id=901)
            )
        ]
    )
    poller = TelegramOutboxPoller(store, client)
    poller.poll_replies()

    row = store.get_by_message_id("msg-imp")
    assert row.response == {"question_type": "importance", "value": 4}


def test_poller_records_discovery_decision(tmp_path):
    from mnemosyne.hermes.telegram_poller import TelegramOutboxPoller

    store = _make_store(tmp_path)
    store.enqueue(
        message_type="question",
        payload={"chat_id": "chat-2", "text": "Approve?", "question_type": "approval"},
        message_id="msg-approval",
        expects_response=True,
        originating_agent="project_manager",
        context_id="discovery:abc123",
    )
    store.mark_delivered(message_id="msg-approval", chat_id="chat-2", telegram_message_id=910)

    client = FakeTelegramClient(
        updates=[
            FakeUpdate(
                FakeMessage(
                    chat_id="chat-2",
                    text="approve",
                    reply_to_message_id=910,
                    message_id=911,
                )
            )
        ]
    )
    poller = TelegramOutboxPoller(store, client)
    poller.poll_replies()

    row = store.get_by_message_id("msg-approval")
    assert row.response == {"decision": "approve"}


def test_poller_handles_async_get_updates(tmp_path):
    from mnemosyne.hermes.telegram_poller import TelegramOutboxPoller

    class AsyncTelegramClient:
        async def get_updates(self, *, offset=None, timeout=None):
            return [
                FakeUpdate(
                    FakeMessage(
                        chat_id="chat-3",
                        text="3",
                        reply_to_message_id=920,
                        message_id=921,
                    )
                )
            ]

    store = _make_store(tmp_path)
    store.enqueue(
        message_type="question",
        payload={"chat_id": "chat-3", "text": "Urgency?", "question_type": "urgency"},
        message_id="msg-urgency",
        expects_response=True,
        originating_agent="project_manager",
        context_id="project:3",
    )
    store.mark_delivered(message_id="msg-urgency", chat_id="chat-3", telegram_message_id=920)

    poller = TelegramOutboxPoller(store, AsyncTelegramClient())
    poller.poll_replies()

    row = store.get_by_message_id("msg-urgency")
    assert row.response == {"question_type": "urgency", "value": 3}
