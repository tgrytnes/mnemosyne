"""
E2E test for Story 024: ingest TSV -> clean/dedup/embed -> store in TheLethe.
"""

import pytest


def _embed(ollama_client, text: str) -> list[float]:
    response = ollama_client.embeddings(model="qwen3-embedding:0.6b", prompt=text)
    return response["embedding"]


@pytest.mark.e2e
@pytest.mark.weaviate
def test_story_024_ingest_and_cluster(
    tmp_path, weaviate_client, ollama_client, clean_weaviate_collection
):
    from mnemosyne.aletheia.email_ingest import EmailIngestConfig, EmailIngestor

    tsv = tmp_path / "emails.tsv"
    tsv.write_text(
        "subject\tbody\tsource\tmessage_id\tdate\n"
        "Project Update\tWe shipped the release and have invoices to process.\t"
        "file1\tmsg-10\t2024-02-01\n"
        "Shipping Notice\tYour parcel is on the way with tracking link.\t"
        "file2\tmsg-11\t2024-02-02\n"
        "Invoice\tInvoice for your recent order, please pay.\t"
        "file3\tmsg-12\t2024-02-03\n"
        "Social\tSee you at the meeting next week.\tfile4\tmsg-13\t2024-02-04\n",
        encoding="utf-8",
    )

    cfg = EmailIngestConfig(
        tsv_path=tsv,
        max_chars=8000,
        collection_name="TheLethe",
        dedup=True,
    )
    ingestor = EmailIngestor(
        cfg,
        weaviate_client,
        embedder=lambda text: _embed(ollama_client, text),
    )
    summary = ingestor.run()

    assert summary.total_loaded == 4
    assert summary.total_stored == 4

    clusters = ingestor.cluster_and_label()
    assert len(clusters) >= 1

    collection = weaviate_client.collections.get("TheLethe")
    objs = collection.query.fetch_objects(limit=10)
    assert len(objs.objects) == 4
    for obj in objs.objects:
        props = obj.properties
        assert props["subject"]
        assert props["body"]
        assert props["messageId"]
        assert props["sourcePath"]
