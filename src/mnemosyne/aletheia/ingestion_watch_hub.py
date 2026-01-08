"""Unified watcher hub for vault, email, and PDF ingestion sources."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from watchdog.observers import Observer

from mnemosyne.aletheia.ingestion_watchers import EmailEventHandler, PDFEventHandler
from mnemosyne.aletheia.vault_watcher import VaultWatcher as _VaultWatcher


def _parse_bool(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return value.lower() not in {"false", "0", "no"}


def _parse_float(value: str | None, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


class IngestionWatchConfig:
    """Environment-driven configuration for ingestion watchers."""

    def __init__(self) -> None:
        self.vault_path = os.getenv("OBSIDIAN_VAULT_PATH")
        self.email_source_dir = os.getenv("SOURCE_DIR")
        self.pdf_scan_path = os.getenv("PDF_SCAN_PATH")

        self.watch_vault_enabled = _parse_bool(os.getenv("WATCH_VAULT_ENABLED"), True)
        self.watch_email_enabled = _parse_bool(os.getenv("WATCH_EMAIL_ENABLED"), True)
        self.watch_pdf_enabled = _parse_bool(os.getenv("WATCH_PDF_ENABLED"), True)

        default_vault_debounce = _parse_float(os.getenv("WATCH_DEBOUNCE_SECONDS"), 2.0)
        self.watch_vault_debounce_seconds = _parse_float(
            os.getenv("WATCH_VAULT_DEBOUNCE_SECONDS"), default_vault_debounce
        )
        self.watch_email_debounce_seconds = _parse_float(
            os.getenv("WATCH_EMAIL_DEBOUNCE_SECONDS"), 5.0
        )
        self.watch_pdf_debounce_seconds = _parse_float(os.getenv("WATCH_PDF_DEBOUNCE_SECONDS"), 5.0)


class VaultWatcher:
    """Adapter that keeps the VaultWatcher signature consistent for the hub."""

    def __init__(self, watch_path: str, debounce_seconds: float):
        self.watch_path = watch_path
        self.debounce_seconds = debounce_seconds
        self._delegate: _VaultWatcher | None = None
        self._on_file_change: Callable[[str], None] | None = None

    def set_callback(self, on_file_change: Callable[[str], None]) -> None:
        self._on_file_change = on_file_change

    def start(self) -> None:
        if self._delegate is None:
            callback = self._on_file_change or (lambda _path: None)
            self._delegate = _VaultWatcher(self.watch_path, callback, self.debounce_seconds)
        self._delegate.start()

    def stop(self) -> None:
        if self._delegate:
            self._delegate.stop()


class _BaseWatcher:
    def __init__(self, watch_path: str, debounce_seconds: float):
        self.watch_path = Path(watch_path)
        self.debounce_seconds = debounce_seconds
        self._observer: Observer | None = None
        self._running = False
        self._on_file_change: Callable[[str], None] | None = None

    def set_callback(self, on_file_change: Callable[[str], None]) -> None:
        self._on_file_change = on_file_change

    def _build_handler(self) -> object:
        raise NotImplementedError

    def start(self) -> None:
        if self._running:
            return
        if not self.watch_path.exists():
            raise ValueError(f"Watch path does not exist: {self.watch_path}")
        if not self.watch_path.is_dir():
            raise ValueError(f"Watch path is not a directory: {self.watch_path}")

        handler = self._build_handler()
        self._observer = Observer()
        self._observer.schedule(handler, str(self.watch_path), recursive=True)
        self._observer.start()
        self._running = True

    def stop(self) -> None:
        if not self._running:
            return
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
        self._running = False


class EmailWatcher(_BaseWatcher):
    def _build_handler(self) -> EmailEventHandler:
        callback = self._on_file_change or (lambda _path: None)
        return EmailEventHandler(callback, debounce_seconds=self.debounce_seconds)


class PDFWatcher(_BaseWatcher):
    def _build_handler(self) -> PDFEventHandler:
        callback = self._on_file_change or (lambda _path: None)
        return PDFEventHandler(callback, debounce_seconds=self.debounce_seconds)


class IngestionWatchHub:
    """Starts and stops per-source watchers based on configuration."""

    def __init__(
        self,
        config: IngestionWatchConfig,
        on_vault_change: Callable[[str], None] | None = None,
        on_email_change: Callable[[str], None] | None = None,
        on_pdf_change: Callable[[str], None] | None = None,
    ) -> None:
        self.config = config
        self._on_vault_change = on_vault_change
        self._on_email_change = on_email_change
        self._on_pdf_change = on_pdf_change

        self.vault_watcher: VaultWatcher | None = None
        self.email_watcher: EmailWatcher | None = None
        self.pdf_watcher: PDFWatcher | None = None

    def _attach_callback(
        self, watcher: object | None, callback: Callable[[str], None] | None
    ) -> None:
        if watcher is None or callback is None:
            return
        if hasattr(watcher, "set_callback"):
            watcher.set_callback(callback)  # type: ignore[call-arg]
        else:
            setattr(watcher, "on_file_change", callback)

    def start(self) -> None:
        if self.config.watch_vault_enabled:
            if not self.config.vault_path:
                raise ValueError("OBSIDIAN_VAULT_PATH must be set to watch the vault")
            self.vault_watcher = VaultWatcher(
                str(self.config.vault_path),
                self.config.watch_vault_debounce_seconds,
            )
            self._attach_callback(self.vault_watcher, self._on_vault_change)
            self.vault_watcher.start()
        else:
            self.vault_watcher = None

        if self.config.watch_email_enabled:
            if not self.config.email_source_dir:
                raise ValueError("SOURCE_DIR must be set to watch emails")
            self.email_watcher = EmailWatcher(
                str(self.config.email_source_dir),
                self.config.watch_email_debounce_seconds,
            )
            self._attach_callback(self.email_watcher, self._on_email_change)
            self.email_watcher.start()
        else:
            self.email_watcher = None

        if self.config.watch_pdf_enabled:
            if not self.config.pdf_scan_path:
                raise ValueError("PDF_SCAN_PATH must be set to watch PDFs")
            self.pdf_watcher = PDFWatcher(
                str(self.config.pdf_scan_path),
                self.config.watch_pdf_debounce_seconds,
            )
            self._attach_callback(self.pdf_watcher, self._on_pdf_change)
            self.pdf_watcher.start()
        else:
            self.pdf_watcher = None

    def stop(self) -> None:
        if self.vault_watcher:
            self.vault_watcher.stop()
        if self.email_watcher:
            self.email_watcher.stop()
        if self.pdf_watcher:
            self.pdf_watcher.stop()
