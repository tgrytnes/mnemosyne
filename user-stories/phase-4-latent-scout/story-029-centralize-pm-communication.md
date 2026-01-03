# Story 029: Centralize User Communication in PM Agent

**As a** user interacting with Mnemosyne via Telegram
**I want** all agent messages to come through a single, consistent conversation interface
**So that** I have a coherent experience with unified throttling, message history, and response handling

## 🎯 Architectural Role

**This story refactors communication patterns to centralize user-facing messaging in the Project Manager Agent.**

Currently, multiple agents send messages directly to the user:
- **Gatekeeper** sends approval requests (Story 014)
- **Monitor Agent** sends escalations (Story 015)
- **PM Agent** sends enrichment questions (Story 016)

This creates fragmented user experience and duplicated communication logic.

**Target Architecture**: PM Agent becomes the single "Conversation Manager" - all other agents queue work for PM to communicate.

```
┌─────────────────────────────────────────────────────┐
│           Current (Fragmented)                       │
└─────────────────────────────────────────────────────┘

Gatekeeper ──→ MessageOutbox ──→ User
Monitor    ──→ MessageOutbox ──→ User
PM Agent   ──→ MessageOutbox ──→ User

❌ Three separate communication paths
❌ Inconsistent message formats
❌ Throttling per-agent instead of global


┌─────────────────────────────────────────────────────┐
│           Target (Centralized)                       │
└─────────────────────────────────────────────────────┘

Gatekeeper ──→ WorkQueue
Monitor    ──→ WorkQueue
                   ↓
              PM Agent ──→ MessageOutbox ──→ User

✅ Single communication path
✅ Consistent messaging patterns
✅ Global throttling (5 messages/hour)
✅ Unified conversation context
```

## Acceptance Criteria

### Phase 1: Remove Gatekeeper Direct Messaging
- [ ] **Gatekeeper stops sending messages directly**
  - Remove `MessageOutbox` dependency from `SQLProjectGatekeeper`
  - Gatekeeper only makes decisions (approve/reject/needs-approval)
  - Queue approval needs for Monitor Agent to handle

- [ ] **Monitor Agent handles all approval communication**
  - Monitor polls `ProposalQueue` for status="awaiting_approval"
  - Monitor sends approval requests via MessageOutbox
  - Monitor continues to handle rejections/escalations
  - Update tests: Gatekeeper tests should NOT check MessageOutbox

### Phase 2: Monitor Queues Work for PM Agent
- [ ] **Create CommunicationQueue (SQLite)**
  - Schema: `id`, `message_type`, `payload_json`, `priority`, `status`, `created_at`
  - Message types: "approval_request", "escalation", "enrichment_question"
  - Priority: 1 (urgent) to 5 (low)

- [ ] **Monitor queues instead of sending directly**
  - Monitor → CommunicationQueue (instead of MessageOutbox)
  - Approval requests: priority 2
  - Escalations: priority 1

- [ ] **PM Agent polls CommunicationQueue**
  - New method: `_process_communication_queue()`
  - Called in `run_pm_check_cycle()` before enrichment checks
  - Sends messages via existing MessageOutbox infrastructure

### Phase 3: Unified Message Templates
- [ ] **Create message template system**
  - `MessageTemplates` class with consistent formatting
  - Templates for: approvals, rejections, escalations, questions
  - Metadata includes: `question_type`, `priority`, `project_id`, `discovery_id`

- [ ] **Update PM Agent to use templates**
  - Enrichment questions use templates
  - Approval requests use templates
  - Escalations use templates

### Phase 4: Global Throttling
- [ ] **Throttling counts ALL message types**
  - Current: Only counts PM enrichment messages
  - Target: Count approvals + escalations + enrichment
  - Limit: 5 total messages per hour (configurable)

- [ ] **Priority-based throttling**
  - Escalations (priority 1) bypass throttle (urgent)
  - Approval requests (priority 2) bypass throttle
  - Enrichment questions (priority 3) respect throttle
  - Low priority messages (priority 4-5) deferred

### Phase 5: Response Routing
- [ ] **PM Agent routes responses to correct handler**
  - Approval responses → Gatekeeper.approve()/reject()
  - Escalation responses → Monitor state update
  - Enrichment responses → PM enrichment handlers (existing)

- [ ] **Metadata-based routing (not content parsing)**
  - Use `message_type` and `question_type` metadata
  - Never parse message content for routing decisions
  - Lesson learned from Story 016 bug

## Implementation Plan

### Step 1: Remove Gatekeeper Messaging (No Breaking Changes)
```python
# BEFORE (Story 014/015)
class SQLProjectGatekeeper:
    def __init__(self, db_conn, queue, outbox, config):
        self.outbox = outbox  # ❌ Remove this

    def process_pending(self):
        if needs_approval:
            self.outbox.enqueue(...)  # ❌ Remove this

# AFTER (Story 029 Phase 1)
class SQLProjectGatekeeper:
    def __init__(self, db_conn, queue, config):
        # No outbox dependency

    def process_pending(self):
        if needs_approval:
            self.queue.update_status(discovery_id, "awaiting_approval")
            # Monitor Agent will handle communication
```

### Step 2: Monitor Handles Approvals
```python
# Monitor Agent (enhanced)
class MonitorAgent:
    def run(self):
        self._send_approval_requests()  # NEW
        self._escalate_rejections()     # EXISTING
        self._reconcile_discoveries()   # EXISTING

    def _send_approval_requests(self):
        """Send approval requests for awaiting_approval proposals."""
        proposals = self.queue.list_by_status("awaiting_approval")
        for proposal in proposals:
            message_id = f"approval_request:{proposal['discovery_id']}"
            payload = {
                "type": "approval_request",
                "discovery_id": proposal["discovery_id"],
                "confidence": proposal["confidence_score"],
                # ... project details
            }
            self.outbox.enqueue("approval_request", payload, message_id)
            self.queue.update_status(proposal["discovery_id"], "approval_sent")
```

### Step 3: Create CommunicationQueue
```python
class CommunicationQueue:
    """SQLite queue for PM Agent communication tasks."""

    def enqueue(self, message_type: str, payload: dict, priority: int = 3):
        """Queue a message for PM to send."""
        pass

    def fetch_pending(self, limit: int = 10) -> list[dict]:
        """Fetch pending messages ordered by priority."""
        pass

    def mark_sent(self, message_id: str):
        """Mark message as sent."""
        pass
```

### Step 4: PM Agent Becomes Communication Hub
```python
class ProjectManagerAgent:
    def __init__(self, db_conn, message_outbox, comm_queue, gatekeeper, ...):
        self.comm_queue = comm_queue  # NEW

    def run_pm_check_cycle(self):
        # Process communication queue FIRST (approvals/escalations)
        self._process_communication_queue()

        # Then check enrichment needs (if throttle allows)
        self._check_enrichment_needs()

    def _process_communication_queue(self):
        """Process queued messages from other agents."""
        messages = self.comm_queue.fetch_pending(limit=10)

        for msg in messages:
            if not self._check_throttle():
                break  # Respect throttle

            self._send_message(msg)
            self.comm_queue.mark_sent(msg["id"])
```

## Why This Matters

### 1. **User Experience**
**Before**: User receives messages from different "voices"
```
[10:00] Gatekeeper: "Approve project X?"
[10:05] PM Agent: "How important is project Y?"
[10:10] Monitor: "Project X was rejected, escalating..."
```
User: "Are these the same system?"

**After**: Consistent conversation
```
[10:00] PM Agent: "I found project X (confidence: 75%). Approve?"
[10:05] PM Agent: "How important is project Y?"
[10:10] PM Agent: "Project X approval needed - confidence improved to 82%"
```
User: "Nice, one coherent assistant!"

### 2. **Throttling**
**Before**: Each agent has separate limits
- Gatekeeper: sends 3 approval requests
- Monitor: sends 2 escalations
- PM: sends 5 enrichment questions
- **Total: 10 messages in 1 hour** (user annoyed)

**After**: Global limit
- PM manages all messages
- Total: 5 messages/hour maximum
- Priority ensures urgent messages go through

### 3. **Maintainability**
**Before**: Communication logic in 3 places
- Gatekeeper: approval request formatting
- Monitor: escalation formatting
- PM: enrichment question formatting

**After**: Communication logic in 1 place
- PM Agent: all message templates
- Easier to add features (typing indicators, read receipts)
- Consistent error handling

## Testing Strategy

### Unit Tests
- [ ] `test_gatekeeper_no_longer_sends_messages()` - Verify no MessageOutbox dependency
- [ ] `test_monitor_sends_approval_requests()` - Monitor handles approvals
- [ ] `test_pm_processes_communication_queue()` - PM sends queued messages
- [ ] `test_global_throttling()` - All message types counted

### Integration Tests
- [ ] `test_approval_flow_via_pm()` - End-to-end approval through PM
- [ ] `test_escalation_flow_via_pm()` - End-to-end escalation through PM
- [ ] `test_mixed_message_prioritization()` - Priority ordering works

### E2E Tests
- [ ] `test_story_029_centralized_messaging()` - Full system with real services

## Migration Path

**No Breaking Changes**: This is a refactor, not a new feature.

1. **Phase 1** (Story 029a): Gatekeeper stops messaging, Monitor takes over
   - Tests still pass (just route differently)
   - User experience unchanged

2. **Phase 2** (Story 029b): Add CommunicationQueue, PM polls it
   - Tests updated to check queue instead of outbox
   - User experience unchanged

3. **Phase 3** (Story 029c): Unified templates and global throttling
   - User experience IMPROVED (consistent messaging)

## Dependencies

- ✅ Story 014: SQL Project Gatekeeper (complete)
- ✅ Story 015: Monitor Agent (complete)
- ✅ Story 016: Project Manager Agent (complete)

## Related Stories

- **Story 027**: Message Outbox Relay (Nexus/Telegram delivery)
- **Story 028**: Scout Management Console (admin interface)

## Success Metrics

- **User Experience**: Single conversation thread (not fragmented)
- **Throttling**: Max 5 messages/hour (down from ~10)
- **Code Duplication**: Message formatting in 1 place (down from 3)
- **Test Complexity**: Easier to test (mock 1 agent instead of 3)

## Notes

**Key Insight from Story 016**: Use metadata for routing, not content parsing. The deadline question contained "importance" in its text, causing wrong routing. This story extends that lesson system-wide.

**Gatekeeper Role Clarified**: Gatekeeper makes DECISIONS (approve/reject/needs-approval) but does NOT communicate with users. Communication is Monitor Agent → PM Agent → User.
