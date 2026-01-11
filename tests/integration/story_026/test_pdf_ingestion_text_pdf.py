"""
Integration test for Story 026: text-based PDF ingestion.
Requires Weaviate and Ollama running.
"""

import shutil
from pathlib import Path

import pytest


@pytest.mark.integration
@pytest.mark.weaviate
@pytest.mark.ollama
def test_text_pdf_ingestion_to_thelethe(tmp_path, weaviate_client, test_config):
    from mnemosyne.aletheia.pdf_ingestor import PDFIngestor
    from mnemosyne.alexandria.weaviate_schema import WeaviateSchemaManager
    from mnemosyne.config.providers import ProviderConfig
    from mnemosyne.providers.factory import create_embedding_provider

    provider_config = ProviderConfig(
        embedding_provider="ollama", ollama_base_url=test_config["ollama_url"]
    )
    embedding_provider = create_embedding_provider(provider_config)

    # Prepare a simple text PDF
    sample_pdf = tmp_path / "sample.pdf"
    src_pdf = (
        Path(__file__).resolve().parents[3] / "test_data" / "fake_pdfs" / "doc_01_project_brief.pdf"
    )
    shutil.copy(src_pdf, sample_pdf)

    cfg_dir = tmp_path
    ingestor = PDFIngestor(
        input_dir=str(cfg_dir),
        weaviate_client=weaviate_client,
        embedding_provider=embedding_provider,
    )

    WeaviateSchemaManager(weaviate_client).ensure_collection_exists("TheLethe")
    ingestor.ingest_pdfs()

    collection = weaviate_client.collections.get("TheLethe")
    objs = collection.query.fetch_objects(limit=10)
    assert objs.objects, "No objects stored in TheLethe"
    props = objs.objects[0].properties
    assert props.get("sourcePath", "").endswith(".pdf")
    assert "body" in props or "text" in props
