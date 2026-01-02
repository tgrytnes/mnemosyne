# Story 012: Proactive Insight Notifications

**As a** user
**I want** to receive unsolicited discoveries from the Latent Scout via Telegram
**So that** I'm alerted to interesting patterns without having to check manually

## Acceptance Criteria
### Hermes Transport + Message Outbox (Story 027)
- [ ] Hermes consumes `message_outbox` and delivers outbound messages to Telegram
- [ ] Outbox messages include `originating_agent`, `context_id`, `message_type`, `payload_json`
- [ ] Hermes updates outbox status (`pending` → `delivered` / `failed`) and `last_error` on failure
- [ ] Hermes writes user responses back to outbox (`response_json`, `response_received_at`)
- [ ] PM questions use `expects_response=True` (PM decides *when* to ask; Story 12 only delivers)
- [ ] Every question includes a stable `message_id` and Hermes correlates replies to that outbox record
- [ ] Telegram callback data includes the outbox `message_id` for every inline action
- [ ] Free-text replies require `/reply <message_id> <value>` or map to the most recent pending question for that chat
- [ ] If no pending question matches, Hermes sends a help prompt and does not alter outbox state
- [ ] Hermes stores `telegram_message_id` + `chat_id` on delivery and resolves replies via `reply_to_message` mapping (no manual IDs needed)

### Notification Preferences + History
- [ ] Configurable notification preferences (types, thresholds, quiet hours, batch mode)
- [ ] Rate limiting for discovery notifications (default max 3/day, configurable)
- [ ] Notification history viewable via Telegram command (e.g., `/discoveries`)
- [ ] Notification settings view/edit via Telegram commands (e.g., `/notify_settings`, `/quiet_hours`)

### Discovery Notifications (Scout/Monitor → Hermes)
- [ ] Smart batching: group multiple discoveries into digest messages
- [ ] Rich formatting: cluster names, confidence scores, and quick-action buttons
- [ ] Emergency bypass: critical discoveries (e.g., contradictions) always notify
- [ ] Notification templates exist for each discovery type (theme, contradiction, project candidate, weak link, digest)

### Inline Actions + Response Routing
- [ ] Inline actions: "View Details", "Dismiss", "Create Note", "Remind Later"
- [ ] Action handlers route responses to the originating agent via outbox (no direct PM scheduling logic in Hermes)
- [ ] Dismissals update discovery feedback (for noise reduction) without suppressing PM follow-ups

### Scope Guardrails
- [ ] Story 12 is **transport and UX only**; scheduling/enrichment logic lives in Story 16
- [ ] Hermes does not decide when to ask PM questions; it only delivers and records replies

## Technical Notes

### Notification Preferences Schema

```python
class NotificationPreferences(BaseModel):
    user_id: str
    enabled: bool = True
    quiet_hours: Tuple[int, int] = (22, 8)  # 10 PM - 8 AM
    max_daily_notifications: int = 3

    # Which discovery types to notify
    notify_emerging_themes: bool = True
    notify_orphaned_clusters: bool = False
    notify_contradictions: bool = True
    notify_project_candidates: bool = True
    notify_weak_links: bool = True

    # Minimum confidence threshold per type
    min_confidence_emerging: float = 0.7
    min_confidence_contradiction: float = 0.8
    min_confidence_project: float = 0.75
    min_confidence_weak_link: float = 0.6

    # Batching preferences
    batch_mode: Literal['immediate', 'daily_digest', 'weekly_digest'] = 'daily_digest'
    digest_time: int = 9  # 9 AM

# Store in The Ananke (PostgreSQL)
```

### Response Correlation Contract

To ensure replies go to the correct agent/question:

- Every outbound question is stored in `message_outbox` with a unique `message_id`.
- Hermes includes that `message_id` in Telegram callbacks (e.g., `reply:message_id:<value>`).
- For free-text replies, Hermes requires `/reply <message_id> <value>` or maps to the most recent pending question for that chat.
- Hermes stores `telegram_message_id` + `chat_id` on delivery and maps `reply_to_message.message_id` back to the outbox record.
- Hermes writes responses back to `message_outbox` with `response_json` + `response_received_at` and preserves `originating_agent`.

### Notification Templates

#### Template 1: Emerging Theme
```python
def format_emerging_theme(discovery: DiscoveryRecord) -> TelegramMessage:
    cluster = get_cluster(discovery.cluster_ids[0])

    message = f"""
🌱 **Emerging Theme Detected**

**{cluster.profile.theme_summary}**

You've added {discovery.metadata['note_count']} notes about this in the last {discovery.metadata['days']} days.

📊 Confidence: {discovery.confidence_score:.0%}
📝 Total notes: {cluster.note_count}
🏷️ Tags: {', '.join(cluster.profile.tags[:3])}

This might be developing into a project!
    """

    buttons = [
        InlineButton("View Cluster", callback="view_cluster:" + cluster.id),
        InlineButton("Create Project", callback="create_project:" + cluster.id),
        InlineButton("Dismiss", callback="dismiss:" + discovery.id)
    ]

    return TelegramMessage(text=message, buttons=buttons)
```

#### Template 2: Contradiction
```python
def format_contradiction(discovery: DiscoveryRecord) -> TelegramMessage:
    c1 = get_cluster(discovery.cluster_ids[0])
    c2 = get_cluster(discovery.cluster_ids[1])

    message = f"""
⚠️ **Potential Contradiction Found**

**Cluster 1**: {c1.profile.theme_summary}
**Cluster 2**: {c2.profile.theme_summary}

{discovery.description}

This might indicate:
• Evolving understanding
• Context-dependent views
• Research to reconcile

📊 Confidence: {discovery.confidence_score:.0%}
    """

    buttons = [
        InlineButton("View Both", callback="compare:" + c1.id + ":" + c2.id),
        InlineButton("Not a Contradiction", callback="dismiss:" + discovery.id),
        InlineButton("Remind Later", callback="remind:7d:" + discovery.id)
    ]

    return TelegramMessage(text=message, buttons=buttons)
```

#### Template 3: Project Candidate
```python
def format_project_candidate(discovery: DiscoveryRecord) -> TelegramMessage:
    cluster = get_cluster(discovery.cluster_ids[0])
    signals = discovery.metadata['projectness_signals']

    message = f"""
🎯 **Potential Project Identified**

**{cluster.profile.theme_summary}**

Projectness indicators:
• {signals['note_count']} notes in cluster
• {signals['action_verbs']} action-oriented notes
• {signals['cross_references']} cross-references
• Active in last {signals['days_since_update']} days

📊 Project Score: {discovery.confidence_score:.0%}

Would you like me to draft a project brief?
    """

    buttons = [
        InlineButton("Draft Project Brief", callback="draft_project:" + cluster.id),
        InlineButton("View Notes", callback="view_cluster:" + cluster.id),
        InlineButton("Not a Project", callback="dismiss:" + discovery.id)
    ]

    return TelegramMessage(text=message, buttons=buttons)
```

#### Template 4: Weak Link
```python
def format_weak_link(discovery: WeakLink) -> TelegramMessage:
    c1 = get_cluster(discovery.cluster1_id)
    c2 = get_cluster(discovery.cluster2_id)

    message = f"""
🔗 **Unexpected Connection Found**

**{c1.profile.theme_summary}** ↔️ **{c2.profile.theme_summary}**

{discovery.explanation}

This connection isn't obvious from your note structure but might be valuable.

📊 Confidence: {discovery.confidence_score:.0%}
    """

    buttons = [
        InlineButton("Explore Connection", callback="explore_link:" + discovery.id),
        InlineButton("Create Linking Note", callback="link_note:" + discovery.id),
        InlineButton("Dismiss", callback="dismiss:" + discovery.id)
    ]

    return TelegramMessage(text=message, buttons=buttons)
```

#### Template 5: Daily Digest
```python
def format_daily_digest(discoveries: List[DiscoveryRecord]) -> TelegramMessage:
    message = f"""
📰 **Daily Discovery Digest**
{datetime.now().strftime('%B %d, %Y')}

Found {len(discoveries)} interesting patterns overnight:

"""

    for i, disc in enumerate(discoveries[:5], 1):  # Top 5
        emoji = get_emoji_for_type(disc.pattern_type)
        message += f"{i}. {emoji} {disc.title} ({disc.confidence_score:.0%})\n"

    message += f"\nUse `/discoveries` to explore all findings."

    buttons = [
        InlineButton("View All", callback="discoveries:all"),
        InlineButton("Settings", callback="settings:notifications")
    ]

    return TelegramMessage(text=message, buttons=buttons)
```

### Notification Logic (Integration with Story 010 + Outbox)

```python
# In Story 010's notify node
@langgraph_node
def notify_via_hermes_node(state: LatentScoutState) -> LatentScoutState:
    """
    Final node in scout graph - sends notifications
    """
    prefs = get_user_notification_preferences()

    if not prefs.enabled:
        return state

    # Filter discoveries by preferences
    discoveries_to_notify = filter_by_preferences(
        state.patterns_detected,
        prefs
    )

    # Check rate limits
    if reached_daily_limit(prefs):
        # Queue for next day
        queue_for_later(discoveries_to_notify)
        return state

    # Check quiet hours
    if is_quiet_hours(prefs):
        schedule_for_morning(discoveries_to_notify, prefs.digest_time)
        return state

    # Send based on batch mode (enqueue to outbox)
    if prefs.batch_mode == 'immediate':
        for discovery in discoveries_to_notify:
            enqueue_notification(discovery, expects_response=False)

    elif prefs.batch_mode == 'daily_digest':
        # Will be sent at prefs.digest_time
        queue_for_digest(discoveries_to_notify, prefs.digest_time)

    return state

def enqueue_notification(discovery: DiscoveryRecord, expects_response: bool):
    """
    Enqueue for Hermes delivery via Message Outbox (Story 027).
    """
    message = format_discovery(discovery)
    outbox.enqueue(
        message_type="discovery_notification",
        payload={
            "chat_id": get_user_chat_id(),
            "text": message.text,
            "buttons": message.buttons,
            "parse_mode": "Markdown",
            "discovery_id": discovery.id,
        },
        expects_response=expects_response,
        originating_agent="latent_scout",
        context_id=str(discovery.id),
    )
```

### Inline Action Handlers

```python
# Telegram callback handlers in Hermes (transport only)

@hermes_bot.callback_handler("view_cluster:*")
def handle_view_cluster(callback_query):
    cluster_id = callback_query.data.split(":")[1]
    cluster = get_cluster(cluster_id)

    # Generate cluster summary
    notes = get_cluster_notes(cluster_id)
    summary = f"""
📚 **Cluster: {cluster.profile.theme_summary}**

**Notes ({len(notes)})**:
{format_note_list(notes[:10])}

**Tags**: {', '.join(cluster.profile.tags)}
**Last updated**: {cluster.last_modified}
    """

    bot.edit_message(callback_query.message.id, summary)

@hermes_bot.callback_handler("dismiss:*")
def handle_dismiss(callback_query):
    discovery_id = callback_query.data.split(":")[1]

    # Mark as dismissed and forward feedback via outbox
    outbox.record_feedback(
        message_type="discovery_feedback",
        context_id=discovery_id,
        payload={"feedback": "dismissed"},
    )

    bot.answer_callback_query(
        callback_query.id,
        text="✅ Dismissed. I'll learn from this."
    )
    bot.delete_message(callback_query.message.id)

@hermes_bot.callback_handler("create_project:*")
def handle_create_project(callback_query):
    cluster_id = callback_query.data.split(":")[1]

    # Forward intent via outbox for upstream agent to act
    outbox.record_feedback(
        message_type="create_project",
        context_id=cluster_id,
        payload={"source": "telegram"},
    )

@hermes_bot.callback_handler("remind:*")
def handle_remind_later(callback_query):
    parts = callback_query.data.split(":")
    days = int(parts[1].replace('d', ''))
    discovery_id = parts[2]

    # Forward reminder intent via outbox
    outbox.record_feedback(
        message_type="remind_later",
        context_id=discovery_id,
        payload={"days": days},
    )

    bot.answer_callback_query(
        callback_query.id,
        text=f"⏰ I'll remind you in {days} days"
    )
```

### Learning from Feedback (Preferences)

```python
class FeedbackLearner:
    """
    Adjust confidence thresholds based on user feedback
    """
    def update_confidence_model(self, discovery: DiscoveryRecord, feedback: str):
        # Track dismiss rate per pattern type
        stats = get_pattern_stats(discovery.pattern_type)

        if feedback == 'dismissed':
            stats.dismiss_count += 1
        elif feedback == 'helpful':
            stats.helpful_count += 1

        # Adjust threshold if dismiss rate > 50%
        dismiss_rate = stats.dismiss_count / (stats.dismiss_count + stats.helpful_count)

        if dismiss_rate > 0.5:
            # Increase threshold to reduce noise
            prefs = get_user_notification_preferences()
            current_threshold = getattr(prefs, f'min_confidence_{discovery.pattern_type}')
            new_threshold = min(current_threshold + 0.05, 0.95)

            setattr(prefs, f'min_confidence_{discovery.pattern_type}', new_threshold)
            save_preferences(prefs)
```

### Dependencies
- Story 027: Message Outbox Relay (transport queue + responses)
- Story 016: Project Manager Agent (scheduling, enrichment questions)
- Story 010: Autonomous Pattern Detection (generates discoveries)
- Story 011: Radar Vector Exploration (generates weak links)
- Alexandria: The Ananke (preferences storage)

## Affected Components
- **Hermes**: Primary implementation (notification sending, callback handlers)
- **Argus**: Calls notification logic from scout graph
- **Alexandria**: Stores preferences

## Priority
**High** - Critical for latent scout user experience

## Estimate
8 story points (5-8 days)

## Linear Labels
`phase-4`, `latent-scout`, `notifications`, `telegram`, `hermes`, `user-experience`

## Related Stories
- Story 010: Autonomous Pattern Detection (triggers notifications)
- Story 011: Radar Vector Exploration (sends weak link notifications)
- Story 013: Discovery Feed Management (alternative to notifications)

## Test Coverage
- [ ] Unit: message formatting, preference filtering, and outbox payload serialization (mocks ok)
- [ ] Integration: real Postgres + message outbox + Hermes send path (skip if required env vars missing)
- [ ] E2E: discovery → outbox → Hermes → Telegram → response recorded → discovery updated

## Future Enhancements
- Push notifications to mobile app (if built)
- Email digest option
- Notification analytics dashboard
- Voice notifications via smart speaker
- Collaborative mode: share discoveries with team
