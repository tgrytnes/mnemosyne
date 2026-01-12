"""
Unit tests for PDF ingestor state path resolution.
"""

import os
from pathlib import Path
from unittest.mock import Mock

from mnemosyne.aletheia.pdf_ingestor import PDFIngestor, _resolve_pdf_state_path


def test_resolve_pdf_state_path_falls_back_when_state_unwritable(tmp_path, monkeypatch):
    monkeypatch.delenv("PDF_INGESTION_STATE_PATH", raising=False)

    original_exists = Path.exists
    original_access = os.access

    def fake_exists(self):
        if str(self) == "/state":
            return True
        return original_exists(self)

    def fake_access(path, mode):
        if str(path) == "/state":
            return False
        return original_access(path, mode)

    monkeypatch.setattr(Path, "exists", fake_exists)
    monkeypatch.setattr(os, "access", fake_access)

    resolved = _resolve_pdf_state_path(None, str(tmp_path))
    assert resolved == tmp_path / "pdf_ingestion_state.json"


def test_pdf_ingestor_defaults_state_path_to_input_dir(tmp_path, monkeypatch):
    monkeypatch.delenv("PDF_INGESTION_STATE_PATH", raising=False)
    monkeypatch.setattr(os, "access", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(Path, "exists", lambda *_args, **_kwargs: False)

    ingestor = PDFIngestor(
        input_dir=str(tmp_path),
        weaviate_client=None,
        embedding_provider=Mock(),
    )

    assert ingestor.state.state_path == tmp_path / "pdf_ingestion_state.json"
