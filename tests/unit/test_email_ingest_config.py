"""
Unit tests for EmailIngestConfig environment defaults.
"""

import pytest

from mnemosyne.aletheia.email_ingest import EmailIngestConfig


def test_email_ingest_config_defaults_to_semantic(monkeypatch, tmp_path):
    monkeypatch.setenv("SOURCE_DIR", str(tmp_path))
    monkeypatch.delenv("CHUNKING_STRATEGY", raising=False)

    config = EmailIngestConfig.from_env()

    assert config.chunking_strategy == "semantic"


def test_email_ingest_config_accepts_override(monkeypatch, tmp_path):
    monkeypatch.setenv("SOURCE_DIR", str(tmp_path))
    monkeypatch.setenv("CHUNKING_STRATEGY", "recursive")

    config = EmailIngestConfig.from_env()

    assert config.chunking_strategy == "recursive"


def test_email_ingest_config_rejects_email_tsv(monkeypatch, tmp_path):
    monkeypatch.setenv("SOURCE_DIR", str(tmp_path))
    monkeypatch.setenv("EMAIL_TSV", "/tmp/emails.tsv")

    with pytest.raises(ValueError, match="EMAIL_TSV"):
        EmailIngestConfig.from_env()
