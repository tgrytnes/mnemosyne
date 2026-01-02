# Project Manager Conversation Flow Testing

## Overview

This test suite validates the **complete conversation loop** of the Project Manager Agent by simulating realistic user interactions through mock services.

## Why These Tests Matter

The previous integration tests verified individual components worked (database writes, file sync, etc.) but **didn't test the core conversation flow**:

1. PM asks question → message goes to outbox
2. Nexus polls outbox → delivers to user
3. User responds → response routes back to PM
4. PM processes response → asks next question
5. **REPEAT** until enrichment completes

These tests fill that critical gap by simulating the entire system working together as a cohesive conversation loop.

## Mock Services

### MockUser

Simulates a user responding to PM questions with configurable behaviors:

**Behaviors:**
- `cooperative`: Always responds appropriately
- `avoidant`: Skips certain questions (e.g., urgency)
- `slow`: Delays responses (for throttling tests)

**Usage:**
```python
mock_user = MockUser(behavior="cooperative")
mock_user.set_response("importance", "5")
mock_user.set_response("urgency", "4")
mock_user.set_response("deadline", "2026-03-01")
```

### MockNexus

Simulates Nexus/Telegram bot polling the message outbox and delivering messages:

**Responsibilities:**
1. Poll `message_outbox.dequeue()` for new messages
2. Deliver messages to `MockUser`
3. Route user responses back to PM via response handlers
4. Track message delivery history

**Usage:**
```python
nexus = MockNexus(message_outbox, project_manager, mock_user)
messages_processed = nexus.poll_and_deliver()
last_message = nexus.get_last_message()
```

### ConversationSimulator

Orchestrates complete conversation flows by running PM cycles and message delivery in a loop:

**Responsibilities:**
1. Run `project_manager.run_pm_check_cycle()`
2. Poll outbox via `mock_nexus.poll_and_deliver()`
3. Check if enrichment completed
4. Repeat until complete or max iterations reached

**Usage:**
```python
sim = ConversationSimulator(project_manager, mock_nexus, max_iterations=10)
stats = sim.run_until_complete(project_id)

print(stats)
# {
#     "turns": 4,
#     "messages_sent": 3,
#     "completed": True
# }
```

## Test Scenarios

### 1. Complete Enrichment Conversation
**File:** `test_complete_enrichment_conversation()`

Tests the full happy path:
1. PM asks importance → user responds "5"
2. PM asks urgency → user responds "4"
3. PM asks deadline → user responds "2026-03-01"
4. All data stored correctly
5. Project marked `enriched=TRUE`

**Validates:** The entire system works end-to-end

### 2. High Priority Projects First
**File:** `test_high_priority_project_enriched_first()`

Tests prioritization logic:
- Creates low cluster count project (priority 1)
- Creates high cluster count project (priority 5)
- Verifies high cluster project asked first

**Validates:** Enrichment queue prioritization

### 3. Avoidant User Behavior
**File:** `test_avoidant_user_only_answers_importance()`

Tests partial enrichment:
- User answers importance question
- User ignores urgency question
- PM keeps asking urgency (doesn't move to deadline)
- Project remains partially enriched

**Validates:** Event-driven flow handles non-responsive users

### 4. Multiple Projects Sequential
**File:** `test_multiple_projects_enriched_sequentially()`

Tests batch processing:
- Creates 3 projects with different priorities
- Enriches each one fully before moving to next
- All eventually complete

**Validates:** Queue processing and multi-project handling

### 5. Natural Language Deadline Parsing
**File:** `test_natural_language_deadline_parsing()`

Tests deadline parsing flexibility:
- User responds with "in 2 weeks"
- PM parses to actual date (~14 days from now)
- Deadline stored correctly in database

**Validates:** `_parse_deadline()` natural language handling

### 6. Throttling Prevention
**File:** `test_throttling_prevents_spam()`

Tests message throttling:
- Creates 10 projects (more than limit)
- PM only sends 5 messages (throttle limit)
- Additional requests blocked

**Validates:** Throttling prevents spam

### 7. Pressure Score Calculation
**File:** `test_pressure_score_updates_after_enrichment()`

Tests pressure score computation:
- Project starts with NULL pressure score
- After enrichment, pressure calculated
- Formula: `(work/time) × (importance × urgency)`

**Validates:** Pressure score computation and storage

## Running Tests

### Prerequisites

1. **PostgreSQL must be running:**
   ```bash
   # Check if PostgreSQL is running
   pg_isready

   # Start PostgreSQL if needed
   sudo systemctl start postgresql
   ```

2. **Test database must exist:**
   ```bash
   # Database created automatically by pytest fixtures
   # See conftest.py for setup
   ```

### Run All Conversation Flow Tests

```bash
pytest tests/integration/test_project_manager_conversation_flow.py -v
```

### Run Specific Test

```bash
pytest tests/integration/test_project_manager_conversation_flow.py::test_complete_enrichment_conversation -v
```

### Run with Coverage

```bash
pytest tests/integration/test_project_manager_conversation_flow.py --cov=src/mnemosyne/aletheia/agents
```

## Test Output Example

```
test_complete_enrichment_conversation PASSED
  - Turns: 4
  - Messages sent: 3
  - Completed: True
  - Final state: importance=5, urgency=4, deadline=2026-03-01
```

## Architecture Diagram

```
┌─────────────────────────────────────────────────────┐
│                 Conversation Flow                    │
└─────────────────────────────────────────────────────┘

┌──────────────────┐         ┌──────────────────┐
│  PM Agent        │         │  MockNexus       │
│                  │         │                  │
│ run_pm_check_    │────1───>│ poll_and_        │
│   cycle()        │         │   deliver()      │
│                  │         │                  │
│ Sends question   │         │ Dequeues msg     │
│ to outbox        │         │                  │
└──────────────────┘         └──────────────────┘
         ^                            │
         │                            │
         │                            2
         │                            │
         │                            v
         │                   ┌──────────────────┐
         │                   │  MockUser        │
         │                   │                  │
         │                   │ respond_to_      │
         │                   │   question()     │
         │                   │                  │
         │                   │ Returns answer   │
         │                   └──────────────────┘
         │                            │
         │                            │
         │                            3
         │                            │
         │                            v
         │                   ┌──────────────────┐
         │                   │  Response        │
         │                   │  Handlers        │
         │                   │                  │
         └───────────────────│ handle_          │
                        4    │   importance_    │
                             │   response()     │
                             └──────────────────┘

Flow:
1. PM sends question to outbox
2. Nexus delivers to user, gets response
3. Response routed to appropriate handler
4. Handler processes, continues enrichment
5. REPEAT until enrichment complete
```

## Key Differences from Previous Tests

| Previous Integration Tests | New Conversation Flow Tests |
|---------------------------|----------------------------|
| Manually call `handle_importance_response()` | PM asks question naturally via check cycle |
| Manually call `handle_urgency_response()` | MockNexus routes responses automatically |
| Step-by-step verification | Complete conversation simulation |
| Tests individual components | Tests entire system integration |
| No user simulation | Realistic user behaviors (cooperative, avoidant) |
| No message delivery | Full outbox → delivery → response loop |

## Benefits

1. **Realistic Testing**: Simulates actual user conversations
2. **Complete Coverage**: Tests entire system working together
3. **Behavior Variety**: Different user types (cooperative, avoidant)
4. **Automatic Flow**: Tests event-driven enrichment naturally
5. **Easy Debugging**: Conversation statistics and message history
6. **Maintainable**: Mock services reusable across scenarios

## Future Enhancements

Possible additions:
- **MockLinearSync**: Simulate Linear issue creation/updates
- **MockObsidianSync**: Simulate file system changes triggering sync
- **Concurrent Conversations**: Multiple projects enriching simultaneously
- **Error Scenarios**: Network failures, database errors during conversation
- **Performance Testing**: Measure conversation throughput
- **Replay Testing**: Record and replay real user conversations
