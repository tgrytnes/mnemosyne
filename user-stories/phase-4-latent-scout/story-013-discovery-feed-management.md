# Story 013: Discovery Feed Management

**As a** user
**I want** a centralized interface to review, dismiss, or act on all discoveries from the Latent Scout
**So that** I can process insights at my own pace without feeling pressured by notifications

## Acceptance Criteria
- [ ] Telegram command `/discoveries` lists all recent discoveries
- [ ] Filter discoveries by type, date, confidence, status
- [ ] Pagination for large discovery lists
- [ ] Bulk actions: dismiss all, mark as reviewed, archive
- [ ] Discovery detail view with full context and evidence
- [ ] Export discoveries to Obsidian note (formatted markdown)
- [ ] Search discoveries by keyword or cluster
- [ ] Stats view: discoveries over time, acceptance rate, top patterns
- [ ] "Explore mode": Interactive navigation through discovery graph

## Technical Notes

### Telegram Command Interface

```python
# In Hermes bot

@hermes_bot.command("discoveries")
def cmd_discoveries(message, args: List[str]):
    """
    Usage:
    /discoveries - Show all recent discoveries
    /discoveries new - Only unreviewed
    /discoveries type:project - Filter by type
    /discoveries week - Last 7 days
    """

    filters = parse_discovery_filters(args)
    discoveries = fetch_discoveries(filters)

    if not discoveries:
        return "No discoveries found matching your criteria."

    # Paginate (10 per page)
    page = filters.get('page', 1)
    paginated = paginate(discoveries, page=page, per_page=10)

    message_text = format_discovery_list(paginated)
    buttons = create_navigation_buttons(paginated, filters)

    bot.send_message(
        chat_id=message.chat.id,
        text=message_text,
        reply_markup=buttons,
        parse_mode='Markdown'
    )

def format_discovery_list(discoveries: PaginatedResult) -> str:
    header = f"""
📊 **Discovery Feed** (Page {discoveries.page}/{discoveries.total_pages})
Found {discoveries.total} discoveries

"""

    items = []
    for i, disc in enumerate(discoveries.items, 1):
        status_emoji = "🆕" if not disc.reviewed_at else "✅"
        type_emoji = get_emoji_for_type(disc.pattern_type)

        items.append(f"""
{status_emoji} {type_emoji} **{disc.title}**
{disc.confidence_score:.0%} confidence • {format_date(disc.detected_at)}
`/view {disc.id[:8]}`
""")

    return header + "\n".join(items)

def create_navigation_buttons(result: PaginatedResult, filters: dict):
    buttons = []

    # Pagination
    nav_row = []
    if result.has_prev:
        nav_row.append(InlineButton("◀️ Prev", callback=f"discoveries:page:{result.page-1}"))
    if result.has_next:
        nav_row.append(InlineButton("Next ▶️", callback=f"discoveries:page:{result.page+1}"))

    if nav_row:
        buttons.append(nav_row)

    # Filter toggles
    filter_row = [
        InlineButton("🔍 Filter", callback="discoveries:filter"),
        InlineButton("📈 Stats", callback="discoveries:stats"),
        InlineButton("⚙️ Settings", callback="settings:discoveries")
    ]
    buttons.append(filter_row)

    return InlineKeyboard(buttons)
```

### Discovery Detail View

```python
@hermes_bot.command("view")
def cmd_view_discovery(message, discovery_id: str):
    """
    Show detailed view of a single discovery
    """
    discovery = get_discovery(discovery_id)

    if not discovery:
        return "Discovery not found."

    # Mark as reviewed
    mark_as_reviewed(discovery.id)

    detail_message = format_discovery_detail(discovery)
    buttons = create_discovery_actions(discovery)

    bot.send_message(
        chat_id=message.chat.id,
        text=detail_message,
        reply_markup=buttons,
        parse_mode='Markdown'
    )

def format_discovery_detail(discovery: DiscoveryRecord) -> str:
    clusters = [get_cluster(cid) for cid in discovery.cluster_ids]

    message = f"""
{get_emoji_for_type(discovery.pattern_type)} **{discovery.title}**

**Type**: {discovery.pattern_type.replace('_', ' ').title()}
**Confidence**: {discovery.confidence_score:.0%}
**Detected**: {format_datetime(discovery.detected_at)}

**Description**:
{discovery.description}

**Clusters Involved**:
"""

    for cluster in clusters:
        message += f"• {cluster.profile.theme_summary} ({cluster.note_count} notes)\n"

    if discovery.metadata.get('evidence'):
        message += f"\n**Evidence**:\n"
        evidence = discovery.metadata['evidence'][:3]  # Top 3
        for note_id in evidence:
            note = get_note(note_id)
            message += f"• [[{note.title}]]\n"

    return message

def create_discovery_actions(discovery: DiscoveryRecord):
    buttons = [
        [
            InlineButton("📝 Create Note", callback=f"discovery_action:create_note:{discovery.id}"),
            InlineButton("🔗 Link Clusters", callback=f"discovery_action:link:{discovery.id}")
        ],
        [
            InlineButton("✅ Mark Helpful", callback=f"discovery_action:helpful:{discovery.id}"),
            InlineButton("❌ Dismiss", callback=f"discovery_action:dismiss:{discovery.id}")
        ],
        [
            InlineButton("📤 Export to Obsidian", callback=f"discovery_action:export:{discovery.id}")
        ],
        [
            InlineButton("◀️ Back to Feed", callback="discoveries:page:1")
        ]
    ]

    return InlineKeyboard(buttons)
```

### Filter Interface

```python
@hermes_bot.callback_handler("discoveries:filter")
def handle_filter_menu(callback_query):
    filter_menu = """
🔍 **Filter Discoveries**

Choose filters to apply:
"""

    buttons = [
        [
            InlineButton("🌱 Emerging Themes", callback="filter:type:emerging_theme"),
            InlineButton("🎯 Projects", callback="filter:type:project_candidate")
        ],
        [
            InlineButton("⚠️ Contradictions", callback="filter:type:contradiction"),
            InlineButton("🔗 Weak Links", callback="filter:type:weak_link")
        ],
        [
            InlineButton("🆕 Unreviewed Only", callback="filter:status:unreviewed"),
            InlineButton("✅ Reviewed Only", callback="filter:status:reviewed")
        ],
        [
            InlineButton("📅 Last 7 Days", callback="filter:date:week"),
            InlineButton("📅 Last 30 Days", callback="filter:date:month")
        ],
        [
            InlineButton("🎯 High Confidence (>80%)", callback="filter:confidence:high"),
            InlineButton("📊 All Confidence", callback="filter:confidence:all")
        ],
        [
            InlineButton("🔄 Reset Filters", callback="filter:reset"),
            InlineButton("✅ Apply", callback="discoveries:page:1")
        ]
    ]

    bot.edit_message_text(
        message_id=callback_query.message.id,
        chat_id=callback_query.message.chat.id,
        text=filter_menu,
        reply_markup=InlineKeyboard(buttons)
    )
```

### Stats Dashboard

```python
@hermes_bot.callback_handler("discoveries:stats")
def handle_stats_view(callback_query):
    stats = calculate_discovery_stats()

    stats_message = f"""
📈 **Discovery Statistics**

**All Time**:
• Total discoveries: {stats.total_discoveries}
• Reviewed: {stats.reviewed_count} ({stats.review_rate:.0%})
• Marked helpful: {stats.helpful_count}
• Dismissed: {stats.dismissed_count}

**By Type**:
{format_type_breakdown(stats.by_type)}

**Last 30 Days**:
• New discoveries: {stats.last_30_days}
• Avg per day: {stats.avg_per_day:.1f}
• Top pattern: {stats.top_pattern_last_30}

**Quality Metrics**:
• Avg confidence: {stats.avg_confidence:.0%}
• Acceptance rate: {stats.acceptance_rate:.0%}
    """

    buttons = [
        [InlineButton("📊 Export Report", callback="stats:export")],
        [InlineButton("◀️ Back to Feed", callback="discoveries:page:1")]
    ]

    bot.edit_message_text(
        message_id=callback_query.message.id,
        chat_id=callback_query.message.chat.id,
        text=stats_message,
        reply_markup=InlineKeyboard(buttons)
    )

def calculate_discovery_stats() -> DiscoveryStats:
    all_discoveries = get_all_discoveries()

    return DiscoveryStats(
        total_discoveries=len(all_discoveries),
        reviewed_count=len([d for d in all_discoveries if d.reviewed_at]),
        helpful_count=len([d for d in all_discoveries if d.user_feedback == 'helpful']),
        dismissed_count=len([d for d in all_discoveries if d.dismissed_at]),
        by_type=Counter([d.pattern_type for d in all_discoveries]),
        last_30_days=len([d for d in all_discoveries if d.detected_at > datetime.now() - timedelta(days=30)]),
        avg_confidence=mean([d.confidence_score for d in all_discoveries]),
        # ... more stats
    )
```

### Export to Obsidian

```python
@hermes_bot.callback_handler("discovery_action:export:*")
def handle_export_to_obsidian(callback_query):
    discovery_id = callback_query.data.split(":")[-1]
    discovery = get_discovery(discovery_id)

    # Generate Obsidian note
    note_content = generate_discovery_note(discovery)

    # Save to vault via The Graphos
    filename = f"Discoveries/{discovery.detected_at.strftime('%Y-%m-%d')}-{slugify(discovery.title)}.md"
    filepath = write_to_graphos(filename, note_content)

    bot.answer_callback_query(
        callback_query.id,
        text=f"✅ Exported to {filename}"
    )

    # Update message
    bot.edit_message_text(
        message_id=callback_query.message.id,
        chat_id=callback_query.message.chat.id,
        text=f"✅ Discovery exported to Obsidian!\n\n`{filename}`\n\n" + callback_query.message.text
    )

def generate_discovery_note(discovery: DiscoveryRecord) -> str:
    """
    Create formatted Obsidian note from discovery
    """
    clusters = [get_cluster(cid) for cid in discovery.cluster_ids]

    note = f"""---
type: discovery
pattern_type: {discovery.pattern_type}
confidence: {discovery.confidence_score}
detected_at: {discovery.detected_at.isoformat()}
clusters: [{', '.join(discovery.cluster_ids)}]
tags: [latent-scout, {discovery.pattern_type}]
---

# {discovery.title}

## Discovery Summary
{discovery.description}

**Confidence**: {discovery.confidence_score:.0%}
**Detected**: {discovery.detected_at.strftime('%B %d, %Y at %H:%M')}

## Involved Clusters

"""

    for cluster in clusters:
        note += f"""
### {cluster.profile.theme_summary}
- **Notes**: {cluster.note_count}
- **Tags**: {', '.join(cluster.profile.tags)}
- **Key Entities**: {', '.join(cluster.profile.key_entities[:5])}

"""

    if discovery.metadata.get('evidence'):
        note += "\n## Supporting Evidence\n\n"
        for note_id in discovery.metadata['evidence']:
            note_obj = get_note(note_id)
            note += f"- [[{note_obj.title}]]\n"

    note += f"\n---\n*Generated by Mnemosyne Latent Scout*\n"

    return note
```

### Bulk Actions

```python
@hermes_bot.command("discoveries_bulk")
def cmd_bulk_actions(message, action: str):
    """
    Usage:
    /discoveries_bulk dismiss_old - Dismiss discoveries older than 30 days
    /discoveries_bulk mark_reviewed - Mark all as reviewed
    /discoveries_bulk export_week - Export last week's discoveries
    """

    if action == "dismiss_old":
        cutoff = datetime.now() - timedelta(days=30)
        count = dismiss_discoveries_before(cutoff)
        return f"✅ Dismissed {count} discoveries older than 30 days"

    elif action == "mark_reviewed":
        count = mark_all_as_reviewed()
        return f"✅ Marked {count} discoveries as reviewed"

    elif action == "export_week":
        discoveries = get_discoveries_last_n_days(7)
        filepath = export_discoveries_to_markdown(discoveries)
        return f"✅ Exported {len(discoveries)} discoveries to {filepath}"

    else:
        return "Unknown bulk action. Use: dismiss_old, mark_reviewed, export_week"
```

### Discovery Search

```python
@hermes_bot.command("search_discoveries")
def cmd_search_discoveries(message, query: str):
    """
    Semantic search across discoveries
    """
    query_embedding = embed_text(query)

    # Search in Discovery Vector DB
    results = weaviate_client.query(
        collection="Discoveries",
        near_vector=query_embedding,
        limit=10
    )

    if not results:
        return f"No discoveries found for '{query}'"

    message_text = f"🔍 **Search Results for '{query}'**\n\n"

    for i, disc in enumerate(results, 1):
        message_text += f"{i}. {disc.title} ({disc.confidence_score:.0%})\n"
        message_text += f"   `/view {disc.id[:8]}`\n\n"

    bot.send_message(
        chat_id=message.chat.id,
        text=message_text,
        parse_mode='Markdown'
    )
```

### Dependencies
- Story 010: Autonomous Pattern Detection (generates discoveries)
- Story 011: Radar Vector Exploration (generates weak links)
- Story 012: Proactive Insight Notifications (alternative interface)
- Hermes: Telegram bot infrastructure
- Alexandria: Discovery DB (Weaviate + The Ananke)
- Aletheia: The Graphos (for Obsidian export)

## Affected Components
- **Hermes**: Primary implementation (all commands and handlers)
- **Alexandria**: Discovery DB queries
- **Aletheia**: Export to Obsidian vault

## Priority
**Medium** - Important for power users, but notifications (Story 012) cover basic needs

## Estimate
8 story points (5-8 days)

## Linear Labels
`phase-4`, `latent-scout`, `telegram`, `user-interface`, `hermes`

## Related Stories
- Story 010: Autonomous Pattern Detection (data source)
- Story 011: Radar Vector Exploration (data source)
- Story 012: Proactive Insight Notifications (complementary UX)

## Future Enhancements
- Web dashboard (alternative to Telegram)
- Mobile app integration
- Collaborative feed (share discoveries with team)
- Discovery templates (user-defined patterns to look for)
- AI-powered discovery summaries (weekly/monthly rollups)
- Integration with spaced repetition (resurface old discoveries)
