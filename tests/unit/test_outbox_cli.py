"""Unit tests for outbox CLI helpers (Story 027)."""

from __future__ import annotations

from datetime import datetime, timedelta

from mnemosyne.alexandria.message_outbox import MessageOutbox
from mnemosyne.cli import outbox as outbox_cli


def test_outbox_status_counts(tmp_path):
    outbox = MessageOutbox(str(tmp_path / "outbox.db"))
    outbox.enqueue(
        message_type="notification",
        payload={"text": "hello"},
        message_id="msg-1",
        originating_agent="project_manager",
    )
    outbox.enqueue(
        message_type="notification",
        payload={"text": "delivered"},
        message_id="msg-2",
        originating_agent="project_manager",
    )
    outbox.mark_delivered("msg-2", chat_id="chat-1", telegram_message_id=1)

    cli = outbox_cli.OutboxCLI(outbox)
    counts = cli.status()

    assert counts["pending"] == 1
    assert counts["delivered"] == 1


def test_outbox_inspect_returns_message(tmp_path):
    outbox = MessageOutbox(str(tmp_path / "outbox.db"))
    outbox.enqueue(
        message_type="notification",
        payload={"text": "inspect"},
        message_id="msg-10",
        originating_agent="project_manager",
    )

    cli = outbox_cli.OutboxCLI(outbox)
    message = cli.inspect("msg-10")

    assert message is not None
    assert message.message_id == "msg-10"


def test_outbox_requeue_failed_message(tmp_path):
    outbox = MessageOutbox(str(tmp_path / "outbox.db"))
    outbox.enqueue(
        message_type="notification",
        payload={"text": "retry"},
        message_id="msg-20",
        originating_agent="project_manager",
    )
    outbox.mark_failed("msg-20", "fail-1")
    outbox.mark_failed("msg-20", "fail-2")
    outbox.mark_failed("msg-20", "fail-3")

    cli = outbox_cli.OutboxCLI(outbox)
    cli.requeue("msg-20")

    message = outbox.get_by_message_id("msg-20")
    assert message.status == "pending"
    assert message.attempts == 0


def test_outbox_clear_delivered(tmp_path):
    outbox = MessageOutbox(str(tmp_path / "outbox.db"))
    outbox.enqueue(
        message_type="notification",
        payload={"text": "done"},
        message_id="msg-30",
        originating_agent="project_manager",
    )
    outbox.mark_delivered("msg-30", chat_id="chat-1", telegram_message_id=2)

    cutoff = (datetime.utcnow() + timedelta(seconds=1)).isoformat()
    cli = outbox_cli.OutboxCLI(outbox)
    removed = cli.clear_delivered(before_iso=cutoff)

    assert removed == 1
    assert outbox.get_by_message_id("msg-30") is None
