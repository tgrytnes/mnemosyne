# CR-000-001: Centralized File Watcher Hub (Change Request)

**Change Request Type**: Architectural Improvement
**Parent Story**: Story 000: Obsidian Vault Ingestion
**Related Stories**: Story 016 (Project Manager), Story 025 (Shadow Copy Hygiene)
**Requested By**: Multiple file watching needs across Stories 000, 016, and 025
**Feature Branch**: TBD (will be merged into relevant feature branches)

---

## Summary

Create a centralized file watcher hub to coordinate multiple file system event handlers, replacing duplicate watchdog Observers with a single, priority-ordered event dispatch system.

---

## Business Justification

### Problem Statement

Currently, Mnemosyne has (or will have) **multiple independent file watchers** monitoring the same Obsidian vault:

1. **VaultWatcher** (Story 000) - Watches vault for Weaviate ingestion
2. **Shadow Copy Sync** (Story 025) - Watches source vault to sync → shadow copy
3. **Project Sync** (Story 016) - Watches Obsidian Projects folder ↔ PostgreSQL
4. **Auto-tagging** (Story 025) - Watches shadow copy for semantic tagging
5. **Weaviate Re-ingestion** - Re-ingests after tagging

Each of these creates its own `watchdog.Observer` instance, leading to:
- **Resource waste**: Multiple OS file handles and threads
- **Event storms**: Same file change triggers 5+ separate handlers
- **Race conditions**: Handlers modifying files trigger other handlers
- **No coordination**: Handler execution order is random/undefined
- **Testing complexity**: Each watcher must be tested in isolation
- **Maintenance burden**: Duplicate debouncing, filtering, error handling

### Why This Change is Needed

**Current Architecture** (Problems):
```
Source Vault
    ↓
Observer #1 (VaultWatcher) → Weaviate Ingestion
Observer #2 (ShadowSync) → Shadow Copy → Observer #3 (Tagger)
Observer #4 (ProjectSync) → PostgreSQL
Observer #5 (ReIngestion) → Weaviate Update
```

**Proposed Architecture** (Benefits):
```
Source Vault
    ↓
FileWatcherHub (Single Observer)
    ↓
Priority-Ordered Handler Pipeline:
    1. ShadowCopyHandler (priority: 10) → Creates shadow copy
    2. ProjectSyncHandler (priority: 50) → Syncs to PostgreSQL
    3. AutoTaggingHandler (priority: 150) → Tags shadow copy
    4. WeaviateHandler (priority: 250) → Ingests to vector DB
```

**Key Improvements**:
1. **Single Observer** - One watchdog instance instead of 5
2. **Ordered Execution** - Shadow copy created before tagging happens before ingestion
3. **Fault Isolation** - Handler errors don't break other handlers
4. **Testability** - Each handler unit-testable independently
5. **Clear Dependencies** - Priority system makes execution order explicit
6. **Performance** - Reduced file system polling, shared debouncing

### Impact if Not Implemented

**Immediate Impacts**:
- Story 016 will create 3rd independent watcher (Projects sync)
- Story 025 will create 4th and 5th watchers (shadow sync + tagging)
- Race conditions likely when Project Sync modifies markdown → triggers VaultWatcher → re-ingestion → infinite loop

**Long-term Impacts**:
- Difficult to add new file-based features (each needs new watcher)
- Hard to debug file watching issues (which observer triggered what?)
- Poor resource utilization on low-power devices (Raspberry Pi)
- Complex startup/shutdown logic (coordinate 5 observers)

---

## Acceptance Criteria

### Functional Requirements

#### 1. FileWatcherHub Core
- [ ] Create `FileWatcherHub` class in `src/mnemosyne/aletheia/file_watcher_hub.py`
- [ ] Single `watchdog.Observer` instance manages all file monitoring
- [ ] Configurable vault path and debounce seconds
- [ ] Support for recursive directory watching
- [ ] Handler registration with priority system (0-999, lower = earlier)
- [ ] Thread-safe handler registration and event dispatch
- [ ] Start/stop lifecycle methods
- [ ] `is_running()` status check

#### 2. Handler Interface
- [ ] Create `FileChangeHandler` abstract base class
- [ ] Required method: `handle_event(event_type: str, file_path: str)`
- [ ] Event types: `'created'`, `'modified'`, `'deleted'`, `'moved'`
- [ ] Optional method: `should_process(file_path: str) -> bool` for filtering
- [ ] Optional method: `get_name() -> str` for logging/debugging

#### 3. Event Dispatch Logic
- [ ] Events dispatched to handlers in priority order (low to high)
- [ ] Each handler execution isolated with try/except
- [ ] Failed handler logs error but doesn't block other handlers
- [ ] Debouncing applied at hub level (before dispatch)
- [ ] Support for both synchronous and async handlers (future)

#### 4. Built-in File Filtering
- [ ] Ignore temporary files (`.tmp`, `~`, `.swp`)
- [ ] Ignore hidden files (starting with `.`)
- [ ] Ignore `.obsidian` directory contents
- [ ] Ignore non-markdown files (unless handler opts in)
- [ ] Configurable ignore patterns (glob/regex)

#### 5. Handler Implementations
- [ ] Migrate `VaultWatcher` → `WeaviateIngestionHandler`
- [ ] Create `ShadowCopyHandler` for Story 025
- [ ] Create `ProjectSyncHandler` for Story 016
- [ ] Create `AutoTaggingHandler` for Story 025
- [ ] All handlers follow same interface

#### 6. Logging & Observability
- [ ] Structured logging for all events (file path, event type, timestamp)
- [ ] Log handler execution order and timing
- [ ] Log handler errors with full context
- [ ] Optional metrics: event counts, handler latencies
- [ ] Debug mode for verbose logging

### Non-Functional Requirements

#### Performance
- [ ] Single file change triggers max 1 debounced event to hub
- [ ] Handler dispatch completes in <100ms (excluding handler work)
- [ ] No memory leaks with long-running watcher (24+ hours)
- [ ] Graceful handling of event storms (rapid file changes)

#### Reliability
- [ ] Hub continues running if handler crashes
- [ ] Clean shutdown stops observer and releases resources
- [ ] No zombie threads after stop()
- [ ] Restart-safe (can stop and start multiple times)

#### Testability
- [ ] Hub unit tests with mock handlers
- [ ] Each handler independently unit testable
- [ ] Integration tests with real file system events
- [ ] Test helper: `FileChangeRecorder` for capturing events

---

## Technical Design

### Class Hierarchy

```python
# src/mnemosyne/aletheia/file_watcher_hub.py

from abc import ABC, abstractmethod
from typing import Callable, List, Tuple
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

class FileChangeHandler(ABC):
    """Abstract base class for file change handlers."""

    @abstractmethod
    def handle_event(self, event_type: str, file_path: str) -> None:
        """Handle a file system event."""
        pass

    def should_process(self, file_path: str) -> bool:
        """Override to filter which files this handler processes."""
        return True

    def get_name(self) -> str:
        """Return handler name for logging."""
        return self.__class__.__name__


class FileWatcherHub:
    """
    Centralized file watcher that coordinates multiple handlers.

    Priority Levels (Recommended):
    - 0-50: Shadow copy sync (must run first to create clean copy)
    - 51-100: Metadata sync (PostgreSQL, etc.)
    - 101-200: Content enrichment (tagging, linking)
    - 201-999: Vector/search indexing (Weaviate, etc.)
    """

    def __init__(
        self,
        vault_path: str,
        debounce_seconds: float = 2.0,
        ignore_patterns: List[str] = None
    ):
        """
        Initialize file watcher hub.

        Args:
            vault_path: Path to Obsidian vault directory
            debounce_seconds: Seconds to wait before processing events
            ignore_patterns: Glob patterns to ignore (e.g., ["*.tmp", ".*"])
        """
        self.vault_path = Path(vault_path)
        self.debounce_seconds = debounce_seconds
        self.ignore_patterns = ignore_patterns or [
            ".*",           # Hidden files
            "*.tmp",        # Temp files
            "*~",           # Backup files
            "*.swp",        # Vim swap files
            ".obsidian/*",  # Obsidian config
        ]

        self.handlers: List[Tuple[int, FileChangeHandler]] = []
        self.observer: Observer | None = None
        self._running = False
        self._last_processed: Dict[str, datetime] = {}

        if not self.vault_path.exists():
            raise ValueError(f"Vault path does not exist: {vault_path}")

    def register_handler(
        self,
        handler: FileChangeHandler,
        priority: int = 100
    ) -> None:
        """
        Register a handler with priority.

        Args:
            handler: Handler instance to register
            priority: Execution priority (0-999, lower runs first)
        """
        if not isinstance(handler, FileChangeHandler):
            raise TypeError("Handler must extend FileChangeHandler")

        if not 0 <= priority <= 999:
            raise ValueError("Priority must be between 0 and 999")

        self.handlers.append((priority, handler))
        self.handlers.sort(key=lambda x: x[0])  # Sort by priority

        logger.info(
            f"Registered handler {handler.get_name()} with priority {priority}"
        )

    def start(self) -> None:
        """Start watching the vault for changes."""
        if self._running:
            logger.warning("Watcher hub already running")
            return

        logger.info(f"Starting file watcher hub for: {self.vault_path}")

        event_handler = _HubEventHandler(self)
        self.observer = Observer()
        self.observer.schedule(
            event_handler,
            str(self.vault_path),
            recursive=True
        )
        self.observer.start()
        self._running = True

        logger.info(
            f"File watcher hub started with {len(self.handlers)} handlers"
        )

    def stop(self) -> None:
        """Stop watching the vault."""
        if not self._running:
            logger.warning("Watcher hub not running")
            return

        logger.info("Stopping file watcher hub...")

        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=5)

        self._running = False
        logger.info("File watcher hub stopped")

    def is_running(self) -> bool:
        """Check if hub is currently running."""
        return self._running

    def _should_ignore(self, file_path: str) -> bool:
        """Check if file matches ignore patterns."""
        from fnmatch import fnmatch

        path = Path(file_path)

        for pattern in self.ignore_patterns:
            if fnmatch(path.name, pattern) or fnmatch(str(path), pattern):
                return True

        return False

    def _should_process_event(self, file_path: str) -> bool:
        """Check debounce timing for file."""
        now = datetime.now()
        last_time = self._last_processed.get(file_path)

        if last_time is None:
            return True

        return (now - last_time).total_seconds() >= self.debounce_seconds

    def _dispatch_event(self, event_type: str, file_path: str) -> None:
        """Dispatch event to all registered handlers in priority order."""
        # Apply global filters
        if self._should_ignore(file_path):
            logger.debug(f"Ignoring file: {file_path}")
            return

        if not self._should_process_event(file_path):
            logger.debug(f"Debouncing file: {file_path}")
            return

        # Update last processed time
        self._last_processed[file_path] = datetime.now()

        logger.info(f"Processing {event_type} event: {file_path}")

        # Dispatch to handlers in priority order
        for priority, handler in self.handlers:
            handler_name = handler.get_name()

            # Check if handler wants to process this file
            try:
                if not handler.should_process(file_path):
                    logger.debug(
                        f"Handler {handler_name} skipped {file_path}"
                    )
                    continue
            except Exception as e:
                logger.error(
                    f"Handler {handler_name}.should_process() failed: {e}"
                )
                continue

            # Execute handler
            try:
                logger.debug(
                    f"Dispatching to {handler_name} (priority={priority})"
                )
                handler.handle_event(event_type, file_path)
                logger.debug(f"Handler {handler_name} completed")
            except Exception as e:
                logger.error(
                    f"Handler {handler_name} failed: {e}",
                    exc_info=True
                )
                # Continue to next handler (fault isolation)


class _HubEventHandler(FileSystemEventHandler):
    """Internal event handler that forwards to hub."""

    def __init__(self, hub: FileWatcherHub):
        super().__init__()
        self.hub = hub

    def on_created(self, event):
        if not event.is_directory:
            self.hub._dispatch_event('created', event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            self.hub._dispatch_event('modified', event.src_path)

    def on_deleted(self, event):
        if not event.is_directory:
            self.hub._dispatch_event('deleted', event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            self.hub._dispatch_event('deleted', event.src_path)
            self.hub._dispatch_event('created', event.dest_path)
```

### Example Handler Implementations

```python
# src/mnemosyne/aletheia/handlers/weaviate_ingestion_handler.py

class WeaviateIngestionHandler(FileChangeHandler):
    """
    Ingests markdown files to Weaviate vector database.
    Priority: 250 (runs after shadow copy, tagging, etc.)
    """

    def __init__(self, ingestor, shadow_vault_path: str):
        self.ingestor = ingestor
        self.shadow_vault_path = Path(shadow_vault_path)

    def should_process(self, file_path: str) -> bool:
        # Only process markdown files
        return file_path.endswith('.md')

    def handle_event(self, event_type: str, file_path: str):
        if event_type in ('created', 'modified'):
            # Ingest from shadow copy (after tagging is complete)
            shadow_path = self._get_shadow_path(file_path)
            if shadow_path.exists():
                self.ingestor.ingest_file(str(shadow_path))

        elif event_type == 'deleted':
            # Remove from Weaviate
            self._remove_from_weaviate(file_path)

    def _get_shadow_path(self, source_path: str) -> Path:
        """Convert source vault path to shadow vault path."""
        # Implementation depends on vault structure
        pass


# src/mnemosyne/aletheia/handlers/project_sync_handler.py

class ProjectSyncHandler(FileChangeHandler):
    """
    Syncs Obsidian Projects folder ↔ PostgreSQL.
    Priority: 50 (runs early, before enrichment)
    """

    def __init__(self, sync_manager: ObsidianSyncManager):
        self.sync_manager = sync_manager

    def should_process(self, file_path: str) -> bool:
        # Only process files in Projects folder
        return '/Projects/' in file_path and file_path.endswith('.md')

    def handle_event(self, event_type: str, file_path: str):
        if event_type in ('created', 'modified'):
            self.sync_manager.sync_obsidian_file_to_sql(file_path)
        # Note: Don't delete projects on file deletion


# src/mnemosyne/aletheia/handlers/shadow_copy_handler.py

class ShadowCopyHandler(FileChangeHandler):
    """
    Syncs source vault → shadow copy.
    Priority: 10 (MUST run first to create clean baseline)
    """

    def __init__(self, janitor):
        self.janitor = janitor

    def handle_event(self, event_type: str, file_path: str):
        if event_type in ('created', 'modified'):
            self.janitor.sync_file_to_shadow(file_path)
        elif event_type == 'deleted':
            self.janitor.delete_from_shadow(file_path)
```

---

## Migration Strategy

### Phase 1: Foundation (Week 1)
- [ ] Implement `FileWatcherHub` core
- [ ] Implement `FileChangeHandler` interface
- [ ] Write comprehensive unit tests
- [ ] Create integration test suite
- [ ] Document API and usage examples

### Phase 2: Handler Migration (Week 1-2)
- [ ] Wrap existing `VaultWatcher` as `WeaviateIngestionHandler`
- [ ] Update Story 000 to use hub (backward compatible)
- [ ] Run parallel testing (old watcher + new hub)
- [ ] Validate no regressions in ingestion

### Phase 3: New Handlers (Week 2)
- [ ] Implement `ProjectSyncHandler` for Story 016
- [ ] Implement `ShadowCopyHandler` for Story 025
- [ ] Implement `AutoTaggingHandler` for Story 025
- [ ] Integration testing with multiple handlers

### Phase 4: Deprecation (Week 3)
- [ ] Mark standalone `VaultWatcher` as deprecated
- [ ] Update all references to use `FileWatcherHub`
- [ ] Remove old `VaultWatcher` after migration complete
- [ ] Update documentation

### Rollback Plan
If hub causes issues:
1. Each handler can run standalone (implements same interface)
2. Can revert to original `VaultWatcher` for ingestion
3. Handlers are isolated - can disable individually
4. Priority system can be adjusted without code changes

---

## Testing Strategy

### Unit Tests
```python
# tests/unit/test_file_watcher_hub.py

def test_hub_initialization():
    """Should initialize with vault path"""
    hub = FileWatcherHub("/path/to/vault")
    assert hub.vault_path == Path("/path/to/vault")
    assert not hub.is_running()

def test_handler_registration():
    """Should register handlers in priority order"""
    hub = FileWatcherHub("/tmp")

    handler1 = MockHandler()
    handler2 = MockHandler()

    hub.register_handler(handler1, priority=100)
    hub.register_handler(handler2, priority=50)

    # Should be sorted by priority
    assert hub.handlers[0][0] == 50  # handler2 first
    assert hub.handlers[1][0] == 100  # handler1 second

def test_event_dispatch_order():
    """Should dispatch to handlers in priority order"""
    hub = FileWatcherHub("/tmp")
    recorder = []

    hub.register_handler(RecordingHandler(recorder, "H1"), priority=100)
    hub.register_handler(RecordingHandler(recorder, "H2"), priority=50)
    hub.register_handler(RecordingHandler(recorder, "H3"), priority=75)

    hub._dispatch_event('created', '/tmp/test.md')

    assert recorder == ["H2", "H3", "H1"]  # Priority order

def test_handler_error_isolation():
    """Should continue to other handlers if one fails"""
    hub = FileWatcherHub("/tmp")
    recorder = []

    hub.register_handler(RecordingHandler(recorder, "H1"), priority=50)
    hub.register_handler(FailingHandler(), priority=75)  # This fails
    hub.register_handler(RecordingHandler(recorder, "H2"), priority=100)

    hub._dispatch_event('created', '/tmp/test.md')

    # H1 and H2 should run despite H2 failure
    assert recorder == ["H1", "H2"]

def test_debouncing():
    """Should debounce rapid file changes"""
    hub = FileWatcherHub("/tmp", debounce_seconds=0.1)
    recorder = []
    hub.register_handler(RecordingHandler(recorder), priority=50)

    # First event processes
    hub._dispatch_event('modified', '/tmp/test.md')
    assert len(recorder) == 1

    # Second event immediately - debounced
    hub._dispatch_event('modified', '/tmp/test.md')
    assert len(recorder) == 1  # Still 1

    # Wait for debounce period
    time.sleep(0.15)
    hub._dispatch_event('modified', '/tmp/test.md')
    assert len(recorder) == 2  # Now 2
```

### Integration Tests
```python
# tests/integration/test_file_watcher_hub_integration.py

def test_real_file_events(tmp_path):
    """Should detect real file system events"""
    vault = tmp_path / "vault"
    vault.mkdir()

    recorder = []
    handler = RecordingHandler(recorder)

    hub = FileWatcherHub(str(vault), debounce_seconds=0.1)
    hub.register_handler(handler, priority=50)
    hub.start()

    try:
        # Create file
        test_file = vault / "test.md"
        test_file.write_text("# Test")
        time.sleep(0.5)

        assert ('created', str(test_file)) in recorder

        # Modify file
        test_file.write_text("# Modified")
        time.sleep(0.5)

        assert ('modified', str(test_file)) in recorder

    finally:
        hub.stop()
```

---

## Documentation Requirements

- [ ] Architecture decision record (ADR) for centralized watcher
- [ ] API documentation for `FileWatcherHub` and `FileChangeHandler`
- [ ] Migration guide for existing watchers
- [ ] Tutorial: Creating custom handlers
- [ ] Performance benchmarks: hub vs multiple observers
- [ ] Troubleshooting guide for common issues

---

## Dependencies

- `watchdog>=4.0.0` (already in dependencies)
- No new external dependencies required

---

## Affected Components

- **Aletheia**: Core file watcher hub implementation
- **Story 000**: Migrate VaultWatcher → WeaviateIngestionHandler
- **Story 016**: New ProjectSyncHandler
- **Story 025**: New ShadowCopyHandler and AutoTaggingHandler
- **Future Stories**: Any file-based automation

---

## Priority

**High** - Architectural foundation for multiple stories (000, 016, 025)

Blocking:
- Story 016 Phase 4 (file watcher implementation)
- Story 025 (shadow copy sync)

---

## Estimate

**5 story points (3-4 days)**

Breakdown:
- Day 1: FileWatcherHub core + unit tests
- Day 2: Handler interface + integration tests
- Day 3: Migrate VaultWatcher + documentation
- Day 4: Testing, refinement, CR review

---

## Linear Labels

`phase-0`, `architecture`, `refactoring`, `aletheia`, `file-watching`

---

## Related Stories

- **Story 000**: Obsidian Vault Ingestion (current VaultWatcher)
- **Story 016**: Project Manager Agent (needs Projects folder sync)
- **Story 025**: Shadow Copy Hygiene (needs source → shadow sync)

---

## References

- Existing implementation: `src/mnemosyne/aletheia/vault_watcher.py`
- Watchdog documentation: https://python-watchdog.readthedocs.io/
- Design pattern: Observer + Chain of Responsibility
