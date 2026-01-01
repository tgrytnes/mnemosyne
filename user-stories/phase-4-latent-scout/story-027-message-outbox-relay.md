# Story 027: Message Outbox Relay (Nexus Middle-Man)

**As a** system
**I want** a local message outbox between agents and Nexus
**So that** agents stay transport-agnostic and user messaging is reliable

## Acceptance Criteria

### Core Functionality
- [ ] Agents write messages to a local outbox (SQLite database)
- [ ] Nexus/Hermes polls outbox and delivers to Telegram (background job every 30 seconds)
- [ ] Messages are idempotent (dedup by `message_id` - INSERT OR IGNORE)
- [ ] Delivery status tracked (pending, delivered, failed, awaiting_response)
- [ ] Failures are retryable with exponential backoff (max 3 attempts)
- [ ] After 3 failed attempts, message marked as `failed` (no more retries)

### Message Types & Routing
- [ ] Supports message types: `notification`, `approval_request`, `escalation`, `question`
- [ ] Discovery-related payloads include `discovery_id` and `discovery_job_key` in context
- [ ] Project-related payloads include `project_id` in `context_id` for response routing (e.g., `project:42`)
- [ ] Message IDs for discovery-related events can be derived from `discovery_id` (for idempotency)
- [ ] Supports interactive messages (`expects_response=True`) that transition to `awaiting_response` on delivery
- [ ] Routes Telegram responses back to originating agent using `record_response()` → returns `originating_agent`
- [ ] Maintains conversation context via `context_id` field (e.g., `project:42`, `discovery:disco_001`)

### State Management
- [ ] State transitions: `pending` → `delivered` (if no response expected)
- [ ] State transitions: `pending` → `awaiting_response` (if response expected)
- [ ] State transitions: `awaiting_response` → `delivered` (when user responds)
- [ ] State transitions: `pending` → `failed` (after 3 failed attempts)
- [ ] State transitions: `failed` → `pending` (on manual requeue)
- [ ] Tracks delivery timestamps: `created_at`, `last_attempted_at`, `delivered_at`, `response_received_at`
- [ ] Stores user response in `response_json` field when received

### Audit & Management
- [ ] Outbox keeps long-term history for audit (no automatic deletion)
- [ ] CLI command: `/mcp outbox status` - Show counts by status
- [ ] CLI command: `/mcp outbox inspect <message_id>` - View message details
- [ ] CLI command: `/mcp outbox requeue <message_id>` - Retry failed message
- [ ] CLI command: `/mcp outbox clear` - Clear old delivered messages (optional)

## Technical Notes

### Outbox Schema (SQLite)

```sql
CREATE TABLE message_outbox (
    id INTEGER PRIMARY KEY,
    message_id TEXT NOT NULL UNIQUE,
    message_type TEXT NOT NULL,  -- notification, approval_request, escalation, question
    originating_agent TEXT,      -- 'project_manager', 'monitor', 'gatekeeper', etc.
    context_id TEXT,             -- project_id, discovery_id, etc. for routing responses
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending, delivered, failed, awaiting_response
    expects_response BOOLEAN DEFAULT FALSE,
    response_received_at TIMESTAMP,
    response_json TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_attempted_at TIMESTAMP,
    delivered_at TIMESTAMP
);

CREATE INDEX idx_outbox_status ON message_outbox(status);
CREATE INDEX idx_outbox_type ON message_outbox(message_type);
CREATE INDEX idx_outbox_agent ON message_outbox(originating_agent);
CREATE INDEX idx_outbox_context ON message_outbox(context_id);
```

### Producer API (used by agents)

```python
class MessageOutbox:
    """
    Queue for agent → user communication
    """
    def enqueue(
        self,
        message_type: str,
        payload: dict,
        message_id: str = None,
        originating_agent: str = None,
        context_id: str = None,
        expects_response: bool = False
    ) -> str:
        """
        Enqueue a message for delivery to user

        Args:
            message_type: 'notification', 'approval_request', 'escalation', 'question'
            payload: Message content and metadata
            message_id: Optional ID for idempotency (auto-generated if None)
            originating_agent: 'project_manager', 'monitor', 'gatekeeper', etc.
            context_id: project_id, discovery_id, etc. for routing responses
            expects_response: True if this is an interactive question

        Returns:
            message_id
        """
        if not message_id:
            message_id = f"{message_type}:{context_id}:{uuid4()}"

        cursor = self.db.cursor()

        cursor.execute("""
            INSERT OR IGNORE INTO message_outbox (
                message_id,
                message_type,
                originating_agent,
                context_id,
                payload_json,
                expects_response
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            message_id,
            message_type,
            originating_agent,
            context_id,
            json.dumps(payload),
            expects_response
        ))

        self.db.commit()
        return message_id

    def send_message(self, text: str, agent: str = None, context_id: str = None):
        """
        Simple helper for text-only notifications
        """
        self.enqueue(
            message_type='notification',
            payload={'text': text},
            originating_agent=agent,
            context_id=context_id
        )
```

**Idempotency Note**: for discovery/proposal messages, set `message_id` to
`{message_type}:{discovery_id}` to prevent duplicates across retries.

### Consumer API (used by Nexus/Hermes)

```python
class MessageOutbox:
    # ... (continued from Producer API)

    def fetch_pending(self, limit: int = 50) -> List[OutboxMessage]:
        """
        Pull pending messages for delivery
        """
        cursor = self.db.cursor()

        cursor.execute("""
            SELECT * FROM message_outbox
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT ?
        """, (limit,))

        return [OutboxMessage.from_row(row) for row in cursor.fetchall()]

    def mark_delivered(self, message_id: str) -> None:
        """
        Mark message as successfully delivered
        """
        cursor = self.db.cursor()

        cursor.execute("""
            UPDATE message_outbox
            SET status = CASE
                    WHEN expects_response THEN 'awaiting_response'
                    ELSE 'delivered'
                END,
                delivered_at = ?
            WHERE message_id = ?
        """, (datetime.now(), message_id))

        self.db.commit()

    def mark_failed(self, message_id: str, error: str) -> None:
        """
        Mark message delivery as failed
        """
        cursor = self.db.cursor()

        cursor.execute("""
            UPDATE message_outbox
            SET attempts = attempts + 1,
                last_error = ?,
                last_attempted_at = ?,
                status = CASE
                    WHEN attempts >= 3 THEN 'failed'
                    ELSE 'pending'
                END
            WHERE message_id = ?
        """, (error, datetime.now(), message_id))

        self.db.commit()

    def record_response(self, context_id: str, response_data: dict) -> str:
        """
        Record user response to an interactive message
        Routes response back to originating agent

        Args:
            context_id: project_id, discovery_id, etc.
            response_data: User's response (parsed from Telegram command)

        Returns:
            originating_agent (for routing)
        """
        cursor = self.db.cursor()

        cursor.execute("""
            UPDATE message_outbox
            SET status = 'delivered',
                response_received_at = ?,
                response_json = ?
            WHERE context_id = ?
            AND expects_response = TRUE
            AND status = 'awaiting_response'
            RETURNING originating_agent
        """, (datetime.now(), json.dumps(response_data), context_id))

        row = cursor.fetchone()
        self.db.commit()

        return row[0] if row else None
```

### Message Types

- `notification`: informational update (no response expected)
- `approval_request`: requires user confirmation (expects yes/no response)
- `escalation`: gatekeeper rejection or urgent issue (may expect response)
- `question`: interactive question from agent (expects structured response)

### Response Routing Pattern

When a user responds to a question via Telegram:

1. **Telegram command received**: `/importance 42 5`
2. **Hermes extracts context**: `project_id=42, field=importance, value=5`
3. **Outbox records response**: `record_response(context_id='project:42', response_data={'field': 'importance', 'value': 5})`
4. **Outbox returns agent**: `'project_manager'`
5. **Hermes routes to agent**: Project Manager processes the response
6. **Agent updates state**: Updates SQL, syncs to Obsidian, may ask next question

```python
# In Hermes Telegram bot
@bot.command("importance")
def cmd_importance(message, project_id: int, value: int):
    """
    User responds to Project Manager's importance question
    """
    # Record response in outbox
    agent = outbox.record_response(
        context_id=f'project:{project_id}',
        response_data={'field': 'importance', 'value': value}
    )

    # Route to agent (if agent is known)
    if agent == 'project_manager':
        project_manager.handle_importance_response(project_id, value)
    elif agent == 'monitor':
        monitor_agent.handle_response(project_id, value)

    bot.send_message(message.chat.id, f"✅ Importance set to {value}")
```

### Outbox State Transitions

States: `pending`, `delivered`, `failed`, `awaiting_response`

Transitions:
- `pending` → `delivered` on successful delivery (if expects_response=False)
- `pending` → `awaiting_response` on successful delivery (if expects_response=True)
- `awaiting_response` → `delivered` when user responds
- `pending` → `failed` after max retry attempts (3 attempts)
- `failed` → `pending` on manual requeue
- `pending` → `pending` on retry (attempts increment, `last_attempted_at` updated)

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
