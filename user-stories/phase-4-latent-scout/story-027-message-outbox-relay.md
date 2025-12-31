# Story 027: Message Outbox Relay (Nexus Middle-Man)

**As a** system
**I want** a local message outbox between agents and Nexus
**So that** agents stay transport-agnostic and user messaging is reliable

## Acceptance Criteria
- [ ] Agents write messages to a local outbox (SQLite)
- [ ] Nexus/Hermes reads from the outbox and delivers to Telegram
- [ ] Messages are idempotent (dedup key per message)
- [ ] Delivery status tracked (pending, delivered, failed)
- [ ] Failures are retryable with backoff
- [ ] Supports message types: notification, approval_request, escalation
- [ ] Outbox keeps long-term history for audit
- [ ] CLI command to inspect or requeue messages

## Technical Notes

### Outbox Schema (SQLite)

```sql
CREATE TABLE message_outbox (
    id INTEGER PRIMARY KEY,
    message_id TEXT NOT NULL UNIQUE,
    message_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_attempted_at TIMESTAMP
);

CREATE INDEX idx_outbox_status ON message_outbox(status);
CREATE INDEX idx_outbox_type ON message_outbox(message_type);
```

### Producer API (used by agents)

```python
def enqueue_message(message_type: str, payload: dict, message_id: str) -> None:
    # Insert or ignore if message_id already exists
    pass
```

### Consumer API (used by Nexus/Hermes)

```python
def fetch_pending(limit: int = 50) -> list[OutboxMessage]:
    # Pull pending messages
    pass


def mark_delivered(message_id: str) -> None:
    pass


def mark_failed(message_id: str, error: str) -> None:
    pass
```

### Message Types

- `notification`: informational update
- `approval_request`: requires user confirmation
- `escalation`: gatekeeper rejection or urgent issue

## Dependencies
- Hermes/Nexus delivery layer (Story 012)
- SQLite persistence

## Affected Components
- **Argus**: emits messages to outbox
- **Hermes**: consumes outbox and delivers to user
- **Alexandria**: outbox storage

## Priority
**High** - Reduces coupling and clarifies messaging flow

## Estimate
5 story points (3-5 days)

## Linear Labels
`phase-4`, `messaging`, `outbox`, `hermes`, `argus`

## Related Stories
- Story 010: Autonomous Pattern Detection
- Story 014: SQL Project Gatekeeper
- Story 015: Monitor Agent
- Story 012: Proactive Insight Notifications
