"""Unit tests for CR-000-001 unified ingestion watcher hub."""

from __future__ import annotations

from dataclasses import dataclass

import mnemosyne.aletheia.ingestion_watch_hub as ingestion_watch_hub


@dataclass
class _FakeWatcher:
    watch_path: str
    debounce_seconds: float
    started: bool = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.started = False


class _FakeVaultWatcher(_FakeWatcher):
    pass


class _FakeEmailWatcher(_FakeWatcher):
    pass


class _FakePDFWatcher(_FakeWatcher):
    pass


def test_watch_config_defaults(monkeypatch, tmp_path):
    vault = tmp_path / "vault"
    emails = tmp_path / "emails"
    pdfs = tmp_path / "pdfs"
    vault.mkdir()
    emails.mkdir()
    pdfs.mkdir()

    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault))
    monkeypatch.setenv("SOURCE_DIR", str(emails))
    monkeypatch.setenv("PDF_SCAN_PATH", str(pdfs))

    config = ingestion_watch_hub.IngestionWatchConfig()

    assert config.watch_vault_enabled is True
    assert config.watch_email_enabled is True
    assert config.watch_pdf_enabled is True
    assert config.watch_vault_debounce_seconds == 2.0
    assert config.watch_email_debounce_seconds == 5.0
    assert config.watch_pdf_debounce_seconds == 5.0


def test_watch_hub_starts_only_enabled_watchers(monkeypatch, tmp_path):
    vault = tmp_path / "vault"
    emails = tmp_path / "emails"
    pdfs = tmp_path / "pdfs"
    vault.mkdir()
    emails.mkdir()
    pdfs.mkdir()

    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault))
    monkeypatch.setenv("SOURCE_DIR", str(emails))
    monkeypatch.setenv("PDF_SCAN_PATH", str(pdfs))
    monkeypatch.setenv("WATCH_EMAIL_ENABLED", "false")

    monkeypatch.setattr(ingestion_watch_hub, "VaultWatcher", _FakeVaultWatcher)
    monkeypatch.setattr(ingestion_watch_hub, "EmailWatcher", _FakeEmailWatcher)
    monkeypatch.setattr(ingestion_watch_hub, "PDFWatcher", _FakePDFWatcher)

    config = ingestion_watch_hub.IngestionWatchConfig()
    hub = ingestion_watch_hub.IngestionWatchHub(config)

    hub.start()

    assert hub.vault_watcher is not None
    assert hub.vault_watcher.started is True
    assert hub.vault_watcher.debounce_seconds == config.watch_vault_debounce_seconds
    assert hub.email_watcher is None
    assert hub.pdf_watcher is not None
    assert hub.pdf_watcher.started is True
    assert hub.pdf_watcher.debounce_seconds == config.watch_pdf_debounce_seconds

    hub.stop()
    assert hub.vault_watcher.started is False
    assert hub.pdf_watcher.started is False
