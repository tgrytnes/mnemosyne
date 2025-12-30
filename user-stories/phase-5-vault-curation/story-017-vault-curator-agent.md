# Story 017: Vault Curator Agent (The Curator)

**As a** knowledge worker
**I want** an agent that analyzes my vault structure and suggests improvements
**So that** my notes stay well-organized, interconnected, and free of redundancy without manual maintenance

## 🎯 Architectural Role

**This story implements The Curator, an analysis agent in the Argus (Subconscious) layer.**

The Curator works alongside Scout, but focuses on vault hygiene rather than pattern discovery. It proactively identifies structural improvements and submits proposals for user approval.

**Workflow**: The Curator → Discovery DB → The Liaison → User approval → The Editor (Story 018) → Obsidian Gatekeeper

## Acceptance Criteria
- [ ] Background job runs weekly (Sunday 10 AM or configurable)
- [ ] Analyzes vault structure from The Muses embeddings
- [ ] Detects improvement opportunities: missing backlinks, redundant content, missing tags, structural issues
- [ ] Generates improvement proposals with confidence scores
- [ ] Stores proposals in Discovery Vector DB (type: "vault_improvement")
- [ ] Sends top 3-5 suggestions via Telegram
- [ ] User can approve/reject/defer suggestions
- [ ] Performance: Complete analysis in <15 minutes for 300+ notes
- [ ] Configurable sensitivity (how aggressive with suggestions)

## Improvement Types

### 1. Missing Backlinks
**Detection**: Find notes that should reference each other but don't

```python
class BacklinkSuggester:
    """
    Finds notes with semantic similarity that lack bidirectional links
    """
    def detect(self, similarity_threshold: float = 0.75) -> List[BacklinkProposal]:
        # Query The Muses for note pairs with high semantic similarity
        similar_pairs = self._find_similar_notes(threshold=similarity_threshold)

        # Filter: only pairs without existing wiki-links
        unlinked_pairs = [
            pair for pair in similar_pairs
            if not self._has_backlink(pair.note_a, pair.note_b)
        ]

        # Generate proposals
        proposals = []
        for pair in unlinked_pairs:
            proposals.append(BacklinkProposal(
                note_a=pair.note_a,
                note_b=pair.note_b,
                similarity=pair.similarity,
                suggested_context=self._extract_linking_context(pair),
                confidence=pair.similarity * 0.9  # Slightly discount
            ))

        return proposals

    def _extract_linking_context(self, pair) -> str:
        """
        Find the best sentence in each note to add the backlink
        """
        # Use semantic similarity to find most relevant sentences
        context_a = self._find_best_sentence(pair.note_a, pair.note_b)
        context_b = self._find_best_sentence(pair.note_b, pair.note_a)

        return {
            "note_a_context": context_a,
            "note_b_context": context_b
        }
```

**Example Proposal**:
```
📎 Missing Backlink Suggestion

**Note A**: "Docker Containerization.md"
**Note B**: "Microservices Architecture.md"

**Similarity**: 82%

**Suggested changes**:
In "Docker Containerization.md" line 42:
  "Containers enable isolated deployment"
  → "Containers enable isolated deployment, especially useful for [[Microservices Architecture]]"

In "Microservices Architecture.md" line 15:
  "Each service runs independently"
  → "Each service runs independently, often using [[Docker Containerization]]"

**Confidence**: 74%

Actions:
/approve_curation 123 - Apply both backlinks
/reject_curation 123 - Not relevant
/view_curation 123 - See full diff
```

---

### 2. Redundant Content Detection
**Detection**: Find notes with >70% overlapping content

```python
class RedundancyDetector:
    """
    Detects duplicate or highly redundant notes
    """
    def detect(self, redundancy_threshold: float = 0.70) -> List[RedundancyProposal]:
        # Use semantic similarity + TF-IDF to find redundant pairs
        all_notes = self._get_all_notes_from_muses()

        redundant_pairs = []
        for i, note_a in enumerate(all_notes):
            for note_b in all_notes[i+1:]:
                overlap = self._calculate_content_overlap(note_a, note_b)

                if overlap > redundancy_threshold:
                    redundant_pairs.append({
                        'note_a': note_a,
                        'note_b': note_b,
                        'overlap_percentage': overlap,
                        'merge_strategy': self._suggest_merge_strategy(note_a, note_b)
                    })

        return redundant_pairs

    def _suggest_merge_strategy(self, note_a, note_b):
        """
        Suggests how to merge: which note to keep, what to move
        """
        # Prefer keeping the note with more backlinks/references
        # Or the older note (more established)

        if note_a.backlink_count > note_b.backlink_count:
            return {
                'primary': note_a,
                'secondary': note_b,
                'action': 'merge_secondary_into_primary',
                'unique_content': self._extract_unique_content(note_b, note_a)
            }
        else:
            return {
                'primary': note_b,
                'secondary': note_a,
                'action': 'merge_secondary_into_primary',
                'unique_content': self._extract_unique_content(note_a, note_b)
            }
```

**Example Proposal**:
```
🔄 Redundant Content Detected

**Note A**: "React Hooks.md" (Created: 2024-01-15, 12 backlinks)
**Note B**: "Using React Hooks.md" (Created: 2024-03-20, 3 backlinks)

**Content overlap**: 78%

**Recommendation**: Merge "Using React Hooks.md" into "React Hooks.md"

**Unique content in secondary note**:
- Section "useCallback best practices" (not in primary)
- Example: Custom hook for API calls

**Proposed action**:
1. Copy unique sections from secondary → primary
2. Update backlinks pointing to secondary → primary
3. Archive secondary note (move to _Archive folder)

**Confidence**: 85%

Actions:
/approve_curation 124 - Merge notes
/reject_curation 124 - Keep separate
/defer_curation 124 7d - Decide later
```

---

### 3. Missing Tags
**Detection**: Suggest tags based on note content and cluster membership

```python
class TagSuggester:
    """
    Suggests missing tags based on cluster analysis
    """
    def detect(self) -> List[TagProposal]:
        # Get all clusters from The Ananke
        clusters = self._get_clusters_with_tags()

        proposals = []
        for cluster in clusters:
            # Find common tags in cluster
            common_tags = self._find_cluster_tags(cluster)

            # Find notes in cluster missing these tags
            for note in cluster.notes:
                missing_tags = [
                    tag for tag in common_tags
                    if tag not in note.tags and self._tag_relevance(note, tag) > 0.7
                ]

                if missing_tags:
                    proposals.append(TagProposal(
                        note=note,
                        suggested_tags=missing_tags,
                        reason=f"Common in cluster '{cluster.theme_summary}'",
                        confidence=self._calculate_tag_confidence(note, missing_tags)
                    ))

        return proposals
```

**Example Proposal**:
```
🏷️ Missing Tags Suggestion

**Note**: "Kubernetes Deployment Guide.md"

**Current tags**: #devops

**Suggested tags**:
- #kubernetes (90% of notes in this cluster use it)
- #orchestration (75% of similar notes use it)
- #containers (80% of notes about K8s mention containers)

**Reason**: This note clusters with "Container Orchestration" theme

**Confidence**: 82%

Actions:
/approve_curation 125 - Add all tags
/partial_curation 125 #kubernetes #containers - Add specific tags
/reject_curation 125 - No tags
```

---

### 4. Structural Issues
**Detection**: Find organizational problems

```python
class StructureAnalyzer:
    """
    Detects structural vault issues
    """
    def detect(self) -> List[StructureProposal]:
        issues = []

        # Issue 1: Orphaned notes (no links in/out, not in any folder)
        orphans = self._find_orphaned_notes()
        if orphans:
            issues.append(StructureProposal(
                issue_type='orphaned_notes',
                affected_notes=orphans,
                suggestion='Move to appropriate folders or add links',
                confidence=0.95
            ))

        # Issue 2: Over-nested folders (>4 levels deep)
        deep_folders = self._find_deep_folder_structures()
        if deep_folders:
            issues.append(StructureProposal(
                issue_type='deep_nesting',
                affected_paths=deep_folders,
                suggestion='Flatten folder structure or use tags instead',
                confidence=0.80
            ))

        # Issue 3: Empty folders
        empty_folders = self._find_empty_folders()
        if empty_folders:
            issues.append(StructureProposal(
                issue_type='empty_folders',
                affected_paths=empty_folders,
                suggestion='Remove empty folders',
                confidence=1.0
            ))

        return issues
```

**Example Proposal**:
```
🗂️ Structural Issue Detected

**Issue**: 8 orphaned notes (no backlinks, not in folders)

**Affected notes**:
- "Random thoughts 2024-01-15.md"
- "Meeting notes temp.md"
- "Draft idea.md"
- ... (5 more)

**Suggested actions**:
1. Move dated notes → "Daily Notes/" folder
2. Move "temp" notes → "_Inbox/" for review
3. Move "Draft" → appropriate project folder

**Confidence**: 90%

Actions:
/approve_curation 126 - Apply suggested moves
/review_curation 126 - Show full list first
/reject_curation 126 - Leave as is
```

---

### 5. Inconsistent Naming
**Detection**: Find notes with similar names that should be standardized

```python
class NamingAnalyzer:
    """
    Detects naming inconsistencies
    """
    def detect(self) -> List[NamingProposal]:
        all_notes = self._get_all_notes()

        # Group by semantic similarity in titles
        title_groups = self._group_similar_titles(all_notes)

        proposals = []
        for group in title_groups:
            if self._has_inconsistent_naming(group):
                proposals.append(NamingProposal(
                    notes=group,
                    issue='Inconsistent naming convention',
                    suggested_pattern=self._suggest_naming_pattern(group),
                    confidence=0.85
                ))

        return proposals
```

**Example Proposal**:
```
📝 Naming Inconsistency Detected

**Pattern**: Docker-related notes use inconsistent naming

**Current names**:
- "Docker - Networking.md"
- "docker_volumes.md"
- "Docker Compose Guide.md"
- "DOCKER_SECURITY.md"

**Suggested standardization**: "Docker - [Topic].md"

**Proposed renames**:
- "docker_volumes.md" → "Docker - Volumes.md"
- "DOCKER_SECURITY.md" → "Docker - Security.md"

(Keep others as-is, already match pattern)

**Confidence**: 75%

Actions:
/approve_curation 127 - Rename notes
/suggest_alternative 127 - Propose different pattern
/reject_curation 127 - Keep current names
```

---

## Technical Implementation

### The Curator Agent Class

```python
class VaultCuratorAgent:
    """
    Proactive vault improvement analysis
    Part of Argus (Subconscious layer)
    """
    def __init__(self, muses_client, ananke_db, discovery_db, messenger):
        self.muses = muses_client  # The Muses (Weaviate)
        self.ananke = ananke_db    # The Ananke (PostgreSQL)
        self.discovery_db = discovery_db  # Discovery Vector DB
        self.messenger = messenger  # The Liaison (Hermes)

        # Sub-analyzers
        self.backlink_suggester = BacklinkSuggester(self.muses)
        self.redundancy_detector = RedundancyDetector(self.muses)
        self.tag_suggester = TagSuggester(self.muses, self.ananke)
        self.structure_analyzer = StructureAnalyzer(self.muses)
        self.naming_analyzer = NamingAnalyzer(self.muses)

    def run_weekly_curation(self):
        """
        Weekly vault curation routine
        """
        log_info("Curator: Starting vault analysis")

        # Run all detectors
        backlink_proposals = self.backlink_suggester.detect()
        redundancy_proposals = self.redundancy_detector.detect()
        tag_proposals = self.tag_suggester.detect()
        structure_proposals = self.structure_analyzer.detect()
        naming_proposals = self.naming_analyzer.detect()

        # Combine and prioritize
        all_proposals = self._prioritize_proposals([
            *backlink_proposals,
            *redundancy_proposals,
            *tag_proposals,
            *structure_proposals,
            *naming_proposals
        ])

        # Store top proposals in Discovery DB
        for proposal in all_proposals[:10]:  # Top 10
            self._store_curation_proposal(proposal)

        # Send top 3-5 to user via The Liaison
        self._send_curation_digest(all_proposals[:5])

        log_info(f"Curator: Found {len(all_proposals)} improvement opportunities")

    def _prioritize_proposals(self, proposals):
        """
        Sort by impact × confidence
        """
        return sorted(
            proposals,
            key=lambda p: p.confidence * p.estimated_impact,
            reverse=True
        )

    def _store_curation_proposal(self, proposal):
        """
        Store in Discovery Vector DB for later retrieval
        """
        self.discovery_db.create({
            "discoveryId": str(uuid4()),
            "title": proposal.title,
            "description": proposal.description,
            "patternType": "vault_improvement",
            "improvementType": proposal.improvement_type,  # backlink, redundancy, etc.
            "confidenceScore": proposal.confidence,
            "affectedNotes": proposal.affected_notes,
            "suggestedChanges": proposal.suggested_changes,
            "detectedAt": datetime.now(),
            "userReviewed": False
        })

    def _send_curation_digest(self, top_proposals):
        """
        Send weekly curation suggestions via Telegram
        """
        message = f"""
🧹 **Weekly Vault Curation Digest**
{datetime.now().strftime('%B %d, %Y')}

The Curator has analyzed your vault and found {len(top_proposals)} high-priority improvements:

"""

        for i, proposal in enumerate(top_proposals, 1):
            message += f"""
**{i}. {proposal.title}**
Type: {proposal.improvement_type}
Confidence: {proposal.confidence:.0%}
Impact: {proposal.estimated_impact}/10

{proposal.summary}

`/view_curation {proposal.id}` - See details
`/approve_curation {proposal.id}` - Apply changes

"""

        message += """
**What happens when you approve?**
1. The Editor (Story 018) creates changes in shadow copy
2. You review the diff via Obsidian Gatekeeper
3. You approve final changes to vault

Use `/skip_curation_week` to pause weekly digests.
"""

        self.messenger.send_message(message)
```

---

## Telegram Commands (via The Liaison)

```python
# In Hermes bot

@hermes_bot.command("view_curation")
def cmd_view_curation(message, curation_id: str):
    """
    View full curation proposal details
    """
    proposal = curator.get_proposal(curation_id)

    if not proposal:
        return "Curation proposal not found."

    detail_message = f"""
🔍 **Curation Proposal Details**

**Type**: {proposal.improvement_type}
**Confidence**: {proposal.confidence:.0%}
**Impact**: {proposal.estimated_impact}/10

**Affected Notes**:
{format_note_list(proposal.affected_notes)}

**Proposed Changes**:
{format_changes_preview(proposal.suggested_changes)}

**Rationale**:
{proposal.rationale}

**Actions**:
`/approve_curation {curation_id}` - Send to The Editor
`/reject_curation {curation_id}` - Not interested
`/defer_curation {curation_id} 7d` - Remind me later
"""

    bot.send_message(
        chat_id=message.chat.id,
        text=detail_message,
        parse_mode='Markdown'
    )

@hermes_bot.command("approve_curation")
def cmd_approve_curation(message, curation_id: str):
    """
    Approve curation proposal → Send to The Editor
    """
    proposal = curator.get_proposal(curation_id)

    if not proposal:
        return "Curation proposal not found."

    # Mark as approved
    curator.mark_approved(curation_id)

    # Trigger The Editor (Story 018) to execute changes
    editor.execute_curation(proposal)

    bot.send_message(
        chat_id=message.chat.id,
        text=f"""
✅ Curation approved

The Editor is now creating shadow copy with proposed changes.
You'll receive a notification when ready for final review via Obsidian Gatekeeper.

Track progress: `/curation_status {curation_id}`
"""
    )

@hermes_bot.command("reject_curation")
def cmd_reject_curation(message, curation_id: str):
    """
    Reject curation proposal
    """
    curator.mark_rejected(curation_id)

    bot.send_message(
        chat_id=message.chat.id,
        text="✅ Curation proposal rejected. The Curator won't suggest this again."
    )

@hermes_bot.command("defer_curation")
def cmd_defer_curation(message, curation_id: str, duration: str):
    """
    Defer curation reminder
    Usage: /defer_curation 123 7d
    """
    remind_at = parse_duration(duration)
    curator.defer_proposal(curation_id, remind_at)

    bot.send_message(
        chat_id=message.chat.id,
        text=f"⏰ Reminder set for {format_date(remind_at)}"
    )

@hermes_bot.command("curation_history")
def cmd_curation_history(message):
    """
    Show past curation suggestions and outcomes
    """
    history = curator.get_history(limit=20)

    response = "📋 **Curation History**\n\n"

    for item in history:
        status_emoji = "✅" if item.approved else "❌" if item.rejected else "⏳"
        response += f"{status_emoji} {item.title} ({item.improvement_type})\n"
        response += f"   {format_datetime(item.detected_at)}\n\n"

    bot.send_message(
        chat_id=message.chat.id,
        text=response,
        parse_mode='Markdown'
    )
```

---

## Integration with Story 018 (The Editor)

When user approves a curation proposal:

```
The Curator (Story 017)
    ↓ User approves via /approve_curation
The Editor (Story 018)
    ↓ Creates shadow copy with changes
Obsidian Gatekeeper (Story 025)
    ↓ User reviews diff
Obsidian Vault
    ↓ Final approval applies changes
```

---

## Scheduled Job

```python
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()

# Weekly curation (Sunday 10 AM)
scheduler.add_job(
    curator.run_weekly_curation,
    'cron',
    day_of_week='sun',
    hour=10,
    minute=0
)

scheduler.start()
```

---

## Configuration

```python
# Environment variables or config
CURATOR_CONFIG = {
    'enabled': True,
    'schedule': 'weekly',  # weekly, biweekly, monthly
    'sensitivity': 'medium',  # low, medium, high
    'min_confidence': 0.70,  # Don't suggest below this
    'max_suggestions_per_week': 5,

    # Analyzer-specific settings
    'backlink_similarity_threshold': 0.75,
    'redundancy_threshold': 0.70,
    'tag_confidence_threshold': 0.75,

    # User preferences
    'skip_improvement_types': [],  # e.g., ['naming'] to disable naming suggestions
}

@hermes_bot.command("configure_curator")
def cmd_configure_curator(message, setting: str, value: str):
    """
    Adjust Curator settings
    Usage: /configure_curator sensitivity high
    """
    if setting in CURATOR_CONFIG:
        CURATOR_CONFIG[setting] = value
        save_curator_config(CURATOR_CONFIG)

        bot.send_message(
            chat_id=message.chat.id,
            text=f"✅ Curator setting updated: {setting} = {value}"
        )
    else:
        bot.send_message(
            chat_id=message.chat.id,
            text=f"Unknown setting. Available: {', '.join(CURATOR_CONFIG.keys())}"
        )
```

---

## Dependencies
- The Muses (Weaviate) - source of truth for note content and embeddings
- The Ananke (PostgreSQL) - cluster metadata for tag suggestions
- Discovery Vector DB - stores curation proposals
- The Liaison (Hermes) - sends suggestions via Telegram
- The Editor (Story 018) - executes approved changes
- Obsidian Gatekeeper (Story 025) - final approval layer

## Affected Components
- **Argus**: The Curator as new analysis agent
- **Alexandria**: Discovery DB stores proposals
- **Hermes**: The Liaison handles user interaction
- **The Gates**: Obsidian Gatekeeper (via The Editor)

## Priority
**Low-Medium** - Nice-to-have quality-of-life improvement (Phase 5)

## Estimate
13 story points (10-15 days) - complex analysis logic

## Linear Labels
`phase-5`, `vault-curation`, `argus`, `curator`, `vault-hygiene`, `proactive`

## Related Stories
- Story 025: Obsidian Gatekeeper (final approval of changes)
- Story 010: Scout (similar proactive pattern in Argus)
- Story 018: The Editor (executes curation changes)

## Future Enhancements
- Machine learning from user approvals/rejections to improve suggestions
- Custom curation rules ("never suggest backlinks to daily notes")
- Batch curation: approve multiple suggestions at once
- Vault health score dashboard
- Integration with Obsidian graph view to visualize suggested backlinks
