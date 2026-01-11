"""
E2E test for Story 031: ingest raw emails with semantic chunking into TheLethe.
"""

import mailbox
from email.message import EmailMessage

import pytest

from mnemosyne.config.providers import ProviderConfig
from mnemosyne.providers.factory import create_embedding_provider, create_llm_provider


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


@pytest.mark.e2e
@pytest.mark.weaviate
def test_story_031_ingest_semantic_chunking(
    tmp_path, weaviate_client, test_config, clean_weaviate_collection
):
    from mnemosyne.aletheia.email_ingest import EmailIngestConfig, EmailIngestor

    provider_config = ProviderConfig(
        embedding_provider="ollama",
        llm_provider="ollama",
        ollama_base_url=test_config["ollama_url"],
    )
    embedding_provider = create_embedding_provider(provider_config)
    llm_provider = create_llm_provider(provider_config)

    source_dir = tmp_path / "source"
    source_dir.mkdir()

    _write_eml(
        source_dir / "msg-1.eml",
        subject="Project Update",
        body=(
            "Software release updates with deployment notes and next steps.\n\n"
            "Marketing plans for the upcoming launch and campaign assets.\n\n"
            "Personal note about scheduling a follow-up call."
        )
        * 4,
        message_id="<msg-10@example.com>",
    )

    mbox_path = source_dir / "archive.mbox"
    m1 = EmailMessage()
    m1["Subject"] = "Archive 1"
    m1["From"] = "bob@example.com"
    m1["Date"] = "Tue, 02 Jan 2024 11:00:00 +0000"
    m1["Message-ID"] = "<mbox-10@example.com>"
    m1.set_content(
        "Operations updates on backlog items and deployment planning.\n\n"
        "Customer feedback summary and response plan.\n\n"
        "Budget notes for the next sprint."
    )
    _write_mbox(mbox_path, [m1])

    state_path = tmp_path / "state" / "email_ingestion_state.json"
    cfg = EmailIngestConfig(
        source_dir=source_dir,
        state_path=state_path,
        collection_name="TheLethe",
        chunking_strategy="semantic",
        semantic_min_chunk_size=60,
        semantic_max_chunk_size=400,
        min_body_chars=10,
    )
    ingestor = EmailIngestor(
        cfg,
        weaviate_client,
        embedding_provider=embedding_provider,
        llm_provider=llm_provider,
    )
    summary = ingestor.run()

    assert summary.total_loaded == 2
    assert summary.total_stored > summary.total_loaded

    collection = weaviate_client.collections.get("TheLethe")
    objs = collection.query.fetch_objects(limit=25)
    assert len(objs.objects) == summary.total_stored
    message_ids = {obj.properties["messageId"] for obj in objs.objects}
    assert len(message_ids) == summary.total_loaded
    for obj in objs.objects:
        props = obj.properties
        assert props["documentType"] == "email"
        assert props["body"]
        assert props["messageId"]
        assert props["sourcePath"]
