"""
Data models for raw email ingestion.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Email:
    """Parsed raw email with a stable unique identifier."""

    subject: str
    body: str
    sender: str | None
    date: str | None
    message_id: str | None
    source_path: str
    unique_id: str


@dataclass(frozen=True)
class EmailChunk:
    """Chunk derived from a parent email."""

    parent_email_unique_id: str
    chunk_text: str
    chunk_index: int
    parent_subject: str
    parent_sender: str | None
    parent_date: str | None
    parent_source_path: str
    document_type: str = "email"
