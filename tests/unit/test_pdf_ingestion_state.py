"""
Unit tests for PDF ingestion state tracking.
"""

from pathlib import Path

from mnemosyne.aletheia.pdf_ingestion_state import PDFIngestionState


def test_pdf_state_roundtrip(tmp_path: Path):
    state_path = tmp_path / "state" / "pdf_ingestion_state.json"
    state = PDFIngestionState(state_path)

    file_path = "/vault/docs/report.pdf"
    state.mark_ingested(file_path, mtime=1000.0, size=2048)
    state.save()

    loaded = PDFIngestionState(state_path)
    assert loaded.is_ingested(file_path, mtime=1000.0, size=2048)
    assert not loaded.is_ingested(file_path, mtime=1001.0, size=2048)
    assert not loaded.is_ingested(file_path, mtime=1000.0, size=4096)


def test_pdf_state_creates_parent_directory(tmp_path: Path):
    state_path = tmp_path / "nested" / "pdf_ingestion_state.json"
    state = PDFIngestionState(state_path)

    state.mark_ingested("/vault/docs/scan.pdf", mtime=2000.0, size=512)
    state.save()

    assert state_path.exists()
