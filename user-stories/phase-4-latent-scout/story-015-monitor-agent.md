# Story 015: Monitor Agent (Discovery → SQL Reconciliation)

**As a** user
**I want** an agent that monitors the gap between discoveries and SQL projects
**So that** high-value discoveries don't get lost when the gatekeeper denies them

## Acceptance Criteria
- [ ] Background agent runs daily (scheduled job)
- [ ] Queries Discovery Vector DB for high-confidence discoveries (>70%)
- [ ] Checks if each discovery exists in The Ananke `projects` table
- [ ] Identifies "orphaned discoveries" (high confidence but not in SQL)
- [ ] Forwards orphaned discoveries to user via Telegram with context
- [ ] Tracks user responses: approve, reject, remind later
- [ ] Logs reconciliation state to avoid re-asking
- [ ] Performance: Complete scan in <5 minutes for 100+ discoveries
- [ ] Configurable scan frequency (daily, weekly)

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

### Monitor Agent Class

```python
class MonitorAgent:
    """
    Reconciles Discovery Vector DB with The Ananke (SQL)
    Based on project_crystal Monitor concept
    """
    def __init__(self, weaviate_client, db_conn, messenger):
        self.weaviate = weaviate_client
        self.db = db_conn
        self.messenger = messenger  # Hermes
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

        # 4. Forward to user via Telegram
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
        """, (discovery.id,))

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
        Send Telegram message asking user to reconsider
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
`/monitor_approve {discovery.id}` - Add to projects
`/monitor_reject {discovery.id}` - Not a project
`/monitor_snooze {discovery.id} 7d` - Ask again in 7 days
`/monitor_view {discovery.id}` - See full details
"""

        self.messenger.send_message(message)

        # Mark as asked
        self._record_ask(discovery.id)

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

### Telegram Commands (Monitor Agent Actions)

```python
# In Hermes bot

@hermes_bot.command("monitor_approve")
def cmd_monitor_approve(message, discovery_id: str):
    """
    User approves discovery via Monitor agent
    """
    discovery = get_discovery(discovery_id)

    if not discovery:
        return "Discovery not found."

    # Write to SQL via Gatekeeper
    try:
        project_id = sql_gatekeeper.write_project_from_discovery(discovery)

        # Update monitor state
        monitor_agent.mark_approved(discovery_id)

        bot.send_message(
            chat_id=message.chat.id,
            text=f"✅ Project '{discovery.title}' added to The Ananke.\nProject ID: {project_id}"
        )
    except Exception as e:
        bot.send_message(
            chat_id=message.chat.id,
            text=f"❌ Failed to add project: {e}"
        )

@hermes_bot.command("monitor_reject")
def cmd_monitor_reject(message, discovery_id: str):
    """
    User confirms discovery is not a project
    """
    discovery = get_discovery(discovery_id)

    if not discovery:
        return "Discovery not found."

    # Record rejection
    monitor_agent.mark_rejected(discovery_id, discovery.confidence_score)

    bot.send_message(
        chat_id=message.chat.id,
        text=f"✅ Marked '{discovery.title}' as not a project.\n"
             f"Monitor will not ask about this again (unless confidence increases significantly)."
    )

@hermes_bot.command("monitor_snooze")
def cmd_monitor_snooze(message, discovery_id: str, duration: str):
    """
    Snooze discovery reminder
    Usage: /monitor_snooze abc123 7d
    """
    discovery = get_discovery(discovery_id)

    if not discovery:
        return "Discovery not found."

    # Parse duration (7d, 2w, 1m)
    snooze_until = parse_snooze_duration(duration)

    monitor_agent.mark_snoozed(discovery_id, snooze_until)

    bot.send_message(
        chat_id=message.chat.id,
        text=f"⏰ Snoozed '{discovery.title}' until {format_date(snooze_until)}"
    )

@hermes_bot.command("monitor_view")
def cmd_monitor_view(message, discovery_id: str):
    """
    View full discovery details
    """
    discovery = get_discovery(discovery_id)

    if not discovery:
        return "Discovery not found."

    # Show full details
    clusters = [get_cluster(cid) for cid in discovery.cluster_ids]

    detail_message = f"""
📊 **Discovery Details**

**Title**: {discovery.title}
**Description**: {discovery.description}

**Confidence**: {discovery.confidence_score:.0%}
**Detected**: {format_datetime(discovery.detected_at)}

**Clusters**:
"""

    for cluster in clusters:
        detail_message += f"""
• {cluster.profile.theme_summary}
  Notes: {cluster.note_count}
"""

    detail_message += f"""
**Actions**:
`/monitor_approve {discovery_id}`
`/monitor_reject {discovery_id}`
`/monitor_snooze {discovery_id} 7d`
"""

    bot.send_message(
        chat_id=message.chat.id,
        text=detail_message,
        parse_mode='Markdown'
    )

@hermes_bot.command("monitor_status")
def cmd_monitor_status(message):
    """
    Show Monitor agent statistics
    """
    stats = monitor_agent.get_statistics()

    status_message = f"""
📊 **Monitor Agent Status**

**Last Run**: {format_datetime(stats.last_run)}

**Discoveries**:
• Total high-confidence: {stats.total_high_confidence}
• In SQL: {stats.in_sql}
• Orphaned: {stats.orphaned}

**User Responses**:
• Approved: {stats.approved_count}
• Rejected: {stats.rejected_count}
• Snoozed: {stats.snoozed_count}
• Pending: {stats.pending_count}

**Next Run**: {format_datetime(stats.next_run)}
"""

    bot.send_message(
        chat_id=message.chat.id,
        text=status_message,
        parse_mode='Markdown'
    )
```

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
        # Notify admin
        messenger.send_message(f"⚠️ Monitor Agent error: {e}")

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
- Discovery Vector DB (Weaviate)
- The Ananke (PostgreSQL)
- Hermes (Telegram bot)
- project_crystal Monitor concept

## Affected Components
- **Argus**: Monitor agent implementation
- **Alexandria**: Discovery DB + The Ananke
- **Hermes**: Telegram commands for user responses

## Priority
**High** - Prevents high-value discoveries from being lost

## Estimate
8 story points (5-8 days)

## Linear Labels
`phase-4`, `latent-scout`, `monitor`, `reconciliation`, `argus`, `hermes`

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
