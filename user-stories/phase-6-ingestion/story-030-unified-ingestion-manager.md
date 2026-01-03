# Story 030: Unified Ingestion Manager

**As a** Mnemosyne user
**I want** a single command that automatically ingests all new content (vault, PDFs, emails)
**So that** I don't need to manually run separate ingestion scripts or remember what's been processed

## 🎯 Problem Statement

**Current state** (fragmented):
```bash
# User must run multiple commands manually
docker compose -f docker-compose.test.yml up -d
.venv/bin/python -m mnemosyne.cli.ingest once --vault-path test_data/fake_vault
.venv/bin/python -m mnemosyne.cli.ingest watch --vault-path test_data/fake_vault &
python scripts/ingest_pdfs.py
python scripts/ingest_emails.py
```

**Problems**:
- ❌ Manual coordination required
- ❌ Vault has watch mode, PDF/email don't
- ❌ No unified "what changed?" detection
- ❌ Docker services must be manually managed
- ❌ Easy to forget to ingest some sources

**Target state** (unified):
```bash
# Single command handles everything
mnemosyne ingest watch --auto-start-services

# Or one-time sync
mnemosyne ingest sync --sources vault,pdf,email
```

## Acceptance Criteria

### Phase 1: Unified Ingestion State Tracking
- [ ] **Single ingestion state database** (SQLite)
  - Tracks last ingestion timestamp per source type
  - Tracks file hashes/modification times
  - Identifies new/modified/deleted files
  - Prevents duplicate processing

- [ ] **Source detection**
  - Auto-discover vault path (look for .obsidian folder)
  - Auto-discover PDF directories (configurable paths)
  - Auto-discover email sources (IMAP, TSV files, etc.)

### Phase 2: Orchestration Engine
- [ ] **IngestionOrchestrator class**
  - Coordinates vault + PDF + email ingestion
  - Runs in configurable order (vault first, then PDFs, then emails)
  - Handles failures gracefully (continue with other sources)
  - Collects statistics across all sources

- [ ] **Incremental ingestion**
  - Only process files changed since last run
  - Use modification timestamps + file hashes
  - Delete embeddings for removed files
  - Update embeddings for modified files

### Phase 3: Service Management
- [ ] **Auto-start Docker services if not running**
  - Check if Weaviate/Ollama are reachable
  - Start `docker-compose.test.yml` automatically if needed
  - Wait for services to be healthy before ingestion
  - Option: `--no-auto-start` to fail if services down

- [ ] **Graceful shutdown**
  - Stop watching when user presses Ctrl+C
  - Option: `--stop-services` to shut down Docker after ingestion

### Phase 4: Watch Mode for All Sources
- [ ] **Vault watcher** (existing, keep it)
- [ ] **PDF directory watcher**
  - Monitor PDF directories with `watchdog`
  - Trigger ingestion when new PDFs added
  - Re-process if PDF modified

- [ ] **Email watcher** (optional)
  - Poll IMAP folders every N minutes
  - Watch TSV files for changes
  - Configurable polling interval

### Phase 5: CLI Integration
- [ ] **`mnemosyne ingest sync`** - One-time sync
  ```bash
  mnemosyne ingest sync \
    --sources vault,pdf,email \
    --vault-path ~/Documents/Obsidian \
    --pdf-paths ~/Downloads/Papers,~/Documents/Research \
    --email-source imap://user@gmail.com
  ```

- [ ] **`mnemosyne ingest watch`** - Continuous monitoring
  ```bash
  mnemosyne ingest watch \
    --auto-start-services \
    --interval 300  # Check for changes every 5 minutes
  ```

- [ ] **`mnemosyne ingest status`** - Show ingestion state
  ```bash
  $ mnemosyne ingest status

  Last Ingestion: 2026-01-02 14:30:00

  Sources:
    Vault (~/Documents/Obsidian):
      Files: 127 (3 new, 2 modified since last run)
      Last sync: 5 minutes ago

    PDFs (~/Downloads/Papers):
      Files: 45 (1 new since last run)
      Last sync: 1 hour ago

    Emails (IMAP):
      Messages: 1,234 (0 new since last run)
      Last sync: 30 minutes ago
  ```

## Implementation Design

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│              Unified Ingestion Manager                   │
└─────────────────────────────────────────────────────────┘

┌──────────────────────┐
│  CLI Entry Point     │
│  mnemosyne ingest    │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────────────────────────────────────┐
│         IngestionOrchestrator                         │
│  - Coordinates all sources                           │
│  - Manages service lifecycle                         │
│  - Tracks ingestion state                            │
└──────────┬───────────────────────────────────────────┘
           │
           ├──────────────┬──────────────┬─────────────┐
           ▼              ▼              ▼             ▼
    ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
    │  Vault   │  │   PDF    │  │  Email   │  │ Services │
    │ Ingestor │  │ Ingestor │  │ Ingestor │  │ Manager  │
    └──────────┘  └──────────┘  └──────────┘  └──────────┘
           │              │              │             │
           └──────────────┴──────────────┴─────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  Ingestion State DB   │
              │  (SQLite)             │
              │  - source_files       │
              │  - ingestion_runs     │
              │  - file_hashes        │
              └───────────────────────┘
```

### Database Schema

```sql
-- Track ingestion runs
CREATE TABLE ingestion_runs (
    id INTEGER PRIMARY KEY,
    source_type TEXT NOT NULL,  -- 'vault', 'pdf', 'email'
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    status TEXT NOT NULL,  -- 'running', 'completed', 'failed'
    files_processed INTEGER DEFAULT 0,
    chunks_created INTEGER DEFAULT 0,
    errors TEXT,
    config_json TEXT  -- Store configuration used
);

-- Track individual files
CREATE TABLE source_files (
    id INTEGER PRIMARY KEY,
    source_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_hash TEXT NOT NULL,  -- SHA256 of content
    last_modified TIMESTAMP NOT NULL,
    last_ingested_at TIMESTAMP,
    chunk_count INTEGER DEFAULT 0,
    weaviate_ids TEXT,  -- JSON array of UUID
    status TEXT NOT NULL,  -- 'pending', 'processed', 'deleted'
    UNIQUE(source_type, file_path)
);

-- Index for quick lookups
CREATE INDEX idx_source_files_status ON source_files(source_type, status);
CREATE INDEX idx_source_files_modified ON source_files(last_modified);
```

### Code Structure

```python
class IngestionOrchestrator:
    """Coordinates ingestion across all sources."""

    def __init__(self, config: IngestionConfig, state_db: StateDatabase):
        self.config = config
        self.state = state_db
        self.services = ServiceManager()
        self.ingestors = {
            'vault': VaultIngestor(),
            'pdf': PDFIngestor(),
            'email': EmailIngestor(),
        }

    def sync(self, sources: list[str] = None) -> IngestionReport:
        """One-time sync of specified sources."""
        # 1. Ensure services are running
        self.services.ensure_running(auto_start=self.config.auto_start_services)

        # 2. Detect changed files
        changes = self._detect_changes(sources or ['vault', 'pdf', 'email'])

        # 3. Process each source in order
        report = IngestionReport()
        for source_type in sources:
            try:
                result = self.ingestors[source_type].ingest_incremental(changes[source_type])
                report.add_source_result(source_type, result)
            except Exception as e:
                report.add_error(source_type, str(e))

        # 4. Update state database
        self.state.record_run(report)

        return report

    def watch(self, sources: list[str] = None, interval: int = 300):
        """Continuous monitoring with periodic syncs."""
        while True:
            try:
                report = self.sync(sources)
                log.info(f"Ingestion complete: {report.summary()}")
                time.sleep(interval)
            except KeyboardInterrupt:
                log.info("Stopping watcher...")
                break

    def _detect_changes(self, sources: list[str]) -> dict[str, list[FileChange]]:
        """Detect new/modified/deleted files for each source."""
        changes = {}
        for source_type in sources:
            changes[source_type] = self._scan_source(source_type)
        return changes

    def _scan_source(self, source_type: str) -> list[FileChange]:
        """Scan a source for changes since last ingestion."""
        # Get current files
        current_files = self._list_files(source_type)

        # Get previous state
        previous_files = self.state.get_files(source_type)

        # Compute diff
        changes = []
        for file_path, file_info in current_files.items():
            prev = previous_files.get(file_path)

            if prev is None:
                # New file
                changes.append(FileChange('new', file_path, file_info))
            elif prev.hash != file_info.hash:
                # Modified file
                changes.append(FileChange('modified', file_path, file_info))

        # Check for deleted files
        for file_path in previous_files:
            if file_path not in current_files:
                changes.append(FileChange('deleted', file_path))

        return changes


class ServiceManager:
    """Manages Docker services lifecycle."""

    def ensure_running(self, auto_start: bool = True):
        """Ensure Weaviate and Ollama are running."""
        if self._is_healthy():
            return

        if not auto_start:
            raise RuntimeError("Services not running (use --auto-start-services)")

        # Start services
        subprocess.run(["docker", "compose", "-f", "docker-compose.test.yml", "up", "-d"])

        # Wait for health
        self._wait_for_health(timeout=60)

    def _is_healthy(self) -> bool:
        """Check if services are reachable."""
        try:
            # Check Weaviate
            resp = requests.get(f"{self.weaviate_url}/v1/.well-known/ready", timeout=2)
            if resp.status_code != 200:
                return False

            # Check Ollama
            resp = requests.get(f"{self.ollama_url}/api/tags", timeout=2)
            if resp.status_code != 200:
                return False

            return True
        except requests.RequestException:
            return False


class VaultIngestor:
    """Handles Obsidian vault ingestion."""

    def ingest_incremental(self, changes: list[FileChange]) -> SourceResult:
        """Ingest only changed files."""
        result = SourceResult('vault')

        for change in changes:
            if change.type == 'deleted':
                self._delete_chunks(change.file_path)
                result.deleted += 1
            elif change.type in ['new', 'modified']:
                self._ingest_file(change.file_path)
                result.processed += 1

        return result
```

### CLI Implementation

```python
# mnemosyne/cli/ingest.py

@click.group()
def ingest():
    """Manage content ingestion from all sources."""
    pass


@ingest.command()
@click.option('--sources', default='vault,pdf,email', help='Comma-separated list')
@click.option('--vault-path', envvar='OBSIDIAN_VAULT_PATH')
@click.option('--pdf-paths', envvar='PDF_PATHS')
@click.option('--auto-start-services/--no-auto-start', default=True)
def sync(sources, vault_path, pdf_paths, auto_start_services):
    """One-time sync of all sources."""
    config = IngestionConfig(
        vault_path=vault_path,
        pdf_paths=pdf_paths.split(',') if pdf_paths else [],
        auto_start_services=auto_start_services,
    )

    orchestrator = IngestionOrchestrator(config, state_db_path='~/.mnemosyne/ingestion.db')
    report = orchestrator.sync(sources=sources.split(','))

    click.echo(report.format_summary())


@ingest.command()
@click.option('--sources', default='vault,pdf,email')
@click.option('--interval', default=300, help='Seconds between checks')
@click.option('--auto-start-services/--no-auto-start', default=True)
def watch(sources, interval, auto_start_services):
    """Watch sources and sync on changes."""
    config = IngestionConfig(auto_start_services=auto_start_services)
    orchestrator = IngestionOrchestrator(config, state_db_path='~/.mnemosyne/ingestion.db')

    click.echo(f"Watching {sources} (checking every {interval}s)")
    orchestrator.watch(sources=sources.split(','), interval=interval)


@ingest.command()
def status():
    """Show ingestion state and statistics."""
    state = StateDatabase('~/.mnemosyne/ingestion.db')

    click.echo("Last Ingestion Runs:")
    for run in state.get_recent_runs(limit=5):
        click.echo(f"  {run.source_type}: {run.completed_at} ({run.files_processed} files)")

    click.echo("\nSource Status:")
    for source_type in ['vault', 'pdf', 'email']:
        stats = state.get_source_stats(source_type)
        click.echo(f"  {source_type}: {stats.total_files} files ({stats.pending} pending)")
```

## Migration Path

**Phase 1**: Basic orchestration
- Create `IngestionOrchestrator` class
- Implement state database
- Single `sync` command

**Phase 2**: Service management
- Add `ServiceManager`
- Auto-start Docker services
- Health checking

**Phase 3**: Watch mode
- Extend to all sources
- File change detection
- Periodic sync

**Phase 4**: Polish
- Better error handling
- Progress bars
- Notification system

## Benefits

1. **User Experience**
   - Single command instead of 3-4
   - No manual Docker management
   - Clear visibility into what's being processed

2. **Reliability**
   - Deduplication prevents re-processing
   - Failed sources don't block others
   - State tracking prevents data loss

3. **Performance**
   - Only process changed files
   - Parallel ingestion possible
   - Reduced redundant work

4. **Maintainability**
   - One place to manage ingestion logic
   - Easier to add new sources
   - Better testing (mock file changes)

## Future Enhancements

- **Cloud storage sources**: Google Drive, Dropbox, OneDrive
- **Web scraping**: Bookmarks, read-later services
- **Real-time sync**: WebSocket/webhook triggers instead of polling
- **Parallel processing**: Ingest multiple sources concurrently
- **Smart scheduling**: Ingest PDFs during low-activity periods
- **Conflict resolution**: Handle files modified in multiple places

## Example Usage

```bash
# First time setup - discovers sources and ingests everything
$ mnemosyne ingest sync --auto-start-services
Starting Docker services...
Services healthy ✓

Scanning sources...
  Vault: 127 files (127 new)
  PDFs: 45 files (45 new)
  Emails: 1,234 messages (1,234 new)

Ingesting vault... ████████████████████ 127/127 files
Ingesting PDFs...  ████████████████████  45/45 files
Ingesting emails... ████████████████████ 1234/1234 messages

Summary:
  Total files: 1,406
  Total chunks: 2,341
  Duration: 3m 24s

# Subsequent runs - only new/changed files
$ mnemosyne ingest sync
Services healthy ✓

Scanning sources...
  Vault: 3 new, 2 modified
  PDFs: 1 new
  Emails: 0 new

Ingesting vault... ████████████████████ 5/5 files
Ingesting PDFs...  ████████████████████ 1/1 files

Summary:
  Total files: 6
  Total chunks: 23
  Duration: 14s

# Continuous monitoring
$ mnemosyne ingest watch --interval 300
Watching vault,pdf,email (checking every 300s)
[14:30:00] Sync complete: 0 new files
[14:35:00] Sync complete: 1 new file (vault)
[14:40:00] Sync complete: 0 new files
^C Stopping watcher...
```

## Testing Strategy

- **Unit tests**: State database, change detection, file hashing
- **Integration tests**: Orchestrator with mock ingestors
- **E2E tests**: Full pipeline with test fixtures
- **Performance tests**: Large vault ingestion (1000+ files)

## Success Metrics

- **Setup time**: From 5+ manual commands → 1 command
- **Duplicate processing**: 0% (state tracking prevents)
- **User errors**: Reduced by 80% (no manual coordination)
- **Time to first ingest**: < 1 minute (auto-start services)
