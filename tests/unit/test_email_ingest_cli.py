"""
Unit tests for email ingestion CLI behavior.
"""

import logging

from click.testing import CliRunner

from mnemosyne.aletheia.email_ingest import email_ingest_cli


def test_email_ingest_cli_rejects_email_tsv(monkeypatch, caplog):
    """CLI should reject deprecated EMAIL_TSV and require SOURCE_DIR."""
    monkeypatch.setenv("EMAIL_TSV", "/tmp/emails.tsv")
    monkeypatch.delenv("SOURCE_DIR", raising=False)

    runner = CliRunner()
    with caplog.at_level(logging.ERROR):
        result = runner.invoke(email_ingest_cli)

    assert result.exit_code == 1
    assert "EMAIL_TSV" in caplog.text
