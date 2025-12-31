# Story 012: Proactive Insight Notifications

**As a** user
**I want** to receive unsolicited discoveries from the Latent Scout via Telegram
**So that** I'm alerted to interesting patterns without having to check manually

## Acceptance Criteria
- [ ] Hermes Telegram notifications wired: discovery payload includes `discovery_id` and `discovery_job_key`
- [ ] Preferences stored in SQL: enabled flag, quiet hours, `max_daily_notifications`, batch mode (immediate vs daily_digest), per-type toggles, per-type confidence thresholds
- [ ] Respect quiet hours + rate limiting; critical contradictions bypass quiet hours; batching groups findings by type
- [ ] Templates per discovery type include confidence + action buttons (view, dismiss/feedback, follow-up); dismissal/feedback persisted in SQL and suppresses future noise for that discovery id/type
- [ ] History commands: `/discoveries` list and `/discoveries stats`; digest message generation works with batching
- [ ] Inline actions update status (reviewed/dismissed) and are idempotent; immediate notifications and daily digest both covered in tests

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

### Notification Logic (Integration with Story 010)

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

    # Send based on batch mode
    if prefs.batch_mode == 'immediate':
        for discovery in discoveries_to_notify:
            send_notification(discovery)

    elif prefs.batch_mode == 'daily_digest':
        # Will be sent at prefs.digest_time
        queue_for_digest(discoveries_to_notify, prefs.digest_time)

    return state

def send_notification(discovery: DiscoveryRecord):
    """
    Send via Hermes Telegram bot
    """
    message = format_discovery(discovery)

    try:
        hermes_bot.send_message(
            chat_id=get_user_chat_id(),
            text=message.text,
            reply_markup=message.buttons,
            parse_mode='Markdown'
        )

        # Mark as notified
        update_discovery(discovery.id, notified_at=datetime.now())

    except Exception as e:
        log_error(f"Failed to send notification: {e}")
        # Retry later
        queue_for_retry(discovery)
```

### Inline Action Handlers

```python
# Telegram callback handlers in Hermes

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

    # Mark as dismissed and learn from feedback
    dismiss_discovery(discovery_id)
    update_confidence_model(discovery_id, feedback='dismissed')

    bot.answer_callback_query(
        callback_query.id,
        text="✅ Dismissed. I'll learn from this."
    )
    bot.delete_message(callback_query.message.id)

@hermes_bot.callback_handler("create_project:*")
def handle_create_project(callback_query):
    cluster_id = callback_query.data.split(":")[1]

    # Trigger Prometheus to draft project proposal
    project_brief = prometheus.draft_project_brief(cluster_id)

    bot.send_message(
        chat_id=callback_query.message.chat.id,
        text=f"✅ Project brief drafted!\n\n{project_brief}"
    )

@hermes_bot.callback_handler("remind:*")
def handle_remind_later(callback_query):
    parts = callback_query.data.split(":")
    days = int(parts[1].replace('d', ''))
    discovery_id = parts[2]

    # Schedule reminder
    schedule_reminder(discovery_id, days_from_now=days)

    bot.answer_callback_query(
        callback_query.id,
        text=f"⏰ I'll remind you in {days} days"
    )
```

### Learning from Feedback

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
- Story 010: Autonomous Pattern Detection (generates discoveries)
- Story 011: Radar Vector Exploration (generates weak links)
- Hermes: Telegram bot infrastructure
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

## Future Enhancements
- Push notifications to mobile app (if built)
- Email digest option
- Notification analytics dashboard
- Voice notifications via smart speaker
- Collaborative mode: share discoveries with team
