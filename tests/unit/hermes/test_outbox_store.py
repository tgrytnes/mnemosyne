from mnemosyne.alexandria.message_outbox import MessageOutbox


def _make_store(tmp_path):
    db_path = tmp_path / "outbox.db"
    return MessageOutbox(str(db_path))


def test_enqueue_and_fetch_pending(tmp_path):
    store = _make_store(tmp_path)
    message_id = "msg-001"
    payload = {"text": "hello", "chat_id": "123"}
    store.enqueue(
        message_type="notification",
        payload=payload,
        message_id=message_id,
        expects_response=False,
        originating_agent="project_manager",
        context_id="disc-1",
    )

    pending = store.fetch_pending(limit=10)
    assert len(pending) == 1
    assert pending[0].message_id == message_id
    assert pending[0].payload == payload


def test_mark_delivered_stores_telegram_mapping(tmp_path):
    store = _make_store(tmp_path)
    message_id = store.enqueue(
        message_type="question",
        payload={"text": "importance?"},
        message_id="msg-002",
        expects_response=True,
        originating_agent="project_manager",
        context_id="project-42",
    )

    store.mark_delivered(
        message_id=message_id,
        chat_id="chat-1",
        telegram_message_id=555,
    )

    row = store.get_by_message_id(message_id)
    assert row.status == "awaiting_response"
    assert row.telegram_message_id == 555
    assert row.chat_id == "chat-1"
    assert row.delivered_at is not None


def test_record_response_by_telegram_reply(tmp_path):
    store = _make_store(tmp_path)
    message_id = store.enqueue(
        message_type="question",
        payload={"text": "urgency?"},
        message_id="msg-003",
        expects_response=True,
        originating_agent="project_manager",
        context_id="project-99",
    )
    store.mark_delivered(message_id=message_id, chat_id="chat-1", telegram_message_id=777)

    agent = store.record_response_from_reply(
        chat_id="chat-1",
        reply_to_message_id=777,
        response_json={"urgency": 5},
    )

    row = store.get_by_message_id(message_id)
    assert agent == "project_manager"
    assert row.response == {"urgency": 5}
    assert row.response_received_at is not None
    assert row.status == "delivered"


def test_reply_to_unknown_message_is_noop(tmp_path):
    store = _make_store(tmp_path)
    agent = store.record_response_from_reply(
        chat_id="chat-1",
        reply_to_message_id=999,
        response_json={"importance": 4},
    )
    # No rows should exist, and no exception should be raised.
    assert agent is None
    assert store.fetch_pending(limit=10) == []


def test_list_recent_by_chat_filters_on_prefix(tmp_path):
    store = _make_store(tmp_path)
    store.enqueue(
        message_type="notification",
        payload={"title": "Home Office"},
        message_id="msg-10",
        expects_response=False,
        originating_agent="project_manager",
        context_id="disc-10",
    )
    store.enqueue(
        message_type="notification",
        payload={"title": "System"},
        message_id="msg-11",
        expects_response=False,
        originating_agent="project_manager",
        context_id="sys-1",
    )
    store.mark_delivered(message_id="msg-10", chat_id="chat-1", telegram_message_id=1)
    store.mark_delivered(message_id="msg-11", chat_id="chat-1", telegram_message_id=2)

    rows = store.list_recent_by_chat(
        chat_id="chat-1",
        limit=10,
        message_type_prefix="notification",
    )

    assert len(rows) == 2
    assert {row.message_id for row in rows} == {"msg-10", "msg-11"}


def test_count_delivered_since(tmp_path):
    store = _make_store(tmp_path)
    for idx in range(3):
        message_id = f"msg-{idx}"
        store.enqueue(
            message_type="notification",
            payload={"title": f"Project {idx}"},
            message_id=message_id,
            expects_response=False,
            originating_agent="project_manager",
            context_id=f"disc-{idx}",
        )
        store.mark_delivered(
            message_id=message_id,
            chat_id="chat-1",
            telegram_message_id=100 + idx,
        )

    assert store.count_delivered_since(chat_id="chat-1", since_iso="2000-01-01T00:00:00") == 3
