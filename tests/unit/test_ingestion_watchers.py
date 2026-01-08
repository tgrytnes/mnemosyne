"""Unit tests for email/pdf ingestion watchers."""

from __future__ import annotations

import pytest
from watchdog.events import DirCreatedEvent, FileCreatedEvent


@pytest.mark.unit
class TestEmailEventHandler:
    @pytest.fixture
    def callback_recorder(self):
        calls = []

        def on_change(path: str) -> None:
            calls.append(path)

        return calls, on_change

    @pytest.fixture
    def handler(self, callback_recorder):
        from mnemosyne.aletheia.ingestion_watchers import EmailEventHandler

        _, on_change = callback_recorder
        return EmailEventHandler(on_file_change=on_change, debounce_seconds=0.1)

    def test_filters_email_files(self, handler):
        assert handler._is_supported_file("note.eml")
        assert handler._is_supported_file("archive.mbox")
        assert not handler._is_supported_file("note.md")
        assert not handler._is_supported_file("note.pdf")

    def test_ignores_temp_files(self, handler):
        assert handler._is_temp_file(".hidden.eml")
        assert handler._is_temp_file("draft.eml.tmp")
        assert not handler._is_temp_file("note.eml")

    def test_on_created_triggers_for_email_file(self, handler, callback_recorder):
        event = FileCreatedEvent("/emails/new.eml")
        handler.on_created(event)
        calls, _ = callback_recorder
        assert calls == ["/emails/new.eml"]

    def test_on_created_ignores_non_email(self, handler, callback_recorder):
        event = FileCreatedEvent("/emails/new.md")
        handler.on_created(event)
        calls, _ = callback_recorder
        assert calls == []

    def test_on_created_ignores_directories(self, handler, callback_recorder):
        event = DirCreatedEvent("/emails/folder")
        handler.on_created(event)
        calls, _ = callback_recorder
        assert calls == []


@pytest.mark.unit
class TestPDFEventHandler:
    @pytest.fixture
    def callback_recorder(self):
        calls = []

        def on_change(path: str) -> None:
            calls.append(path)

        return calls, on_change

    @pytest.fixture
    def handler(self, callback_recorder):
        from mnemosyne.aletheia.ingestion_watchers import PDFEventHandler

        _, on_change = callback_recorder
        return PDFEventHandler(on_file_change=on_change, debounce_seconds=0.1)

    def test_filters_pdf_files(self, handler):
        assert handler._is_supported_file("scan.pdf")
        assert not handler._is_supported_file("note.md")
        assert not handler._is_supported_file("message.eml")

    def test_ignores_temp_files(self, handler):
        assert handler._is_temp_file(".hidden.pdf")
        assert handler._is_temp_file("scan.pdf.tmp")
        assert not handler._is_temp_file("scan.pdf")

    def test_on_created_triggers_for_pdf_file(self, handler, callback_recorder):
        event = FileCreatedEvent("/pdfs/new.pdf")
        handler.on_created(event)
        calls, _ = callback_recorder
        assert calls == ["/pdfs/new.pdf"]

    def test_on_created_ignores_non_pdf(self, handler, callback_recorder):
        event = FileCreatedEvent("/pdfs/new.eml")
        handler.on_created(event)
        calls, _ = callback_recorder
        assert calls == []
