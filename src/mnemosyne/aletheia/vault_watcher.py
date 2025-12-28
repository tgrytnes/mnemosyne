"""
Vault watcher for monitoring Obsidian vault changes.

Monitors the vault directory for new/modified markdown files and
triggers ingestion automatically.
"""

import logging
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)


class VaultEventHandler(FileSystemEventHandler):
    """
    Handles file system events for the Obsidian vault.

    Triggers ingestion when markdown files are created or modified.
    """

    def __init__(self, on_file_change: Callable[[str], None], debounce_seconds: float = 2.0):
        """
        Initialize vault event handler.

        Args:
            on_file_change: Callback function to call with file path when a file changes
            debounce_seconds: Seconds to wait before processing (avoids duplicate events)
        """
        super().__init__()
        self.on_file_change = on_file_change
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
        # Ignore hidden files, temp files, and Obsidian's workspace files
        return (
            path.name.startswith(".")
            or path.name.endswith(".tmp")
            or path.name.endswith("~")
            or ".obsidian" in path.parts
        )

    def on_created(self, event):
        """Handle file creation event."""
        if event.is_directory:
            return

        if not self._is_markdown_file(event.src_path):
            return

        if self._is_temp_file(event.src_path):
            return

        if not self._should_process(event.src_path):
            logger.debug(f"Skipping {event.src_path} (debounce)")
            return

        logger.info(f"Detected new file: {event.src_path}")
        self._last_processed[event.src_path] = datetime.now()

        try:
            self.on_file_change(event.src_path)
        except Exception as e:
            logger.error(f"Error processing {event.src_path}: {e}")

    def on_modified(self, event):
        """Handle file modification event."""
        if event.is_directory:
            return

        if not self._is_markdown_file(event.src_path):
            return

        if self._is_temp_file(event.src_path):
            return

        if not self._should_process(event.src_path):
            logger.debug(f"Skipping {event.src_path} (debounce)")
            return

        logger.info(f"Detected modified file: {event.src_path}")
        self._last_processed[event.src_path] = datetime.now()

        try:
            self.on_file_change(event.src_path)
        except Exception as e:
            logger.error(f"Error processing {event.src_path}: {e}")


class VaultWatcher:
    """
    Watches Obsidian vault for changes and triggers ingestion.

    Uses watchdog to monitor file system events and automatically
    ingest new/modified markdown files.
    """

    def __init__(
        self, vault_path: str, on_file_change: Callable[[str], None], debounce_seconds: float = 2.0
    ):
        """
        Initialize vault watcher.

        Args:
            vault_path: Path to Obsidian vault directory
            on_file_change: Callback function to call with file path when a file changes
            debounce_seconds: Seconds to wait before processing (avoids duplicate events)
        """
        self.vault_path = Path(vault_path)
        self.on_file_change = on_file_change
        self.debounce_seconds = debounce_seconds

        if not self.vault_path.exists():
            raise ValueError(f"Vault path does not exist: {vault_path}")

        if not self.vault_path.is_dir():
            raise ValueError(f"Vault path is not a directory: {vault_path}")

        self.event_handler = VaultEventHandler(on_file_change, debounce_seconds)
        self.observer: Observer | None = None
        self._running = False

    def start(self):
        """Start watching the vault for changes."""
        if self._running:
            logger.warning("Watcher already running")
            return

        logger.info(f"Starting vault watcher for: {self.vault_path}")

        self.observer = Observer()
        self.observer.schedule(self.event_handler, str(self.vault_path), recursive=True)
        self.observer.start()
        self._running = True

        logger.info("Vault watcher started successfully")

    def stop(self):
        """Stop watching the vault."""
        if not self._running:
            logger.warning("Watcher not running")
            return

        logger.info("Stopping vault watcher...")

        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=5)

        self._running = False
        logger.info("Vault watcher stopped")

    def is_running(self) -> bool:
        """Check if watcher is currently running."""
        return self._running

    def run_forever(self):
        """
        Run the watcher indefinitely.

        Blocks until interrupted (Ctrl+C).
        """
        try:
            self.start()
            logger.info("Watcher is running. Press Ctrl+C to stop.")

            while True:
                time.sleep(1)

        except KeyboardInterrupt:
            logger.info("Received interrupt signal")

        finally:
            self.stop()
