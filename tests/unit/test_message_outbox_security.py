"""Unit tests for message outbox hardening and scheduling behavior."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from mnemosyne.alexandria.message_outbox import MessageOutbox


def test_ensure_column_rejects_invalid_identifier(tmp_path):
    outbox = MessageOutbox(str(tmp_path / "outbox.db"))
    with pytest.raises(ValueError, match="invalid column"):
        outbox._ensure_column("chat_id); DROP TABLE message_outbox;--", "TEXT")


def test_enqueue_rejects_non_pm_originating_agent(tmp_path):
    outbox = MessageOutbox(str(tmp_path / "outbox.db"))
    with pytest.raises(ValueError, match="project_manager"):
        outbox.enqueue(
            message_type="notification",
            payload={"text": "hello"},
            originating_agent="gatekeeper",
            context_id="project:1",
        )


def test_mark_failed_records_utc_timezone(tmp_path):
    outbox = MessageOutbox(str(tmp_path / "outbox.db"))
    message_id = outbox.enqueue(
        message_type="notification",
        payload={"text": "retry"},
        originating_agent="project_manager",
    )

    outbox.mark_failed(message_id, error="oops")
    message = outbox.get_by_message_id(message_id)

    assert message is not None
    assert message.next_attempt_at is not None
    assert message.next_attempt_at.tzinfo == UTC


def test_fetch_pending_skips_future_entries_and_returns_next_due(tmp_path):
    outbox = MessageOutbox(str(tmp_path / "outbox.db"))
    future_id = outbox.enqueue(
        message_type="notification",
        payload={"text": "future"},
        message_id="future",
        originating_agent="project_manager",
    )
    future_time = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    cursor = outbox.db.cursor()
    cursor.execute(
        "UPDATE message_outbox SET next_attempt_at = ? WHERE message_id = ?",
        (future_time, future_id),
    )
    outbox.db.commit()

    ready_id = outbox.enqueue(
        message_type="notification",
        payload={"text": "ready"},
        message_id="ready",
        originating_agent="project_manager",
    )

    pending = outbox.fetch_pending(limit=1)

    assert [message.message_id for message in pending] == [ready_id]


def test_next_attempt_at_index_exists(tmp_path):
    outbox = MessageOutbox(str(tmp_path / "outbox.db"))
    cursor = outbox.db.cursor()
    cursor.execute("PRAGMA index_list(message_outbox)")
    index_names = {row[1] for row in cursor.fetchall()}

    assert any("next_attempt" in name for name in index_names)
