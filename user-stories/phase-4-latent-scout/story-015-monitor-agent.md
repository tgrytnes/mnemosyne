# Story 015: Monitor Agent (Discovery → Proposal Queue)

**As a** user
**I want** an agent that monitors the gap between discoveries and SQL projects
**So that** high-value discoveries don't get lost when the gatekeeper denies them

## Acceptance Criteria

### Entry Point and Scheduling
- [ ] Provide a CLI entrypoint `python -m mnemosyne.cli.monitor run` that performs a single reconciliation pass and exits 0 on success.
- [ ] Daily scheduling is achieved via external scheduler (cron/systemd) invoking the same CLI; document a sample daily command and required env vars.

### Discovery Inputs and Identity
- [ ] Query Weaviate `Discoveries` with filters `patternType=project_candidate` and `confidenceScore >= MONITOR_CONFIDENCE_THRESHOLD`, limited by `MONITOR_SCAN_LIMIT`.
- [ ] Each discovery record includes `discoveryJobKey`, `candidateKey`, and `discoveryId`.
- [ ] `discoveryId` is exactly `{discovery_job_key}:{candidate_key}`.
- [ ] `candidateKey` is a slugified label (lowercase, alnum, `_`, `-`); if no label is available, use a deterministic hash derived from sorted `clusterIds`.
- [ ] Proposal payload includes `discovery_id`, `discovery_job_key`, `candidate_key`, `cluster_ids`, `confidence_score`, `detected_at`.

### Proposal Queue and State (SQLite)
- [ ] Proposal queue persists to SQLite table `proposal_queue` with unique `discovery_id` (idempotent inserts/updates).
- [ ] Monitor state persists to SQLite table `monitor_state` with fields: `discovery_id`, `asked_at`, `ask_count`, `rejected_at`, `rejected_confidence`, `snoozed_until`, `archived_at`.
- [ ] Re-ask policy is enforced using `cooldown_days`, `max_asks`, and `confidence_delta` with defaults 14, 3, 0.15.

### Gatekeeper and Escalation
- [ ] For each eligible discovery not in SQL projects, a proposal is created/updated in the queue with status `pending`.
- [ ] Rejected proposals (`status=rejected`) are escalated once to the Message Outbox with deterministic `message_id` `proposal_escalation:{discovery_id}`.
- [ ] Escalation writes to the Message Outbox only (no direct Telegram send path).

### Logging, Resilience, Performance
- [ ] Logs include counts for scanned discoveries, proposals queued, skipped reasons (already project, cooldown, snooze, max_asks), and escalations emitted.
- [ ] Agent does not crash on empty discovery sets or missing optional fields.
- [ ] Performance: reconcile 100 discoveries in <5 minutes on a dev machine (can be a separate `@pytest.mark.performance` check).

### Configuration
- [ ] Monitor config via env vars: `MONITOR_CONFIDENCE_THRESHOLD`, `MONITOR_SCAN_LIMIT`, `MONITOR_COOLDOWN_DAYS`, `MONITOR_MAX_ASKS`, `MONITOR_CONFIDENCE_DELTA`, `MONITOR_QUEUE_DB_PATH`, `MONITOR_STATE_DB_PATH`, `MONITOR_OUTBOX_DB_PATH`.
- [ ] Weaviate connection uses `WEAVIATE_HTTP_HOST`, `WEAVIATE_HTTP_PORT`, `WEAVIATE_GRPC_PORT`.
- [ ] Postgres connection uses `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`.

### Tests
- [ ] Unit tests cover re-ask policy, idempotency, and rejection escalation behavior.
- [ ] Integration tests use real Weaviate + SQLite + Postgres (no mocks).
- [ ] E2E test covers discovery -> proposal -> rejection -> escalation loop with real services.

## Scope Notes
- Scheduler integration inside the app is out of scope for this story; external scheduling via CLI is required.

## Critical Architectural Role

**The Monitor Agent bridges the gap between fuzzy discovery and hard commitment.**

This agent is inspired by project_crystal's Monitor concept:
> **Monitor**: Watch SQL projects for stalls and missing data.

But extended to also watch for **reverse stalls** - discoveries that should be projects but aren't.

**Why this matters**: The Latent Scout finds patterns, the Gatekeeper approves them, but what if:
1. Gatekeeper sets threshold too high and misses good projects?
2. User ignores approval requests?
3. Discovery confidence increases over time (more notes added)?

The Monitor catches these cases and gives the user a second chance.

## Technical Notes

### Discovery Identity (Required)
- `discovery_job_key`: stable identifier for the radar/scout job (e.g., `private_projects`)
- `candidate_key`: stable slug derived from the discovery label (e.g., `house_painting`)
- `discovery_id`: `{discovery_job_key}:{candidate_key}` (used for dedup + project linking)

Examples:
- `private_projects:house_painting`
- `private_projects:renovate_kitchen`
- `professional_projects:deploy_pipeline`

### Monitor Agent Class

```python
class MonitorAgent:
    """
    Reconciles Discovery Vector DB with The Ananke (SQL)
    Based on project_crystal Monitor concept
    """
    def __init__(self, weaviate_client, db_conn, outbox):
        self.weaviate = weaviate_client
        self.db = db_conn
        self.outbox = outbox  # Message Outbox (Story 027)
        self.state_db = self._init_state_db()

    def run_discovery_reconciliation(self):
        """
        Daily job: Check for orphaned discoveries
        """
        # 1. Get all high-confidence project discoveries
        discoveries = self._get_high_confidence_discoveries(threshold=0.70)

        # 2. Check which ones exist in SQL
        orphaned = []
        for discovery in discoveries:
            if not self._exists_in_sql(discovery):
                orphaned.append(discovery)

        # 3. Filter out already-asked discoveries
        new_orphans = self._filter_already_asked(orphaned)

        # 4. Escalate to outbox for user review
        for discovery in new_orphans:
            self._forward_discovery_request(discovery)

        # 5. Log results
        self._log_reconciliation_run(
            total_discoveries=len(discoveries),
            orphaned=len(orphaned),
            new_orphans=len(new_orphans)
        )

    def _get_high_confidence_discoveries(self, threshold: float = 0.70) -> List[DiscoveryRecord]:
        """
        Query Discovery Vector DB for project candidates
        """
        result = self.weaviate.query(
            collection="Discoveries",
            where={
                "path": ["patternType"],
                "operator": "Equal",
                "valueText": "project_candidate"
            },
            filter={
                "path": ["confidenceScore"],
                "operator": "GreaterThan",
                "valueNumber": threshold
            },
            limit=100
        )

        return [DiscoveryRecord.from_weaviate(r) for r in result]

    def _exists_in_sql(self, discovery: DiscoveryRecord) -> bool:
        """
        Check if discovery has been written to SQL
        """
        cursor = self.db.cursor()

        cursor.execute("""
            SELECT id FROM projects
            WHERE discovery_id = %s
        """, (discovery.discovery_id,))

        return cursor.fetchone() is not None

    def _filter_already_asked(self, discoveries: List[DiscoveryRecord]) -> List[DiscoveryRecord]:
        """
        Don't re-ask about discoveries user already rejected/snoozed
        """
        new_orphans = []

        for discovery in discoveries:
            state = self._get_discovery_state(discovery.id)

            # Never asked before
            if state is None:
                new_orphans.append(discovery)
                continue

            # User snoozed: check if snooze expired
            if state.snoozed_until and state.snoozed_until < datetime.now():
                new_orphans.append(discovery)
                continue

            # User rejected: don't ask again (unless confidence increased significantly)
            if state.rejected_at:
                confidence_increased = discovery.confidence_score > (state.rejected_confidence + 0.15)
                if confidence_increased:
                    new_orphans.append(discovery)
                continue

        return new_orphans

    def _forward_discovery_request(self, discovery: DiscoveryRecord):
        """
        Queue escalation message for user reconsideration
        """
        message = f"""
🔍 **Monitor Agent: Discovery Needs Attention**

**Title**: {discovery.title}
**Description**: {discovery.description}

**Why I'm asking**:
• Confidence: {discovery.confidence_score:.0%} (high!)
• Detected: {format_time_ago(discovery.detected_at)}
• Status: Not in SQL project tracker

**This discovery was not added to The Ananke. Would you like to reconsider?**

Actions:
`/monitor_approve {discovery.discovery_id}` - Add to projects
`/monitor_reject {discovery.discovery_id}` - Not a project
`/monitor_snooze {discovery.discovery_id} 7d` - Ask again in 7 days
`/monitor_view {discovery.discovery_id}` - See full details
"""

        self.outbox.enqueue(message)

        # Mark as asked
        self._record_ask(discovery.discovery_id)

    def _get_discovery_state(self, discovery_id: str):
        """
        Get reconciliation state from SQLite
        """
        cursor = self.state_db.cursor()

        cursor.execute("""
            SELECT * FROM monitor_state
            WHERE discovery_id = ?
        """, (discovery_id,))

        row = cursor.fetchone()
        if row:
            return MonitorState.from_row(row)
        return None

    def _record_ask(self, discovery_id: str):
        """
        Log that we asked user about this discovery
        """
        cursor = self.state_db.cursor()

        cursor.execute("""
            INSERT INTO monitor_state (discovery_id, asked_at)
            VALUES (?, ?)
            ON CONFLICT(discovery_id) DO UPDATE
            SET asked_at = ?, ask_count = ask_count + 1
        """, (discovery_id, datetime.now(), datetime.now()))

        self.state_db.commit()

    def _init_state_db(self):
        """
        SQLite database for Monitor agent state
        """
        conn = sqlite3.connect("/data/monitor_state.db")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS monitor_state (
                discovery_id TEXT PRIMARY KEY,
                asked_at TIMESTAMP,
                ask_count INTEGER DEFAULT 1,
                rejected_at TIMESTAMP,
                rejected_confidence FLOAT,
                snoozed_until TIMESTAMP
            )
        """)

        return conn
```

### Proposal Queue (SQLite)

```sql
CREATE TABLE IF NOT EXISTS proposal_queue (
    id INTEGER PRIMARY KEY,
    proposal_id TEXT NOT NULL UNIQUE,
    discovery_id TEXT NOT NULL UNIQUE,
    discovery_job_key TEXT NOT NULL,
    candidate_key TEXT NOT NULL,
    proposal_hash TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'pending', -- pending, approved, rejected, escalated
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE INDEX idx_proposal_status ON proposal_queue(status);
```

### Proposal State Transitions

States: `pending`, `approved`, `rejected`, `escalated`, `archived`

Transitions:
- `pending` → `approved` when SQL Gatekeeper approves and writes to SQL
- `pending` → `rejected` when SQL Gatekeeper rejects
- `rejected` → `escalated` when Monitor escalates to Message Outbox
- `escalated` → `pending` only after explicit user reconsideration
- `rejected`/`escalated` → `archived` when max asks reached or cooldown exceeds policy
- `approved` → `archived` after SQL write confirmed (terminal)

### Message Outbox Payload (Escalation)

```python
outbox.enqueue(
    {
        "type": "proposal_escalation",
        "proposal_id": proposal.id,
        "discovery_id": discovery.discovery_id,
        "discovery_job_key": discovery.discovery_job_key,
        "candidate_key": discovery.candidate_key,
        "title": discovery.title,
        "confidence": discovery.confidence_score,
        "reason": gatekeeper_reason,
        "detected_at": discovery.detected_at,
    }
)
```

### Re-Ask Policy (Explicit)

- Cooldown: default 14 days after a reject/snooze
- Max asks: 3 total per `discovery_id`
- Re-ask only if confidence increased by >= 0.15 since last rejection
- If max asks reached, mark as `archived` in monitor state

### Scheduled Job Integration

```python
from apscheduler.schedulers.background import BackgroundScheduler

# Schedule Monitor agent to run daily at 3 AM
scheduler = BackgroundScheduler()

def run_monitor_agent():
    """
    Daily reconciliation job
    """
    log_info("Monitor Agent: Starting discovery reconciliation")

    try:
        monitor_agent.run_discovery_reconciliation()
        log_info("Monitor Agent: Reconciliation complete")
    except Exception as e:
        log_error(f"Monitor Agent failed: {e}")
        outbox.enqueue(f"Monitor Agent error: {e}")

scheduler.add_job(
    run_monitor_agent,
    'cron',
    hour=3,  # 3 AM daily
    minute=0
)

scheduler.start()
```

### Confidence Increase Detection

```python
def _check_confidence_increased(self, discovery: DiscoveryRecord, state: MonitorState) -> bool:
    """
    Check if discovery confidence increased significantly
    This can happen when more notes are added to related clusters
    """
    if not state.rejected_confidence:
        return False

    # Significant increase: +15% confidence
    increase_threshold = 0.15

    current = discovery.confidence_score
    previous = state.rejected_confidence

    if current > (previous + increase_threshold):
        log_info(
            f"Discovery {discovery.id} confidence increased: "
            f"{previous:.0%} → {current:.0%} (+{current-previous:.0%})"
        )
        return True

    return False
```

### LangGraph Integration

```python
from langgraph.graph import StateGraph

class MonitorState(BaseModel):
    discoveries_checked: int
    orphaned_found: int
    user_requests_sent: int
    errors: List[str]

def build_monitor_graph() -> StateGraph:
    """
    LangGraph workflow for Monitor agent
    """
    graph = StateGraph(MonitorState)

    graph.add_node("fetch_discoveries", fetch_high_confidence_discoveries)
    graph.add_node("check_sql", check_sql_existence)
    graph.add_node("filter_asked", filter_already_asked_discoveries)
    graph.add_node("forward_requests", forward_telegram_requests)
    graph.add_node("log_results", log_reconciliation_results)

    graph.set_entry_point("fetch_discoveries")
    graph.add_edge("fetch_discoveries", "check_sql")
    graph.add_edge("check_sql", "filter_asked")
    graph.add_edge("filter_asked", "forward_requests")
    graph.add_edge("forward_requests", "log_results")

    return graph.compile()
```

### Dependencies
- Story 010: Autonomous Pattern Detection (generates discoveries)
- Story 014: SQL Project Gatekeeper (SQL writes)
- Story 027: Message Outbox Relay (escalations to user)
- Discovery Vector DB (Weaviate)
- The Ananke (PostgreSQL)
- project_crystal Monitor concept

## Affected Components
- **Argus**: Monitor agent implementation
- **Alexandria**: Discovery DB + The Ananke
- **Alexandria**: Proposal queue + monitor state (SQLite)
- **Hermes**: Consumes outbox later

## Priority
**High** - Prevents high-value discoveries from being lost

## Estimate
8 story points (5-8 days)

## Linear Labels
`phase-4`, `latent-scout`, `monitor`, `reconciliation`, `argus`

## Related Stories
- Story 010: Autonomous Pattern Detection (data source)
- Story 014: SQL Project Gatekeeper (writes to SQL)
- Story 016: Project Manager Agent (manages SQL projects)
- project_crystal Monitor concept (watches SQL for stalls)

## Future Enhancements
- Auto-escalate: If user ignores 3 requests, mark as "user not interested"
- Team mode: Notify multiple users for approval
- Confidence trend analysis: Predict which discoveries will become high-confidence
- Integration with Prometheus: Draft proposals for orphaned discoveries
