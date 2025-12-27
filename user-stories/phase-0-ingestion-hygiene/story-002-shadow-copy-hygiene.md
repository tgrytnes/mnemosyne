# Story 002: Shadow Copy & Hygiene Layer (Obsidian Gatekeeper)

**As a** user
**I want** all automated edits to happen in a shadow copy of my vault
**So that** my canonical Obsidian vault remains safe from automated changes until I approve them

## 🎯 Architectural Role

**This story implements the Obsidian Gatekeeper (part of The Gates approval layer).**

The Obsidian Gatekeeper ensures that no automated agent can directly modify your vault. All edits happen in a shadow copy and require your explicit approval before being applied to the canonical vault.

## Acceptance Criteria
- [ ] Shadow vault directory created (mirroring source vault structure)
- [ ] Janitor service copies files from source → shadow on file changes
- [ ] Shadow copy receives all automated tags (#needs_review, #relevant_lessons_learned)
- [ ] Shadow copy undergoes text normalization (whitespace, formatting)
- [ ] Gatekeeper approval required before syncing shadow → source
- [ ] User reviews shadow changes in dedicated folder
- [ ] Approved changes synced back to canonical vault
- [ ] Rejected changes discarded from shadow
- [ ] Audit log of all automated edits and approvals

## Technical Notes

### Architecture (Adapted from Project Crystal)

```python
class Janitor:
    """
    Based on project_crystal/app/janitor.py
    Shadow copy manager for safe hygiene
    """
    def __init__(self, source_vault: str, shadow_vault: str):
        self.source_vault = source_vault
        self.shadow_vault = shadow_vault

    def sync_to_shadow(self):
        """
        Copy source → shadow with text normalization
        """
        for file_path in glob(f"{self.source_vault}/**/*.md", recursive=True):
            relative_path = os.path.relpath(file_path, self.source_vault)
            shadow_path = os.path.join(self.shadow_vault, relative_path)

            # Create directories if needed
            os.makedirs(os.path.dirname(shadow_path), exist_ok=True)

            # Copy and clean
            cleaned_content = self.normalize_file(file_path)
            write_file(shadow_path, cleaned_content)

    def normalize_file(self, file_path: str) -> str:
        """
        Text normalization without semantic changes
        """
        content = read_file(file_path)

        # Normalize line endings
        content = content.replace('\r\n', '\n')

        # Normalize whitespace (but preserve intentional spacing)
        lines = content.split('\n')
        normalized_lines = []

        for line in lines:
            # Remove trailing whitespace
            line = line.rstrip()

            # Normalize multiple spaces to single (except in code blocks)
            if not line.startswith('    ') and not line.startswith('\t'):
                line = re.sub(r' {2,}', ' ', line)

            normalized_lines.append(line)

        # Remove multiple consecutive blank lines (max 2)
        content = '\n'.join(normalized_lines)
        content = re.sub(r'\n{3,}', '\n\n', content)

        return content
```

### Automated Tagging (Tagger)

```python
class Tagger:
    """
    Apply semantic tags to shadow copy using Ollama
    """
    def __init__(self, ollama_client):
        self.ollama = ollama_client

    def tag_file(self, shadow_file_path: str) -> List[str]:
        """
        Analyze file and return suggested tags
        """
        content = read_file(shadow_file_path)

        # Extract first 1000 chars for analysis
        sample = content[:1000]

        prompt = f"""
Analyze this Obsidian note and suggest relevant tags from this list:

Tags:
- #needs_review: Note has incomplete thoughts, TODOs, or placeholders
- #relevant_lessons_learned: Contains failure analysis or lessons
- #project_candidate: Describes a potential project
- #reference_material: Evergreen reference content
- #daily_note: Daily journal entry
- #meeting_notes: Meeting or conversation notes

Note content:
{sample}

Return ONLY the tags that apply (one per line, with #).
"""

        response = self.ollama.generate(
            model="qwen3:0.6b",
            prompt=prompt,
            options={"temperature": 0.2}
        )

        # Parse tags from response
        tags = [
            line.strip()
            for line in response['response'].split('\n')
            if line.strip().startswith('#')
        ]

        return tags

    def apply_tags_to_file(self, shadow_file_path: str, tags: List[str]):
        """
        Append tags to YAML frontmatter in shadow copy
        """
        content = read_file(shadow_file_path)

        # Parse existing frontmatter
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                frontmatter = parts[1]
                body = parts[2]
            else:
                frontmatter = ""
                body = content
        else:
            frontmatter = ""
            body = content

        # Add tags to frontmatter
        if 'tags:' in frontmatter:
            # Append to existing tags
            for tag in tags:
                if tag not in frontmatter:
                    frontmatter += f"  - {tag}\n"
        else:
            # Create new tags section
            tag_lines = '\n'.join([f"  - {tag}" for tag in tags])
            frontmatter += f"\ntags:\n{tag_lines}\n"

        # Reconstruct file
        new_content = f"---{frontmatter}---{body}"
        write_file(shadow_file_path, new_content)

        # Log for gatekeeper approval
        log_automated_edit(shadow_file_path, tags)
```

### Gatekeeper Approval Workflow

```python
class ObsidianGatekeeper:
    """
    Controls write-back from shadow → source vault
    """
    def __init__(self, source_vault: str, shadow_vault: str):
        self.source_vault = source_vault
        self.shadow_vault = shadow_vault
        self.pending_approvals = []

    def request_approval(self, shadow_file: str, changes: Dict):
        """
        Queue shadow file for user review
        """
        approval_request = ApprovalRequest(
            shadow_file=shadow_file,
            source_file=self.get_source_path(shadow_file),
            changes=changes,
            requested_at=datetime.now()
        )
        self.pending_approvals.append(approval_request)

        # Notify via Hermes
        send_telegram_notification(
            f"🔍 Review request: {os.path.basename(shadow_file)}\n"
            f"Changes: {', '.join(changes['tags_added'])}\n"
            f"Approve with /approve {approval_request.id}"
        )

    def approve_changes(self, approval_id: str):
        """
        User approved: sync shadow → source
        """
        request = self.get_approval_request(approval_id)

        if not request:
            raise ValueError(f"Approval request {approval_id} not found")

        # Copy shadow file to source
        shutil.copy2(request.shadow_file, request.source_file)

        # Log approval
        log_approval(request, approved=True)

        # Remove from pending
        self.pending_approvals.remove(request)

    def reject_changes(self, approval_id: str):
        """
        User rejected: discard shadow changes
        """
        request = self.get_approval_request(approval_id)

        # Revert shadow to match source
        shutil.copy2(request.source_file, request.shadow_file)

        # Log rejection
        log_approval(request, approved=False)

        # Remove from pending
        self.pending_approvals.remove(request)
```

### Diff Viewer for Review

```python
def generate_diff(source_file: str, shadow_file: str) -> str:
    """
    Generate human-readable diff for Telegram
    """
    import difflib

    source_content = read_file(source_file).splitlines()
    shadow_content = read_file(shadow_file).splitlines()

    diff = difflib.unified_diff(
        source_content,
        shadow_content,
        fromfile='Original',
        tofile='Shadow (Proposed)',
        lineterm=''
    )

    diff_text = '\n'.join(diff)

    # Truncate if too long for Telegram
    if len(diff_text) > 2000:
        diff_text = diff_text[:2000] + "\n... (truncated)"

    return f"```diff\n{diff_text}\n```"
```

### Integration with Hermes (Telegram)

```python
# In Hermes bot

@hermes_bot.command("review_pending")
def cmd_review_pending(message):
    """
    Show pending approval requests
    """
    pending = gatekeeper.get_pending_approvals()

    if not pending:
        return "No pending reviews."

    response = "📋 **Pending Reviews**\n\n"

    for request in pending:
        response += f"""
{request.id}. {os.path.basename(request.shadow_file)}
   Changes: {', '.join(request.changes['tags_added'])}
   Requested: {format_time_ago(request.requested_at)}
   `/diff {request.id}` | `/approve {request.id}` | `/reject {request.id}`

"""

    bot.send_message(chat_id=message.chat.id, text=response)

@hermes_bot.command("diff")
def cmd_diff(message, approval_id: str):
    """
    Show diff for approval request
    """
    request = gatekeeper.get_approval_request(approval_id)
    diff = generate_diff(request.source_file, request.shadow_file)

    bot.send_message(
        chat_id=message.chat.id,
        text=diff,
        parse_mode='Markdown'
    )

@hermes_bot.command("approve")
def cmd_approve(message, approval_id: str):
    """
    Approve shadow changes
    """
    gatekeeper.approve_changes(approval_id)
    bot.send_message(
        chat_id=message.chat.id,
        text=f"✅ Approved changes for request {approval_id}"
    )

@hermes_bot.command("reject")
def cmd_reject(message, approval_id: str):
    """
    Reject shadow changes
    """
    gatekeeper.reject_changes(approval_id)
    bot.send_message(
        chat_id=message.chat.id,
        text=f"❌ Rejected changes for request {approval_id}"
    )
```

### Audit Log

```python
class AuditLog:
    """
    Track all automated edits and approvals
    """
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        self.create_table()

    def create_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                action TEXT NOT NULL,  -- 'tag_applied', 'approved', 'rejected'
                file_path TEXT NOT NULL,
                changes JSON,
                user_decision TEXT  -- 'approved', 'rejected', NULL
            )
        """)

    def log_automated_edit(self, file_path: str, tags: List[str]):
        self.conn.execute(
            "INSERT INTO audit_log (action, file_path, changes) VALUES (?, ?, ?)",
            ('tag_applied', file_path, json.dumps({'tags': tags}))
        )

    def log_approval(self, request: ApprovalRequest, approved: bool):
        self.conn.execute(
            "INSERT INTO audit_log (action, file_path, changes, user_decision) VALUES (?, ?, ?, ?)",
            (
                'user_review',
                request.source_file,
                json.dumps(request.changes),
                'approved' if approved else 'rejected'
            )
        )
```

### File Watching for Shadow Sync

```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class VaultSyncHandler(FileSystemEventHandler):
    def __init__(self, janitor: Janitor, tagger: Tagger):
        self.janitor = janitor
        self.tagger = tagger

    def on_modified(self, event):
        if event.src_path.endswith('.md'):
            # 1. Copy to shadow
            self.janitor.sync_file_to_shadow(event.src_path)

            # 2. Tag shadow copy
            shadow_path = self.janitor.get_shadow_path(event.src_path)
            tags = self.tagger.tag_file(shadow_path)

            if tags:
                self.tagger.apply_tags_to_file(shadow_path, tags)

                # 3. Request approval
                gatekeeper.request_approval(shadow_path, {'tags_added': tags})
```

### Dependencies
- project_crystal/app/janitor.py (shadow copy logic)
- Ollama for semantic tagging (qwen3:0.6b)
- Watchdog for file system monitoring
- Hermes (Telegram bot) for approval workflow
- SQLite for audit log

## Affected Components
- **Aletheia**: Janitor and Tagger implementation
- **Hermes**: Approval commands (/review_pending, /approve, /reject, /diff)
- **Obsidian Vault**: Source vault (read-only), shadow vault (write)

## Priority
**High** - Critical safety feature for automated vault edits

## Estimate
13 story points (8-10 days)

## Linear Labels
`phase-0`, `hygiene`, `safety`, `aletheia`, `hermes`

## Related Stories
- Story 000: Obsidian Vault Ingestion (reads from shadow copy)
- Story 009: Actionable Synthesis (writes to shadow, requires approval)
- Story 012: Proactive Insight Notifications (approval via Telegram)

## References
- Implementation: `project_crystal/app/janitor.py`
- Crystal philosophy: "Safe Hygiene: Shadow copies absorb all automated edits"
- Gatekeeper concept: "Binary Sovereignty: Yes/No prompts only"
