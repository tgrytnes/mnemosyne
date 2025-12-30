# Story 018: Vault Editor Agent (The Editor)

**As a** user
**I want** approved curation suggestions automatically applied to a shadow copy for my review
**So that** I can quickly implement vault improvements without manual editing

## 🎯 Architectural Role

**This story implements The Editor, an execution agent that works with the Obsidian Gatekeeper.**

The Editor bridges The Curator's suggestions (Story 017) and the Obsidian Gatekeeper (Story 025). It translates high-level curation proposals into concrete file edits in the shadow copy, which you then review and approve.

**Workflow**: User approves curation → The Editor → Shadow copy edits → Obsidian Gatekeeper → User final approval → Vault

## Acceptance Criteria
- [ ] Receives approved curation proposals from The Curator
- [ ] Executes file operations in shadow copy (not vault directly)
- [ ] Supports all improvement types: backlinks, merges, tags, renames, moves
- [ ] Generates clean diffs for user review
- [ ] Handles errors gracefully (file conflicts, missing notes)
- [ ] Integrates with Obsidian Gatekeeper approval workflow
- [ ] Logs all edit operations for audit trail
- [ ] Rollback capability if shadow edit fails
- [ ] Performance: Execute curation in <5 minutes

## Improvement Execution Types

### 1. Backlink Addition

```python
class BacklinkEditor:
    """
    Adds bidirectional links between notes
    """
    def execute(self, proposal: BacklinkProposal):
        """
        Add backlinks in shadow copy
        """
        note_a_path = self.shadow_vault_path / proposal.note_a.path
        note_b_path = self.shadow_vault_path / proposal.note_b.path

        # Read shadow copies
        content_a = self._read_file(note_a_path)
        content_b = self._read_file(note_b_path)

        # Insert backlinks at suggested locations
        updated_a = self._insert_backlink(
            content_a,
            line=proposal.context_a.line_number,
            target=proposal.note_b.title
        )

        updated_b = self._insert_backlink(
            content_b,
            line=proposal.context_b.line_number,
            target=proposal.note_a.title
        )

        # Write to shadow copy
        self._write_file(note_a_path, updated_a)
        self._write_file(note_b_path, updated_b)

        # Log changes
        self._log_edit(
            edit_type='backlink_addition',
            affected_files=[proposal.note_a.path, proposal.note_b.path],
            proposal_id=proposal.id
        )

    def _insert_backlink(self, content: str, line: int, target: str) -> str:
        """
        Insert wiki-link at specific line
        """
        lines = content.split('\n')

        # Find best insertion point in the sentence
        original_line = lines[line]
        updated_line = self._add_link_to_sentence(original_line, target)

        lines[line] = updated_line
        return '\n'.join(lines)

    def _add_link_to_sentence(self, sentence: str, target: str) -> str:
        """
        Intelligently insert link in sentence
        """
        # Strategy: Add at end of sentence before period
        # Or append as new clause

        if sentence.endswith('.'):
            # Insert before period
            return sentence[:-1] + f', see [[{target}]].'
        else:
            # Append
            return sentence + f' [[{target}]]'
```

---

### 2. Note Merging (Redundancy Resolution)

```python
class NoteMerger:
    """
    Merges redundant notes
    """
    def execute(self, proposal: RedundancyProposal):
        """
        Merge secondary note into primary
        """
        primary_path = self.shadow_vault_path / proposal.primary.path
        secondary_path = self.shadow_vault_path / proposal.secondary.path

        # Read both notes
        primary_content = self._read_file(primary_path)
        secondary_content = self._read_file(secondary_path)

        # Extract unique content from secondary
        unique_content = proposal.unique_content

        # Merge strategy
        merged_content = self._merge_content(
            primary_content,
            unique_content,
            merge_strategy='append_section'
        )

        # Update backlinks pointing to secondary → primary
        self._redirect_backlinks(
            from_note=proposal.secondary.title,
            to_note=proposal.primary.title
        )

        # Write merged content to primary
        self._write_file(primary_path, merged_content)

        # Move secondary to archive
        archive_path = self.shadow_vault_path / '_Archive' / proposal.secondary.path.name
        self._move_file(secondary_path, archive_path)

        # Add archive notice to secondary
        self._add_archive_notice(
            archive_path,
            merged_into=proposal.primary.title
        )

        # Log changes
        self._log_edit(
            edit_type='note_merge',
            affected_files=[proposal.primary.path, proposal.secondary.path],
            proposal_id=proposal.id
        )

    def _merge_content(self, primary: str, unique: str, merge_strategy: str) -> str:
        """
        Merge unique content into primary note
        """
        if merge_strategy == 'append_section':
            # Add unique content as new section at end
            return f"{primary}\n\n## Merged Content\n\n{unique}\n"
        elif merge_strategy == 'integrate':
            # Intelligently integrate based on headers
            return self._integrate_by_sections(primary, unique)
        else:
            raise ValueError(f"Unknown merge strategy: {merge_strategy}")

    def _redirect_backlinks(self, from_note: str, to_note: str):
        """
        Update all notes that link to 'from_note' to link to 'to_note'
        """
        # Find all notes with links to from_note
        linking_notes = self._find_notes_linking_to(from_note)

        for note_path in linking_notes:
            content = self._read_file(note_path)

            # Replace [[from_note]] with [[to_note]]
            updated_content = content.replace(
                f'[[{from_note}]]',
                f'[[{to_note}]]'
            )

            self._write_file(note_path, updated_content)

    def _add_archive_notice(self, archive_path: Path, merged_into: str):
        """
        Add notice at top of archived note
        """
        content = self._read_file(archive_path)

        notice = f"""
---
**This note has been merged into [[{merged_into}]]**
Archived: {datetime.now().strftime('%Y-%m-%d')}
---

{content}
"""
        self._write_file(archive_path, notice)
```

---

### 3. Tag Addition

```python
class TagEditor:
    """
    Adds missing tags to notes
    """
    def execute(self, proposal: TagProposal):
        """
        Add tags to note frontmatter or inline
        """
        note_path = self.shadow_vault_path / proposal.note.path

        content = self._read_file(note_path)

        # Strategy: Add to YAML frontmatter if exists, else inline at top
        if self._has_yaml_frontmatter(content):
            updated_content = self._add_tags_to_frontmatter(
                content,
                proposal.suggested_tags
            )
        else:
            updated_content = self._add_tags_inline(
                content,
                proposal.suggested_tags
            )

        self._write_file(note_path, updated_content)

        # Log changes
        self._log_edit(
            edit_type='tag_addition',
            affected_files=[proposal.note.path],
            tags_added=proposal.suggested_tags,
            proposal_id=proposal.id
        )

    def _add_tags_to_frontmatter(self, content: str, tags: List[str]) -> str:
        """
        Add tags to existing YAML frontmatter
        """
        lines = content.split('\n')

        # Find frontmatter bounds
        frontmatter_end = lines.index('---', 1)  # Second ---

        # Check if 'tags:' already exists
        tags_line_idx = None
        for i in range(1, frontmatter_end):
            if lines[i].startswith('tags:'):
                tags_line_idx = i
                break

        if tags_line_idx:
            # Append to existing tags
            existing_tags_line = lines[tags_line_idx]
            existing_tags = self._parse_yaml_tags(existing_tags_line)

            new_tags = existing_tags + [tag for tag in tags if tag not in existing_tags]
            lines[tags_line_idx] = f"tags: [{', '.join(new_tags)}]"
        else:
            # Add new tags line
            lines.insert(frontmatter_end, f"tags: [{', '.join(tags)}]")

        return '\n'.join(lines)

    def _add_tags_inline(self, content: str, tags: List[str]) -> str:
        """
        Add tags at top of note (no frontmatter)
        """
        tag_line = ' '.join(tags)
        return f"{tag_line}\n\n{content}"
```

---

### 4. File Renaming

```python
class FileRenamer:
    """
    Renames files and updates all references
    """
    def execute(self, proposal: NamingProposal):
        """
        Rename files in shadow copy and update backlinks
        """
        for rename in proposal.renames:
            old_path = self.shadow_vault_path / rename.old_name
            new_path = self.shadow_vault_path / rename.new_name

            # Rename file
            old_path.rename(new_path)

            # Update all backlinks across vault
            self._update_backlinks_after_rename(
                old_name=rename.old_title,
                new_name=rename.new_title
            )

        # Log changes
        self._log_edit(
            edit_type='file_rename',
            renames=[(r.old_name, r.new_name) for r in proposal.renames],
            proposal_id=proposal.id
        )

    def _update_backlinks_after_rename(self, old_name: str, new_name: str):
        """
        Update all [[old_name]] → [[new_name]] across vault
        """
        all_notes = self._get_all_notes_in_shadow()

        for note_path in all_notes:
            content = self._read_file(note_path)

            if f'[[{old_name}]]' in content:
                updated_content = content.replace(
                    f'[[{old_name}]]',
                    f'[[{new_name}]]'
                )
                self._write_file(note_path, updated_content)
```

---

### 5. Structural Changes (Move Files)

```python
class FileMover:
    """
    Moves files to appropriate folders
    """
    def execute(self, proposal: StructureProposal):
        """
        Move orphaned or misplaced files
        """
        for move in proposal.moves:
            source_path = self.shadow_vault_path / move.current_path
            dest_path = self.shadow_vault_path / move.target_path

            # Ensure destination folder exists
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Move file
            shutil.move(str(source_path), str(dest_path))

            # No backlink updates needed (path-independent in Obsidian)

        # Log changes
        self._log_edit(
            edit_type='file_move',
            moves=[(m.current_path, m.target_path) for m in proposal.moves],
            proposal_id=proposal.id
        )
```

---

## The Editor Agent Class

```python
class VaultEditorAgent:
    """
    Executes approved curation changes in shadow copy
    Works with Obsidian Gatekeeper for final approval
    """
    def __init__(self, vault_path: str, shadow_vault_path: str, gatekeeper):
        self.vault_path = Path(vault_path)
        self.shadow_vault_path = Path(shadow_vault_path)
        self.gatekeeper = gatekeeper  # Obsidian Gatekeeper (Story 025)

        # Execution strategies
        self.backlink_editor = BacklinkEditor(shadow_vault_path)
        self.note_merger = NoteMerger(shadow_vault_path)
        self.tag_editor = TagEditor(shadow_vault_path)
        self.file_renamer = FileRenamer(shadow_vault_path)
        self.file_mover = FileMover(shadow_vault_path)

        # Audit log
        self.edit_log = []

    def execute_curation(self, proposal: CurationProposal):
        """
        Main entry point: execute approved curation
        """
        log_info(f"Editor: Executing curation {proposal.id} ({proposal.improvement_type})")

        try:
            # Sync vault → shadow (ensure fresh copy)
            self._sync_vault_to_shadow()

            # Execute based on improvement type
            if proposal.improvement_type == 'backlink':
                self.backlink_editor.execute(proposal)
            elif proposal.improvement_type == 'redundancy':
                self.note_merger.execute(proposal)
            elif proposal.improvement_type == 'tag':
                self.tag_editor.execute(proposal)
            elif proposal.improvement_type == 'naming':
                self.file_renamer.execute(proposal)
            elif proposal.improvement_type == 'structure':
                self.file_mover.execute(proposal)
            else:
                raise ValueError(f"Unknown improvement type: {proposal.improvement_type}")

            # Generate diff for user review
            diff = self._generate_diff()

            # Send to Obsidian Gatekeeper for approval
            self.gatekeeper.submit_for_approval(
                edit_source='curator',
                proposal_id=proposal.id,
                diff=diff,
                affected_files=proposal.affected_notes
            )

            log_info(f"Editor: Curation {proposal.id} ready for review")

        except Exception as e:
            log_error(f"Editor: Failed to execute curation {proposal.id}: {e}")
            self._rollback_shadow()
            raise

    def _sync_vault_to_shadow(self):
        """
        Ensure shadow copy is up-to-date with vault
        """
        # Use rsync or similar to sync vault → shadow
        # This ensures we're working with latest vault state
        rsync(
            source=self.vault_path,
            dest=self.shadow_vault_path,
            exclude=['.obsidian/', '.git/']
        )

    def _generate_diff(self):
        """
        Generate diff between vault and shadow
        """
        # Use git diff or difflib
        diff_output = subprocess.run(
            ['diff', '-ru', str(self.vault_path), str(self.shadow_vault_path)],
            capture_output=True,
            text=True
        )

        return diff_output.stdout

    def _rollback_shadow(self):
        """
        Rollback shadow copy if edit failed
        """
        # Re-sync vault → shadow (discard shadow changes)
        self._sync_vault_to_shadow()
        log_info("Editor: Shadow copy rolled back")

    def _log_edit(self, edit_type: str, **kwargs):
        """
        Log edit operation for audit trail
        """
        self.edit_log.append({
            'timestamp': datetime.now(),
            'edit_type': edit_type,
            **kwargs
        })
```

---

## Integration with Obsidian Gatekeeper

```python
# In Obsidian Gatekeeper (Story 025)

def submit_for_approval(self, edit_source: str, proposal_id: str, diff: str, affected_files: List[str]):
    """
    Submit shadow edits for user approval
    Extended to support Curator/Editor workflow
    """
    approval_id = str(uuid4())

    # Store pending approval
    self.pending_approvals[approval_id] = {
        'source': edit_source,  # 'curator', 'janitor', 'tagger', etc.
        'proposal_id': proposal_id,
        'diff': diff,
        'affected_files': affected_files,
        'submitted_at': datetime.now()
    }

    # Send to user via The Liaison
    message = f"""
📝 **Shadow Copy Ready for Review**

**Source**: {edit_source.title()}
**Files affected**: {len(affected_files)}

**Changes preview**:
```diff
{diff[:500]}...
```

**Actions**:
`/review_shadow {approval_id}` - See full diff
`/approve_shadow {approval_id}` - Apply to vault
`/reject_shadow {approval_id}` - Discard changes
"""

    self.messenger.send_message(message)
```

---

## Telegram Commands (via The Liaison)

```python
# In Hermes bot

@hermes_bot.command("review_shadow")
def cmd_review_shadow(message, approval_id: str):
    """
    View full diff of shadow copy changes
    """
    approval = gatekeeper.get_approval(approval_id)

    if not approval:
        return "Shadow approval not found."

    # Send full diff (may need pagination for large diffs)
    diff_lines = approval['diff'].split('\n')

    if len(diff_lines) > 50:
        # Paginate
        send_paginated_diff(message.chat.id, diff_lines, approval_id)
    else:
        bot.send_message(
            chat_id=message.chat.id,
            text=f"```diff\n{approval['diff']}\n```",
            parse_mode='Markdown'
        )

    bot.send_message(
        chat_id=message.chat.id,
        text=f"""
**Actions**:
`/approve_shadow {approval_id}` - Apply these changes
`/reject_shadow {approval_id}` - Discard
"""
    )

@hermes_bot.command("approve_shadow")
def cmd_approve_shadow(message, approval_id: str):
    """
    Apply shadow changes to vault
    """
    approval = gatekeeper.get_approval(approval_id)

    if not approval:
        return "Shadow approval not found."

    # Apply shadow → vault
    gatekeeper.apply_shadow_to_vault()

    # Mark curation as completed
    if approval['source'] == 'curator':
        curator.mark_completed(approval['proposal_id'])

    bot.send_message(
        chat_id=message.chat.id,
        text=f"""
✅ Shadow changes applied to vault

**Files updated**: {len(approval['affected_files'])}

Your vault has been updated with the approved changes.
"""
    )

@hermes_bot.command("reject_shadow")
def cmd_reject_shadow(message, approval_id: str):
    """
    Discard shadow changes
    """
    approval = gatekeeper.get_approval(approval_id)

    if not approval:
        return "Shadow approval not found."

    # Discard shadow changes (rollback)
    editor.rollback_shadow()

    # Mark curation as rejected
    if approval['source'] == 'curator':
        curator.mark_rejected(approval['proposal_id'])

    del gatekeeper.pending_approvals[approval_id]

    bot.send_message(
        chat_id=message.chat.id,
        text="✅ Shadow changes discarded. Your vault remains unchanged."
    )

@hermes_bot.command("curation_status")
def cmd_curation_status(message, curation_id: str):
    """
    Check status of curation execution
    """
    status = editor.get_curation_status(curation_id)

    if not status:
        return "Curation not found."

    status_message = f"""
📊 **Curation Status**

**ID**: {curation_id}
**Type**: {status.improvement_type}
**Status**: {status.current_status}

**Timeline**:
- Detected: {format_datetime(status.detected_at)}
- Approved: {format_datetime(status.approved_at) if status.approved_at else 'N/A'}
- Executed: {format_datetime(status.executed_at) if status.executed_at else 'Pending'}
- Applied to vault: {format_datetime(status.applied_at) if status.applied_at else 'Not yet'}

**Files affected**: {len(status.affected_files)}
"""

    bot.send_message(
        chat_id=message.chat.id,
        text=status_message,
        parse_mode='Markdown'
    )
```

---

## Error Handling

```python
class EditorErrorHandler:
    """
    Handle errors during curation execution
    """
    def handle_file_not_found(self, proposal):
        """
        Note was deleted or moved since curation was proposed
        """
        log_warn(f"Curation {proposal.id}: File not found, marking as stale")

        curator.mark_stale(proposal.id)

        messenger.send_message(f"""
⚠️ **Curation Execution Failed**

The note referenced in curation proposal no longer exists.
This proposal has been marked as stale and won't be retried.

Curation ID: {proposal.id}
""")

    def handle_conflict(self, proposal):
        """
        Vault changed in a way that conflicts with curation
        """
        log_warn(f"Curation {proposal.id}: Conflict detected")

        messenger.send_message(f"""
⚠️ **Curation Conflict Detected**

Your vault has changed since this curation was proposed.
The proposed changes may no longer be valid.

**Options**:
1. `/retry_curation {proposal.id}` - Re-analyze and propose updated changes
2. `/cancel_curation {proposal.id}` - Discard this curation

Curation ID: {proposal.id}
""")
```

---

## Audit Log

```sql
-- The Editor maintains audit log in SQLite

CREATE TABLE edit_operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    curation_id TEXT NOT NULL,
    improvement_type TEXT NOT NULL,
    edit_type TEXT NOT NULL,  -- backlink, merge, tag, rename, move
    affected_files TEXT NOT NULL,  -- JSON array
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    applied_to_vault_at TIMESTAMP,  -- NULL until approved by user
    executed_by TEXT DEFAULT 'editor_agent'
);

CREATE INDEX idx_edit_curation ON edit_operations(curation_id);
CREATE INDEX idx_edit_timestamp ON edit_operations(executed_at);
```

---

## Performance Optimizations

- **Incremental sync**: Only sync changed files to shadow (not full vault)
- **Batch operations**: Group multiple tag additions into single write
- **Diff caching**: Cache diff output for re-review
- **Parallel execution**: Execute independent curations in parallel

---

## Dependencies
- Obsidian Gatekeeper (Story 025) - final approval workflow
- The Curator (Story 017) - source of curation proposals
- The Liaison (Hermes) - user communication
- Shadow copy infrastructure from Story 025

## Affected Components
- **The Gates**: Obsidian Gatekeeper (extended for curator workflow)
- **Hermes**: The Liaison (new commands for curation review)
- **Supporting Agent**: The Editor (new execution agent)

## Priority
**Low-Medium** - Dependent on Story 017 (Phase 5)

## Estimate
10 story points (8-12 days) - complex file operations and error handling

## Linear Labels
`phase-5`, `vault-curation`, `editor`, `shadow-copy`, `file-operations`

## Related Stories
- Story 025: Obsidian Gatekeeper (approval workflow foundation)
- Story 017: The Curator (provides curation proposals)

## Future Enhancements
- Preview mode: Show before/after in Obsidian preview
- Partial application: Apply only some changes from a curation
- Undo: Revert applied curation
- Dry-run mode: Simulate curation without touching shadow copy
