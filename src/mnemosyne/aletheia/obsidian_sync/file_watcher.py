"""
Obsidian File Watcher for Project Manager Agent (Story 016)

Watches the Obsidian Projects folder for markdown file changes and
automatically syncs edits back to PostgreSQL (The Ananke).
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)


class ObsidianFileWatcher:
    """
    Watches Obsidian Projects folder for file changes and triggers sync to SQL.

    Monitors markdown files in the Projects folder and automatically syncs
    user edits back to The Ananke via ObsidianSyncManager.
    """

    def __init__(
        self,
        vault_path: str,
        sync_manager,
        projects_folder: str = "Projects",
        debounce_seconds: float = 2.0,
        on_file_changed: Optional[Callable[[str], None]] = None,
        on_sync_error: Optional[Callable[[str, Exception], None]] = None,
    ):
        """
        Initialize Obsidian file watcher.

        Args:
            vault_path: Path to Obsidian vault directory
            sync_manager: ObsidianSyncManager instance for syncing
            projects_folder: Folder name to watch (default: "Projects")
            debounce_seconds: Seconds to wait before processing events
            on_file_changed: Optional callback when file changes
            on_sync_error: Optional callback when sync fails
        """
        self.vault_path = vault_path
        self.sync_manager = sync_manager
        self.projects_folder = projects_folder
        self.debounce_seconds = debounce_seconds
        self.on_file_changed = on_file_changed
        self.on_sync_error = on_sync_error

        # Validate vault path
        vault = Path(vault_path)
        if not vault.exists():
            raise ValueError(f"Vault path does not exist: {vault_path}")

        # Ensure Projects folder exists
        self.watch_path = str(vault / projects_folder)
        projects_path = Path(self.watch_path)
        if not projects_path.exists():
            projects_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created Projects folder: {self.watch_path}")

        # Setup event handler
        self.event_handler = _ObsidianEventHandler(
            watcher=self,
            debounce_seconds=debounce_seconds,
        )

        self.observer: Optional[Observer] = None
        self.is_running = False

    def start(self):
        """Start watching the Projects folder for changes."""
        if self.is_running:
            logger.warning("Watcher already running")
            return

        logger.info(f"Starting Obsidian file watcher for: {self.watch_path}")

        self.observer = Observer()
        self.observer.schedule(
            self.event_handler,
            self.watch_path,
            recursive=True,
        )
        self.observer.start()
        self.is_running = True

        logger.info("Obsidian file watcher started successfully")

    def stop(self):
        """Stop watching the Projects folder."""
        if not self.is_running:
            logger.warning("Watcher not running")
            return

        logger.info("Stopping Obsidian file watcher...")

        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=5)

        self.is_running = False
        logger.info("Obsidian file watcher stopped")

    def __enter__(self):
        """Context manager entry - start watcher."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - stop watcher."""
        self.stop()
        return False


class _ObsidianEventHandler(FileSystemEventHandler):
    """
    Internal event handler for Obsidian file events.

    Filters markdown files and triggers sync via ObsidianSyncManager.
    """

    def __init__(self, watcher: ObsidianFileWatcher, debounce_seconds: float):
        super().__init__()
        self.watcher = watcher
        self.debounce_seconds = debounce_seconds
        self._last_processed: dict[str, datetime] = {}

    def _should_process(self, file_path: str) -> bool:
        """
        Check if file should be processed based on debounce timing.

        Args:
            file_path: Path to file

        Returns:
            True if file should be processed
        """
        now = datetime.now()
        last_time = self._last_processed.get(file_path)

        if last_time is None:
            return True

        # Only process if enough time has passed since last event
        return (now - last_time).total_seconds() >= self.debounce_seconds

    def _is_markdown_file(self, file_path: str) -> bool:
        """Check if file is a markdown file."""
        return file_path.endswith(".md")

    def _is_temp_file(self, file_path: str) -> bool:
        """Check if file is a temporary file that should be ignored."""
        path = Path(file_path)
        # Ignore hidden files, temp files, swap files, and Obsidian config
        return (
            path.name.startswith(".")
            or path.name.startswith("~")
            or path.name.endswith(".tmp")
            or path.name.endswith("~")
            or path.name.endswith(".swp")
            or ".obsidian" in path.parts
        )

    def _handle_file_change(self, file_path: str):
        """
        Handle a file change event.

        Args:
            file_path: Path to the changed file
        """
        # Apply filters
        if not self._is_markdown_file(file_path):
            return

        if self._is_temp_file(file_path):
            logger.debug(f"Ignoring temp file: {file_path}")
            return

        if not self._should_process(file_path):
            logger.debug(f"Debouncing file: {file_path}")
            return

        logger.info(f"Processing file change: {file_path}")
        self._last_processed[file_path] = datetime.now()

        # Trigger optional callback
        if self.watcher.on_file_changed:
            try:
                self.watcher.on_file_changed(file_path)
            except Exception as e:
                logger.error(f"File changed callback failed: {e}")

        # Sync to SQL
        try:
            self.watcher.sync_manager.sync_obsidian_file_to_sql(file_path)
            logger.info(f"Successfully synced: {file_path}")
        except Exception as e:
            logger.error(f"Failed to sync {file_path}: {e}", exc_info=True)

            # Trigger error callback
            if self.watcher.on_sync_error:
                try:
                    self.watcher.on_sync_error(file_path, e)
                except Exception as callback_error:
                    logger.error(f"Sync error callback failed: {callback_error}")

    def on_created(self, event):
        """Handle file creation event."""
        if event.is_directory:
            return

        self._handle_file_change(event.src_path)

    def on_modified(self, event):
        """Handle file modification event."""
        if event.is_directory:
            return

        self._handle_file_change(event.src_path)
