"""
Unit tests for JSON-based email ingestion state.
"""

import json
from pathlib import Path

from mnemosyne.aletheia.email_ingestion_state import EmailIngestionState


def test_state_file_roundtrip(tmp_path: Path):
    state_path = tmp_path / "state" / "email_ingestion_state.json"
    state = EmailIngestionState(state_path)

    assert not state.is_ingested("<msg-1@example.com>")

    state.mark_ingested("<msg-1@example.com>")
    state.mark_ingested("hash-abc123")
    state.mark_ingested("<msg-1@example.com>")
    state.save()

    data = json.loads(state_path.read_text(encoding="utf-8"))
    assert set(data["ingested_ids"]) == {"<msg-1@example.com>", "hash-abc123"}

    loaded = EmailIngestionState(state_path)
    assert loaded.is_ingested("<msg-1@example.com>")
    assert loaded.is_ingested("hash-abc123")


def test_state_creates_parent_directory(tmp_path: Path):
    state_path = tmp_path / "nested" / "email_ingestion_state.json"
    state = EmailIngestionState(state_path)

    state.mark_ingested("hash-xyz")
    state.save()

    assert state_path.exists()
