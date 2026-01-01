"""
Integration test for Story 024: ingest cleaned emails into Weaviate Lethe with required fields.
"""

from pathlib import Path

import pytest


def _embed(ollama_client, text: str) -> list[float]:
    response = ollama_client.embeddings(model="qwen3-embedding:0.6b", prompt=text)
    return response["embedding"]


@pytest.mark.integration
@pytest.mark.weaviate
def test_email_ingest_to_lethe(tmp_path: Path, weaviate_client, clean_weaviate_collection, ollama_client):
    from mnemosyne.aletheia.email_ingest import EmailIngestConfig, EmailIngestor

    tsv = tmp_path / "emails.tsv"
    tsv.write_text(
        "subject\tbody\tsource\tmessage_id\tdate\n"
        "Hello\tThis is a body with tracking https://example.com/?utm_source=x\tin1\tmsg-1\t2024-01-01\n"
        "Hello\tThis is a body with tracking https://example.com/?utm_source=x\tin1\tmsg-1\t2024-01-01\n"
        "Bad\tBroken Ã¼ body\tin2\tmsg-2\t2024-01-02\n",
        encoding="utf-8",
    )

    cfg = EmailIngestConfig(
        tsv_path=tsv,
        max_chars=8000,
        collection_name="TheLethe",
        dedup=True,
    )
    ingestor = EmailIngestor(cfg, weaviate_client, embedder=lambda text: _embed(ollama_client, text))
    result = ingestor.run()

    assert result.total_loaded == 3
    assert result.rejected == 1  # mojibake rejected
    assert result.duplicates == 1
    assert result.total_stored == 1

    collection = weaviate_client.collections.get("TheLethe")
    objs = collection.query.fetch_objects(limit=5)
    assert len(objs.objects) == 1
    props = objs.objects[0].properties
    assert props["subject"] == "Hello"
    assert props["body"]
    assert props["messageId"] == "msg-1"
    assert props["sourcePath"] == "in1"
    assert "vector" not in props
