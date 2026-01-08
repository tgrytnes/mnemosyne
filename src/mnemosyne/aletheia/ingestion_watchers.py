"""File system watchers for email and PDF ingestion."""

from __future__ import annotations

import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler


class _BaseEventHandler(FileSystemEventHandler):
    def __init__(self, on_file_change, debounce_seconds: float):
        super().__init__()
        self.on_file_change = on_file_change
        self.debounce_seconds = debounce_seconds
        self._last_processed: dict[str, float] = {}

    def _is_temp_file(self, file_path: str) -> bool:
        path = Path(file_path)
        name = path.name
        return name.startswith(".") or name.endswith(".tmp") or name.endswith("~")

    def _is_supported_file(self, file_path: str) -> bool:
        raise NotImplementedError

    def _should_process(self, file_path: str) -> bool:
        if not self._is_supported_file(file_path):
            return False
        if self._is_temp_file(file_path):
            return False

        now = time.time()
        last = self._last_processed.get(file_path, 0)
        if now - last < self.debounce_seconds:
            return False
        self._last_processed[file_path] = now
        return True

    def _handle_event(self, event) -> None:
        if event.is_directory:
            return
        file_path = str(event.src_path)
        if self._should_process(file_path):
            if self.on_file_change:
                self.on_file_change(file_path)

    def on_created(self, event):
        self._handle_event(event)

    def on_modified(self, event):
        self._handle_event(event)


class EmailEventHandler(_BaseEventHandler):
    def _is_supported_file(self, file_path: str) -> bool:
        path = Path(file_path)
        return path.suffix.lower() in {".eml", ".mbox"}


class PDFEventHandler(_BaseEventHandler):
    def _is_supported_file(self, file_path: str) -> bool:
        path = Path(file_path)
        return path.suffix.lower() == ".pdf"
