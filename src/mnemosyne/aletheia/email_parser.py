"""
Parsers for raw .eml and .mbox email sources.
"""

from __future__ import annotations

import mailbox
from collections.abc import Iterator
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from hashlib import sha256
from pathlib import Path

from mnemosyne.aletheia.email_cleaner import clean_email_body
from mnemosyne.aletheia.models import Email


def parse_eml_file(path: Path) -> Email | None:
    """Parse a single .eml file into an Email object."""
    message = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
    return _email_from_message(message, source_path=str(path))


def parse_mbox_file(path: Path) -> Iterator[Email]:
    """Yield Email objects from an .mbox archive."""
    mbox = mailbox.mbox(path)
    try:
        for index, message in enumerate(mbox):
            email = _email_from_message(message, source_path=f"{path}:{index}")
            if email:
                yield email
    finally:
        mbox.close()


def _email_from_message(message, source_path: str) -> Email | None:
    normalized = _to_email_message(message)
    subject = (normalized.get("subject") or "").strip()
    sender = (normalized.get("from") or "").strip() or None
    date = (normalized.get("date") or "").strip() or None
    message_id = (normalized.get("message-id") or "").strip() or None

    body = _extract_body(normalized)
    cleaned_body = clean_email_body(body)

    unique_id = message_id or _hash_email(subject, sender, date, cleaned_body)

    return Email(
        subject=subject,
        body=cleaned_body,
        sender=sender,
        date=date,
        message_id=message_id,
        source_path=source_path,
        unique_id=unique_id,
    )


def _to_email_message(message) -> EmailMessage:
    if isinstance(message, EmailMessage):
        return message
    return BytesParser(policy=policy.default).parsebytes(message.as_bytes())


def _extract_body(message: EmailMessage) -> str:
    if message.is_multipart():
        plain_parts: list[str] = []
        html_parts: list[str] = []
        for part in message.walk():
            if part.get_content_maintype() == "multipart":
                continue
            if part.get_filename():
                continue
            content_type = part.get_content_type()
            payload = _decode_part(part)
            if not payload:
                continue
            if content_type == "text/plain":
                plain_parts.append(payload)
            elif content_type == "text/html":
                html_parts.append(payload)
        if plain_parts:
            return "\n".join(plain_parts)
        if html_parts:
            return "\n".join(html_parts)
        return ""

    return _decode_part(message)


def _decode_part(message: EmailMessage) -> str:
    try:
        return message.get_content() or ""
    except Exception:
        payload = message.get_payload(decode=True)
        if not payload:
            return ""
        charset = message.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")


def _hash_email(subject: str, sender: str | None, date: str | None, body: str) -> str:
    seed = "|".join(
        [
            subject or "",
            sender or "",
            date or "",
            body[:256],
        ]
    )
    digest = sha256(seed.encode("utf-8")).hexdigest()
    return f"hash-{digest}"
