"""
Unit tests for Message Outbox (Story 027)

Tests the Producer API and Consumer API for the message outbox system
that enables transport-agnostic agent-to-user communication with response routing.

TDD Approach: These tests are written BEFORE implementation.
"""

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

# ==============================================================================
# Test Fixtures
# ==============================================================================


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for testing"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    yield db_path

    # Cleanup
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def outbox_db(temp_db):
    """Create message outbox database with schema"""
    conn = sqlite3.connect(temp_db)
    conn.row_factory = sqlite3.Row

    # Create schema (this will be moved to migration later)
    conn.execute(
        """
        CREATE TABLE message_outbox (
            id INTEGER PRIMARY KEY,
            message_id TEXT NOT NULL UNIQUE,
            message_type TEXT NOT NULL,
            originating_agent TEXT,
            context_id TEXT,
            payload_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            expects_response BOOLEAN DEFAULT FALSE,
            response_received_at TIMESTAMP,
            response_json TEXT,
            attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_attempted_at TIMESTAMP,
            delivered_at TIMESTAMP
        )
    """
    )

    conn.execute("CREATE INDEX idx_outbox_status ON message_outbox(status)")
    conn.execute("CREATE INDEX idx_outbox_type ON message_outbox(message_type)")
    conn.execute("CREATE INDEX idx_outbox_agent ON message_outbox(originating_agent)")
    conn.execute("CREATE INDEX idx_outbox_context ON message_outbox(context_id)")

    conn.commit()

    yield conn

    conn.close()


@pytest.fixture
def message_outbox(outbox_db):
    """Create MessageOutbox instance"""
    from mnemosyne.alexandria.message_outbox import MessageOutbox

    return MessageOutbox(outbox_db)


# ==============================================================================
# Producer API Tests (Enqueuing Messages)
# ==============================================================================


class TestProducerAPI:
    """Test the Producer API used by agents to enqueue messages"""

    def test_enqueue_simple_notification(self, message_outbox):
        """Test enqueuing a simple notification message"""
        message_id = message_outbox.enqueue(
            message_type="notification",
            payload={"text": "Hello user!"},
            originating_agent="test_agent",
            context_id="test:123",
        )

        assert message_id is not None
        assert message_id.startswith("notification:test:123:")

    def test_enqueue_with_custom_message_id(self, message_outbox):
        """Test enqueuing with a custom message ID for idempotency"""
        custom_id = "approval_request:disco_001"

        message_id = message_outbox.enqueue(
            message_type="approval_request",
            payload={"text": "Approve this?"},
            message_id=custom_id,
            originating_agent="gatekeeper",
            context_id="discovery:disco_001",
        )

        assert message_id == custom_id

    def test_enqueue_idempotency(self, message_outbox):
        """Test that duplicate message_id does not create duplicate records"""
        custom_id = "notification:project:42:importance"

        # Enqueue first time
        message_id_1 = message_outbox.enqueue(
            message_type="notification",
            payload={"text": "First message"},
            message_id=custom_id,
            originating_agent="project_manager",
        )

        # Enqueue second time with same ID (should be ignored)
        message_id_2 = message_outbox.enqueue(
            message_type="notification",
            payload={"text": "Second message (should be ignored)"},
            message_id=custom_id,
            originating_agent="project_manager",
        )

        assert message_id_1 == message_id_2

        # Verify only one record exists
        cursor = message_outbox.db.cursor()
        cursor.execute("SELECT COUNT(*) FROM message_outbox WHERE message_id = ?", (custom_id,))
        count = cursor.fetchone()[0]
        assert count == 1

        # Verify payload is from first message (INSERT OR IGNORE keeps first)
        cursor.execute("SELECT payload_json FROM message_outbox WHERE message_id = ?", (custom_id,))
        payload = json.loads(cursor.fetchone()[0])
        assert payload["text"] == "First message"

    def test_enqueue_with_response_expected(self, message_outbox):
        """Test enqueuing interactive question that expects response"""
        message_id = message_outbox.enqueue(
            message_type="question",
            payload={"text": "How important is this project? (1-5)"},
            originating_agent="project_manager",
            context_id="project:42",
            expects_response=True,
        )

        # Verify record created with expects_response=True
        cursor = message_outbox.db.cursor()
        cursor.execute(
            "SELECT expects_response FROM message_outbox WHERE message_id = ?", (message_id,)
        )
        expects_response = cursor.fetchone()[0]
        assert expects_response == 1  # SQLite BOOLEAN stored as INTEGER

    def test_enqueue_all_message_types(self, message_outbox):
        """Test all supported message types"""
        message_types = ["notification", "approval_request", "escalation", "question"]

        for msg_type in message_types:
            message_id = message_outbox.enqueue(
                message_type=msg_type,
                payload={"text": f"Test {msg_type}"},
                originating_agent="test_agent",
            )

            assert message_id is not None
            assert message_id.startswith(f"{msg_type}:")

    def test_send_message_helper(self, message_outbox):
        """Test simple send_message helper for text-only notifications"""
        message_outbox.send_message(
            text="Simple notification", agent="test_agent", context_id="test:123"
        )

        # Verify record created
        cursor = message_outbox.db.cursor()
        cursor.execute("SELECT * FROM message_outbox WHERE message_type = 'notification'")
        row = cursor.fetchone()

        assert row is not None
        payload = json.loads(row["payload_json"])
        assert payload["text"] == "Simple notification"
        assert row["originating_agent"] == "test_agent"
        assert row["context_id"] == "test:123"


# ==============================================================================
# Consumer API Tests (Fetching and Delivery)
# ==============================================================================


class TestConsumerAPI:
    """Test the Consumer API used by Hermes to deliver messages"""

    def test_fetch_pending_messages(self, message_outbox):
        """Test fetching pending messages for delivery"""
        # Enqueue 3 messages
        for i in range(3):
            message_outbox.enqueue(
                message_type="notification",
                payload={"text": f"Message {i}"},
                originating_agent="test_agent",
            )

        # Fetch pending
        pending = message_outbox.fetch_pending(limit=10)

        assert len(pending) == 3
        assert all(msg.status == "pending" for msg in pending)

    def test_fetch_pending_limit(self, message_outbox):
        """Test fetch_pending respects limit parameter"""
        # Enqueue 5 messages
        for i in range(5):
            message_outbox.enqueue(message_type="notification", payload={"text": f"Message {i}"})

        # Fetch with limit=2
        pending = message_outbox.fetch_pending(limit=2)

        assert len(pending) == 2

    def test_fetch_pending_order(self, message_outbox):
        """Test that pending messages are fetched in creation order (FIFO)"""
        # Enqueue messages with identifiable content
        message_outbox.enqueue(
            message_type="notification", payload={"text": "First"}, message_id="msg_1"
        )

        message_outbox.enqueue(
            message_type="notification", payload={"text": "Second"}, message_id="msg_2"
        )

        message_outbox.enqueue(
            message_type="notification", payload={"text": "Third"}, message_id="msg_3"
        )

        # Fetch all
        pending = message_outbox.fetch_pending(limit=10)

        assert len(pending) == 3
        assert pending[0].message_id == "msg_1"
        assert pending[1].message_id == "msg_2"
        assert pending[2].message_id == "msg_3"

    def test_mark_delivered_no_response_expected(self, message_outbox):
        """Test marking message as delivered when no response expected"""
        message_id = message_outbox.enqueue(
            message_type="notification", payload={"text": "Test"}, expects_response=False
        )

        # Mark as delivered
        message_outbox.mark_delivered(message_id)

        # Verify status changed to 'delivered'
        cursor = message_outbox.db.cursor()
        cursor.execute(
            "SELECT status, delivered_at FROM message_outbox WHERE message_id = ?", (message_id,)
        )
        row = cursor.fetchone()

        assert row["status"] == "delivered"
        assert row["delivered_at"] is not None

    def test_mark_delivered_response_expected(self, message_outbox):
        """Test marking message as delivered when response expected (should go to awaiting_response)"""  # noqa: E501
        message_id = message_outbox.enqueue(
            message_type="question",
            payload={"text": "How important? (1-5)"},
            originating_agent="project_manager",
            context_id="project:42",
            expects_response=True,
        )

        # Mark as delivered
        message_outbox.mark_delivered(message_id)

        # Verify status changed to 'awaiting_response'
        cursor = message_outbox.db.cursor()
        cursor.execute(
            "SELECT status, delivered_at FROM message_outbox WHERE message_id = ?", (message_id,)
        )
        row = cursor.fetchone()

        assert row["status"] == "awaiting_response"
        assert row["delivered_at"] is not None

    def test_mark_failed_increments_attempts(self, message_outbox):
        """Test that marking failed increments attempts counter"""
        message_id = message_outbox.enqueue(message_type="notification", payload={"text": "Test"})

        # Mark failed
        message_outbox.mark_failed(message_id, error="Connection timeout")

        # Verify attempts incremented and error recorded
        cursor = message_outbox.db.cursor()
        cursor.execute(
            "SELECT attempts, last_error, status FROM message_outbox WHERE message_id = ?",
            (message_id,),
        )
        row = cursor.fetchone()

        assert row["attempts"] == 1
        assert row["last_error"] == "Connection timeout"
        assert row["status"] == "pending"  # Still pending, can retry

    def test_mark_failed_max_attempts(self, message_outbox):
        """Test that message marked as failed after max attempts (3)"""
        message_id = message_outbox.enqueue(message_type="notification", payload={"text": "Test"})

        # Fail 3 times
        for i in range(3):
            message_outbox.mark_failed(message_id, error=f"Attempt {i+1} failed")

        # Verify status changed to 'failed'
        cursor = message_outbox.db.cursor()
        cursor.execute(
            "SELECT attempts, status FROM message_outbox WHERE message_id = ?", (message_id,)
        )
        row = cursor.fetchone()

        assert row["attempts"] == 3
        assert row["status"] == "failed"


# ==============================================================================
# Response Routing Tests
# ==============================================================================


class TestResponseRouting:
    """Test response routing back to originating agents"""

    def test_record_response_returns_originating_agent(self, message_outbox):
        """Test that record_response returns originating agent for routing"""
        # Enqueue question from project_manager
        message_id = message_outbox.enqueue(
            message_type="question",
            payload={"text": "How important? (1-5)"},
            originating_agent="project_manager",
            context_id="project:42",
            expects_response=True,
        )

        # Mark as delivered (goes to awaiting_response)
        message_outbox.mark_delivered(message_id)

        # Record user response
        agent = message_outbox.record_response(
            context_id="project:42", response_data={"field": "importance", "value": 5}
        )

        assert agent == "project_manager"

    def test_record_response_updates_status(self, message_outbox):
        """Test that record_response updates status to delivered"""
        message_id = message_outbox.enqueue(
            message_type="question",
            payload={"text": "How urgent? (1-5)"},
            originating_agent="project_manager",
            context_id="project:42",
            expects_response=True,
        )

        message_outbox.mark_delivered(message_id)

        # Record response
        message_outbox.record_response(
            context_id="project:42", response_data={"field": "urgency", "value": 4}
        )

        # Verify status changed to 'delivered' and response stored
        cursor = message_outbox.db.cursor()
        cursor.execute(
            "SELECT status, response_json, response_received_at FROM message_outbox WHERE message_id = ?",  # noqa: E501
            (message_id,),
        )
        row = cursor.fetchone()

        assert row["status"] == "delivered"
        assert row["response_json"] is not None
        assert row["response_received_at"] is not None

        response = json.loads(row["response_json"])
        assert response["field"] == "urgency"
        assert response["value"] == 4

    def test_record_response_only_for_awaiting_response(self, message_outbox):
        """Test that record_response only works for messages in awaiting_response state"""
        # Enqueue message but don't mark as delivered
        message_outbox.enqueue(
            message_type="question",
            payload={"text": "Test"},
            originating_agent="project_manager",
            context_id="project:99",
            expects_response=True,
        )

        # Try to record response (should return None - not in awaiting_response state)
        agent = message_outbox.record_response(
            context_id="project:99", response_data={"field": "test", "value": 1}
        )

        assert agent is None

    def test_record_response_for_nonexistent_context(self, message_outbox):
        """Test that record_response returns None for nonexistent context"""
        agent = message_outbox.record_response(
            context_id="project:999", response_data={"field": "test", "value": 1}
        )

        assert agent is None


# ==============================================================================
# State Transition Tests
# ==============================================================================


class TestStateTransitions:
    """Test state machine transitions: pending → delivered/awaiting_response → delivered"""

    def test_transition_pending_to_delivered(self, message_outbox):
        """Test: pending → delivered (no response expected)"""
        message_id = message_outbox.enqueue(
            message_type="notification", payload={"text": "Test"}, expects_response=False
        )

        # Initial state
        cursor = message_outbox.db.cursor()
        cursor.execute("SELECT status FROM message_outbox WHERE message_id = ?", (message_id,))
        assert cursor.fetchone()["status"] == "pending"

        # Mark delivered
        message_outbox.mark_delivered(message_id)

        # Final state
        cursor.execute("SELECT status FROM message_outbox WHERE message_id = ?", (message_id,))
        assert cursor.fetchone()["status"] == "delivered"

    def test_transition_pending_to_awaiting_response(self, message_outbox):
        """Test: pending → awaiting_response (response expected)"""
        message_id = message_outbox.enqueue(
            message_type="question",
            payload={"text": "Test"},
            originating_agent="test_agent",
            context_id="test:1",
            expects_response=True,
        )

        # Initial state
        cursor = message_outbox.db.cursor()
        cursor.execute("SELECT status FROM message_outbox WHERE message_id = ?", (message_id,))
        assert cursor.fetchone()["status"] == "pending"

        # Mark delivered
        message_outbox.mark_delivered(message_id)

        # Intermediate state
        cursor.execute("SELECT status FROM message_outbox WHERE message_id = ?", (message_id,))
        assert cursor.fetchone()["status"] == "awaiting_response"

    def test_transition_awaiting_response_to_delivered(self, message_outbox):
        """Test: awaiting_response → delivered (user responds)"""
        message_id = message_outbox.enqueue(
            message_type="question",
            payload={"text": "Test"},
            originating_agent="test_agent",
            context_id="test:1",
            expects_response=True,
        )

        message_outbox.mark_delivered(message_id)

        # Intermediate state
        cursor = message_outbox.db.cursor()
        cursor.execute("SELECT status FROM message_outbox WHERE message_id = ?", (message_id,))
        assert cursor.fetchone()["status"] == "awaiting_response"

        # Record response
        message_outbox.record_response(context_id="test:1", response_data={"answer": "yes"})

        # Final state
        cursor.execute("SELECT status FROM message_outbox WHERE message_id = ?", (message_id,))
        assert cursor.fetchone()["status"] == "delivered"

    def test_transition_pending_to_failed(self, message_outbox):
        """Test: pending → failed (after max retries)"""
        message_id = message_outbox.enqueue(message_type="notification", payload={"text": "Test"})

        # Fail 3 times
        for i in range(3):
            message_outbox.mark_failed(message_id, error=f"Error {i+1}")

        cursor = message_outbox.db.cursor()
        cursor.execute("SELECT status FROM message_outbox WHERE message_id = ?", (message_id,))
        assert cursor.fetchone()["status"] == "failed"

    def test_transition_failed_to_pending_on_requeue(self, message_outbox):
        """Test: failed → pending (manual requeue)"""
        message_id = message_outbox.enqueue(message_type="notification", payload={"text": "Test"})

        # Fail 3 times to reach failed state
        for i in range(3):
            message_outbox.mark_failed(message_id, error=f"Error {i+1}")

        # Requeue (reset attempts and status)
        message_outbox.requeue(message_id)

        cursor = message_outbox.db.cursor()
        cursor.execute(
            "SELECT status, attempts FROM message_outbox WHERE message_id = ?", (message_id,)
        )
        row = cursor.fetchone()

        assert row["status"] == "pending"
        assert row["attempts"] == 0


# ==============================================================================
# Audit and History Tests
# ==============================================================================


class TestAuditAndHistory:
    """Test long-term history retention for audit purposes"""

    def test_delivered_messages_retained(self, message_outbox):
        """Test that delivered messages are NOT automatically deleted"""
        # Enqueue and deliver
        message_id = message_outbox.enqueue(message_type="notification", payload={"text": "Test"})

        message_outbox.mark_delivered(message_id)

        # Verify still exists in database
        cursor = message_outbox.db.cursor()
        cursor.execute("SELECT COUNT(*) FROM message_outbox WHERE message_id = ?", (message_id,))
        count = cursor.fetchone()[0]

        assert count == 1

    def test_timestamps_tracked(self, message_outbox):
        """Test that all timestamps are tracked correctly"""
        message_id = message_outbox.enqueue(message_type="notification", payload={"text": "Test"})

        cursor = message_outbox.db.cursor()
        cursor.execute("SELECT created_at FROM message_outbox WHERE message_id = ?", (message_id,))
        row = cursor.fetchone()

        # created_at should be set
        assert row["created_at"] is not None

        # Mark as delivered
        message_outbox.mark_delivered(message_id)

        cursor.execute(
            "SELECT delivered_at FROM message_outbox WHERE message_id = ?", (message_id,)
        )
        row = cursor.fetchone()

        # delivered_at should be set
        assert row["delivered_at"] is not None


# ==============================================================================
# Edge Cases and Error Handling Tests
# ==============================================================================


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_enqueue_with_empty_payload(self, message_outbox):
        """Test that enqueue requires non-empty payload"""
        with pytest.raises(ValueError, match="payload cannot be empty"):
            message_outbox.enqueue(message_type="notification", payload={})

    def test_enqueue_with_invalid_message_type(self, message_outbox):
        """Test that invalid message types are rejected"""

        with pytest.raises(ValueError, match="Invalid message_type"):
            message_outbox.enqueue(message_type="invalid_type", payload={"text": "Test"})

    def test_fetch_pending_empty_outbox(self, message_outbox):
        """Test fetching from empty outbox returns empty list"""
        pending = message_outbox.fetch_pending(limit=10)

        assert pending == []

    def test_mark_delivered_nonexistent_message(self, message_outbox):
        """Test marking nonexistent message as delivered (should not error)"""
        # Should not raise exception
        message_outbox.mark_delivered("nonexistent_id")

    def test_mark_failed_nonexistent_message(self, message_outbox):
        """Test marking nonexistent message as failed (should not error)"""
        # Should not raise exception
        message_outbox.mark_failed("nonexistent_id", error="Test error")

    def test_requeue_nonexistent_message(self, message_outbox):
        """Test requeueing nonexistent message raises ValueError"""
        with pytest.raises(ValueError, match="Message .* not found"):
            message_outbox.requeue("nonexistent_id")

    def test_requeue_non_failed_message(self, message_outbox):
        """Test that only failed messages can be requeued"""
        message_id = message_outbox.enqueue(message_type="notification", payload={"text": "Test"})

        # Try to requeue pending message (should fail)
        with pytest.raises(ValueError, match="Can only requeue failed messages"):
            message_outbox.requeue(message_id)


# ==============================================================================
# Integration Tests (will be moved to tests/integration/ later)
# ==============================================================================


class TestOutboxMessage:
    """Test OutboxMessage data class"""

    def test_outbox_message_from_row(self):
        """Test creating OutboxMessage from database row"""
        from mnemosyne.alexandria.message_outbox import OutboxMessage

        # Simulate database row
        row_dict = {
            "id": 1,
            "message_id": "test_msg_1",
            "message_type": "notification",
            "originating_agent": "test_agent",
            "context_id": "test:123",
            "payload_json": '{"text": "Hello"}',
            "status": "pending",
            "expects_response": False,
            "response_received_at": None,
            "response_json": None,
            "attempts": 0,
            "last_error": None,
            "created_at": "2026-01-01 10:00:00",
            "last_attempted_at": None,
            "delivered_at": None,
        }

        msg = OutboxMessage.from_row(row_dict)

        assert msg.message_id == "test_msg_1"
        assert msg.message_type == "notification"
        assert msg.originating_agent == "test_agent"
        assert msg.context_id == "test:123"
        assert msg.payload == {"text": "Hello"}
        assert msg.status == "pending"
        assert msg.expects_response is False
        assert msg.attempts == 0
