"""
Unit tests for email ingestion CLI behavior.
"""

import pytest

from mnemosyne.aletheia import email_ingest


def test_email_ingest_main_rejects_email_tsv(monkeypatch, caplog):
    monkeypatch.setenv("EMAIL_TSV", "/tmp/emails.tsv")
    monkeypatch.delenv("SOURCE_DIR", raising=False)

    with pytest.raises(SystemExit) as exc:
        email_ingest.main()

    assert exc.value.code == 1
    assert "EMAIL_TSV" in caplog.text
    assert "SOURCE_DIR" in caplog.text
