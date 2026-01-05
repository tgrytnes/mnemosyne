"""
Unit tests for raw email parsing utilities.
"""

import mailbox
from email.message import EmailMessage
from pathlib import Path

from mnemosyne.aletheia.email_parser import parse_eml_file, parse_mbox_file


def _write_eml(
    path: Path,
    *,
    subject: str,
    body: str,
    message_id: str | None,
    sender: str = "alice@example.com",
    date: str = "Mon, 01 Jan 2024 10:00:00 +0000",
) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["Date"] = date
    if message_id:
        msg["Message-ID"] = message_id
    msg.set_content(body)
    path.write_bytes(msg.as_bytes())


def _write_mbox(path: Path, messages: list[EmailMessage]) -> None:
    mbox = mailbox.mbox(path)
    for message in messages:
        mbox.add(message)
    mbox.flush()
    mbox.close()


def test_parse_eml_uses_message_id_and_cleans_body(tmp_path: Path):
    eml = tmp_path / "msg.eml"
    _write_eml(
        eml,
        subject="Hello",
        body="<html>Hi there</html> https://example.com/?utm_source=x Sent from my iPhone",
        message_id="<msg-1@example.com>",
    )

    email = parse_eml_file(eml)

    assert email is not None
    assert email.message_id == "<msg-1@example.com>"
    assert email.unique_id == "<msg-1@example.com>"
    assert "utm_source" not in email.body
    assert "<html>" not in email.body
    assert str(eml) in email.source_path


def test_parse_eml_missing_message_id_hashes(tmp_path: Path):
    eml = tmp_path / "missing-id.eml"
    _write_eml(
        eml,
        subject="No ID",
        body="Fallback to hash when Message-ID is missing.",
        message_id=None,
    )

    email = parse_eml_file(eml)
    assert email is not None
    assert email.message_id is None
    assert email.unique_id.startswith("hash-")

    email_again = parse_eml_file(eml)
    assert email_again is not None
    assert email_again.unique_id == email.unique_id


def test_parse_mbox_yields_multiple_emails(tmp_path: Path):
    mbox_path = tmp_path / "archive.mbox"

    msg1 = EmailMessage()
    msg1["Subject"] = "Archive 1"
    msg1["From"] = "bob@example.com"
    msg1["Date"] = "Tue, 02 Jan 2024 11:00:00 +0000"
    msg1["Message-ID"] = "<mbox-1@example.com>"
    msg1.set_content("Archive body one.")

    msg2 = EmailMessage()
    msg2["Subject"] = "Archive 2"
    msg2["From"] = "carol@example.com"
    msg2["Date"] = "Wed, 03 Jan 2024 12:00:00 +0000"
    msg2.set_content("Archive body two.")

    _write_mbox(mbox_path, [msg1, msg2])

    emails = list(parse_mbox_file(mbox_path))

    assert len(emails) == 2
    assert emails[0].unique_id == "<mbox-1@example.com>"
    assert emails[1].unique_id.startswith("hash-")
