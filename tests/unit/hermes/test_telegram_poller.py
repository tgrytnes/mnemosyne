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
        def __init__(self) -> None:
            self.calls = 0
            self.loop = None

        async def get_updates(self, *, offset=None, timeout=None):
            import asyncio

            loop = asyncio.get_running_loop()
            if self.loop is None:
                self.loop = loop
            elif self.loop is not loop:
                raise RuntimeError("loop changed")
            self.calls += 1
            if self.calls > 1:
                return []
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
    poller.poll_replies()

    row = store.get_by_message_id("msg-urgency")
    assert row.response == {"question_type": "urgency", "value": 3}


def test_api_client_awaits_async_send_message(monkeypatch):
    import sys
    import types

    from mnemosyne.hermes.telegram_poller import TelegramApiClient

    class FakeMessage:
        def __init__(self, message_id: int):
            self.message_id = message_id

    class FakeBot:
        def __init__(self, token: str):
            self.token = token

        async def send_message(self, **_kwargs):
            return FakeMessage(123)

    fake_module = types.ModuleType("telegram")
    fake_module.Bot = FakeBot
    monkeypatch.setitem(sys.modules, "telegram", fake_module)

    client = TelegramApiClient(token="token")
    message_id = client.send_message(
        chat_id="chat-1",
        text="Hello",
        buttons=[],
        parse_mode=None,
    )

    assert message_id == 123


def test_poller_records_non_reply_when_single_pending(tmp_path):
    from mnemosyne.hermes.telegram_poller import TelegramOutboxPoller

    store = _make_store(tmp_path)
    store.enqueue(
        message_type="question",
        payload={"chat_id": "chat-5", "text": "Approve?", "question_type": "approval"},
        message_id="msg-nonreply",
        expects_response=True,
        originating_agent="project_manager",
        context_id="project:nonreply",
    )
    store.mark_delivered(message_id="msg-nonreply", chat_id="chat-5", telegram_message_id=930)

    client = FakeTelegramClient(updates=[FakeUpdate(FakeMessage(chat_id="chat-5", text="approve"))])
    poller = TelegramOutboxPoller(store, client)
    poller.poll_replies()

    row = store.get_by_message_id("msg-nonreply")
    assert row.response == {"decision": "approve"}


def test_poller_ignores_non_reply_when_multiple_pending(tmp_path):
    from mnemosyne.hermes.telegram_poller import TelegramOutboxPoller

    store = _make_store(tmp_path)
    store.enqueue(
        message_type="question",
        payload={"chat_id": "chat-6", "text": "Approve A?", "question_type": "approval"},
        message_id="msg-nonreply-a",
        expects_response=True,
        originating_agent="project_manager",
        context_id="project:nonreply-a",
    )
    store.enqueue(
        message_type="question",
        payload={"chat_id": "chat-6", "text": "Approve B?", "question_type": "approval"},
        message_id="msg-nonreply-b",
        expects_response=True,
        originating_agent="project_manager",
        context_id="project:nonreply-b",
    )
    store.mark_delivered(message_id="msg-nonreply-a", chat_id="chat-6", telegram_message_id=931)
    store.mark_delivered(message_id="msg-nonreply-b", chat_id="chat-6", telegram_message_id=932)

    client = FakeTelegramClient(updates=[FakeUpdate(FakeMessage(chat_id="chat-6", text="approve"))])
    poller = TelegramOutboxPoller(store, client)
    poller.poll_replies()

    row_a = store.get_by_message_id("msg-nonreply-a")
    row_b = store.get_by_message_id("msg-nonreply-b")
    assert row_a.response is None
    assert row_b.response is None
