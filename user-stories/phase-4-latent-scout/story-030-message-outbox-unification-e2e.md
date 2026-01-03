# Story 030: Message Outbox Unification + E2E Testing

**As a** developer
**I want** a unified MessageOutbox implementation used by all agents and Hermes
**So that** the full conversation flow works E2E and can be properly tested

## Problem Statement

Currently there are **two incompatible MessageOutbox implementations**:

1. **`alexandria/message_outbox.py`** - Used by PM Agent (Story 016)
   - API: `enqueue(message_type, payload, originating_agent, context_id, expects_response)`
   - Schema: Has `attempts`, `last_error`, `response_json` fields

2. **`hermes/outbox_store.py`** - Used by Hermes (Story 012)
   - API: `enqueue(message_type, payload_json, ...)`
   - Schema: Has `chat_id`, `telegram_message_id` fields

**Result**: PM Agent cannot communicate with Hermes! They write/read from incompatible outboxes.

## Acceptance Criteria

### Unification
- [ ] Single MessageOutbox implementation in `alexandria/message_outbox.py`
- [ ] Schema supports both agent needs (response routing) AND Hermes needs (Telegram mapping)
- [ ] Unified API that works for both producers (agents) and consumers (Hermes)
- [ ] PM Agent uses unified MessageOutbox
- [ ] Hermes uses unified MessageOutbox
- [ ] Migration script for any existing data (if needed)

### E2E Testing
- [ ] E2E test: PM Agent → MessageOutbox → Hermes → Mock Telegram → Response routing back
- [ ] Test complete enrichment conversation flow (importance → urgency → deadline)
- [ ] Test multiple projects enriched sequentially
- [ ] Test throttling (max messages per hour)
- [ ] Test response parsing and routing
- [ ] Test Obsidian sync after enrichment complete
- [ ] All E2E tests use REAL components (no mocks except Telegram API)

## Technical Design

### Unified Schema

```sql
CREATE TABLE message_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Message identification
    message_id TEXT NOT NULL UNIQUE,
    message_type TEXT NOT NULL,

    -- Agent routing (for responses)
    originating_agent TEXT,
    context_id TEXT,
    expects_response INTEGER DEFAULT 0,

    -- Payload
    payload_json TEXT NOT NULL,

    -- Telegram mapping (for Hermes)
    chat_id TEXT,
    telegram_message_id INTEGER,

    -- Response handling
    response_json TEXT,
    response_received_at TIMESTAMP,

    -- Delivery tracking
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_attempted_at TIMESTAMP,
    delivered_at TIMESTAMP,

    -- Constraints
    CHECK (message_type IN ('notification', 'approval_request', 'escalation', 'question')),
    CHECK (status IN ('pending', 'delivered', 'failed', 'awaiting_response'))
);
```

### Unified API

```python
class MessageOutbox:
    # Producer API (agents)
    def enqueue(
        message_type: str,
        payload: dict,
        originating_agent: str | None = None,
        context_id: str | None = None,
        expects_response: bool = False
    ) -> str:
        """Enqueue message for delivery"""

    # Consumer API (Hermes)
    def fetch_pending(limit: int = 50) -> list[OutboxMessage]:
        """Fetch pending messages for delivery"""

    def mark_delivered(
        message_id: str,
        chat_id: str,
        telegram_message_id: int
    ) -> None:
        """Mark message as delivered with Telegram info"""

    def mark_failed(message_id: str, error: str) -> None:
        """Mark delivery failure"""

    # Response routing (Hermes → Agent)
    def record_response(
        chat_id: str,
        telegram_message_id: int,
        response_data: dict
    ) -> str | None:
        """Record response, return originating_agent"""
```

### E2E Test Architecture

```python
class MockTelegramClient:
    """Simulates Telegram API for testing"""
    def send_message(chat_id, text, buttons=None):
        # Record sent message
        # Return fake telegram_message_id

    def simulate_user_reply(telegram_message_id, text):
        # Trigger webhook/polling handler
        # Routes back through Hermes → MessageOutbox

def test_complete_pm_enrichment_e2e():
    """
    E2E: Complete conversation flow with real components

    Components:
    - REAL PM Agent
    - REAL MessageOutbox (unified)
    - REAL Hermes TelegramOutboxConsumer
    - REAL Hermes TelegramReplyRouter
    - MOCK TelegramClient (simulates API)
    - REAL PostgreSQL
    - REAL Obsidian files
    """
    # 1. Insert unenriched project
    # 2. PM runs check cycle → enqueues question
    # 3. Hermes polls outbox → delivers to MockTelegram
    # 4. MockTelegram simulates user response
    # 5. Response routes back to PM
    # 6. PM processes → enqueues next question
    # 7. Repeat until enrichment complete
    # 8. Assert: project enriched, synced to Obsidian
```

## Migration Strategy

1. **Create unified MessageOutbox** with combined schema
2. **Update PM Agent** to use unified version (already done in Story 016)
3. **Update Hermes** to use unified MessageOutbox instead of OutboxStore
4. **Add E2E tests** with real components
5. **Remove `hermes/outbox_store.py`** (deprecated)

## Dependencies
- Story 012 (Hermes) - merged ✅
- Story 016 (PM Agent) - in PR #22
- Story 027 (MessageOutbox) - implemented ✅

## Affected Components
- **Alexandria**: Unified MessageOutbox
- **Hermes**: Update to use alexandria MessageOutbox
- **PM Agent**: Already updated (Story 016)
- **Tests**: New E2E test suite

## Priority
**Critical** - Blocks PM Agent + Hermes integration

## Estimate
**5 points** (3-4 days)
- Unification: 2 points
- Hermes migration: 2 points
- E2E tests: 1 point

## Test Plan

### Unit Tests
- [ ] Unified MessageOutbox works for enqueue/fetch/mark operations
- [ ] Response routing finds correct originating_agent
- [ ] Telegram mapping stored correctly

### Integration Tests
- [ ] PM Agent enqueues messages
- [ ] Hermes consumes messages
- [ ] Response routing works

### E2E Tests
- [ ] Complete conversation flow (3+ question cycles)
- [ ] Multiple projects
- [ ] Error handling and retries
- [ ] Obsidian sync integration

## Success Metrics
- Single MessageOutbox implementation
- PM Agent → Hermes conversation works E2E
- All E2E tests passing in CI
- No mock MessageOutbox implementations in codebase
