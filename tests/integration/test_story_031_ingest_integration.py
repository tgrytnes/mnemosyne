"""
Integration test for Story 031: ingest raw emails into Weaviate TheLethe as chunks.
"""

import mailbox
from email.message import EmailMessage
from pathlib import Path

import pytest

from mnemosyne.config.providers import ProviderConfig
from mnemosyne.providers.factory import create_embedding_provider


def _write_eml(
    path,
    *,
    subject: str,
    body: str,
    message_id: str | None,
    sender: str = "alice@example.com",
    date: str = "Mon, 01 Jan 2024 10:00:00 +0000",
) -> None:
    from email.message import EmailMessage

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["Date"] = date
    if message_id:
        msg["Message-ID"] = message_id
    msg.set_content(body)
    path.write_bytes(msg.as_bytes())


def _write_mbox(path, messages) -> None:
    mbox = mailbox.mbox(path)
    for message in messages:
        mbox.add(message)
    mbox.flush()
    mbox.close()


@pytest.mark.integration
@pytest.mark.weaviate
def test_email_ingest_raw_sources_to_lethe(
    tmp_path: Path,
    weaviate_client,
    clean_weaviate_collection,
    test_config,
):
    from mnemosyne.aletheia.email_ingest import EmailIngestConfig, EmailIngestor

    provider_config = ProviderConfig(
        embedding_provider="ollama", ollama_base_url=test_config["ollama_url"]
    )
    embedding_provider = create_embedding_provider(provider_config)

    source_dir = tmp_path / "source"
    source_dir.mkdir()

    _write_eml(
        source_dir / "msg-1.eml",
        subject="Hello",
        body="Alpha update.\n\nBeta planning.\n\nGamma notes." * 10,
        message_id="<msg-1@example.com>",
    )
    _write_eml(
        source_dir / "msg-2.eml",
        subject="Update",
        body="Topic one.\n\nTopic two.\n\nTopic three." * 8,
        message_id="<msg-2@example.com>",
    )

    mbox_path = source_dir / "archive.mbox"
    m1 = EmailMessage()
    m1["Subject"] = "Archive 1"
    m1["From"] = "bob@example.com"
    m1["Date"] = "Tue, 02 Jan 2024 11:00:00 +0000"
    m1["Message-ID"] = "<mbox-1@example.com>"
    m1.set_content("Archive alpha.\n\nArchive beta.\n\nArchive gamma." * 6)

    m2 = EmailMessage()
    m2["Subject"] = "Archive 2"
    m2["From"] = "carol@example.com"
    m2["Date"] = "Wed, 03 Jan 2024 12:00:00 +0000"
    m2["Message-ID"] = "<mbox-2@example.com>"
    m2.set_content("Archive delta.\n\nArchive epsilon.\n\nArchive zeta." * 6)

    _write_mbox(mbox_path, [m1, m2])

    state_path = tmp_path / "state" / "email_ingestion_state.json"
    cfg = EmailIngestConfig(
        source_dir=source_dir,
        state_path=state_path,
        collection_name="TheLethe",
        chunking_strategy="recursive",
        chunk_size=120,
        chunk_overlap=0,
        min_body_chars=10,
    )
    ingestor = EmailIngestor(
        cfg,
        weaviate_client,
        embedding_provider=embedding_provider,
    )
    result = ingestor.run()

    assert result.total_loaded == 4
    assert result.total_stored > result.total_loaded

    collection = weaviate_client.collections.get("TheLethe")
    objs = collection.query.fetch_objects(limit=50)
    assert len(objs.objects) == result.total_stored
    for obj in objs.objects:
        props = obj.properties
        assert props["documentType"] == "email"
        assert props["body"]
        assert props["messageId"]
        assert props["sourcePath"]
        assert "chunkIndex" in props
