import json
import sqlite3


def _make_store(tmp_path):
    from mnemosyne.hermes.outbox_store import OutboxStore

    db_path = tmp_path / "outbox.db"
    return OutboxStore(str(db_path))


def test_enqueue_and_fetch_pending(tmp_path):
    store = _make_store(tmp_path)
    message_id = "msg-001"
    payload = {"text": "hello", "chat_id": "123"}
    store.enqueue(
        message_id=message_id,
        message_type="discovery_notification",
        payload_json=payload,
        expects_response=False,
        originating_agent="latent_scout",
        context_id="disc-1",
    )

    pending = store.fetch_pending(limit=10)
    assert len(pending) == 1
    assert pending[0]["message_id"] == message_id
    assert json.loads(pending[0]["payload_json"]) == payload


def test_mark_delivered_stores_telegram_mapping(tmp_path):
    store = _make_store(tmp_path)
    message_id = "msg-002"
    store.enqueue(
        message_id=message_id,
        message_type="question",
        payload_json={"text": "importance?"},
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
    assert row["status"] == "delivered"
    assert row["telegram_message_id"] == 555
    assert row["chat_id"] == "chat-1"


def test_record_response_by_telegram_reply(tmp_path):
    store = _make_store(tmp_path)
    message_id = "msg-003"
    store.enqueue(
        message_id=message_id,
        message_type="question",
        payload_json={"text": "urgency?"},
        expects_response=True,
        originating_agent="project_manager",
        context_id="project-99",
    )
    store.mark_delivered(message_id=message_id, chat_id="chat-1", telegram_message_id=777)

    store.record_response_from_reply(
        chat_id="chat-1",
        reply_to_message_id=777,
        response_json={"urgency": 5},
    )

    row = store.get_by_message_id(message_id)
    assert row["response_json"] == json.dumps({"urgency": 5})
    assert row["response_received_at"] is not None


def test_reply_to_unknown_message_is_noop(tmp_path):
    store = _make_store(tmp_path)
    store.record_response_from_reply(
        chat_id="chat-1",
        reply_to_message_id=999,
        response_json={"importance": 4},
    )
    # No rows should exist, and no exception should be raised.
    assert store.fetch_pending(limit=10) == []

