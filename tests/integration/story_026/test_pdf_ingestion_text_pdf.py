"""
Integration test for Story 026: text-based PDF ingestion.
Requires Weaviate and Ollama running.
"""

import pytest
from pathlib import Path
import shutil


@pytest.mark.integration
@pytest.mark.weaviate
@pytest.mark.ollama
def test_text_pdf_ingestion_to_thelethe(tmp_path, weaviate_client, ollama_client):
    from mnemosyne.aletheia.pdf_ingestor import PDFIngestor  # to be implemented
    from mnemosyne.alexandria.weaviate_schema import WeaviateSchemaManager

    # Prepare a simple text PDF
    sample_pdf = tmp_path / "sample.pdf"
    src_pdf = (Path(__file__).parent / "../../test_data/fake_pdfs/doc_01_project_brief.pdf").resolve()
    shutil.copy(src_pdf, sample_pdf)

    cfg_dir = tmp_path
    ingestor = PDFIngestor(input_dir=str(cfg_dir), weaviate_client=weaviate_client, embedder=lambda txt: ollama_client.embeddings(model="qwen3-embedding:0.6b", prompt=txt)["embedding"])

    WeaviateSchemaManager(weaviate_client).ensure_collection_exists("TheLethe")
    ingestor.ingest_pdfs()

    collection = weaviate_client.collections.get("TheLethe")
    objs = collection.query.fetch_objects(limit=10)
    assert objs.objects, "No objects stored in TheLethe"
    props = objs.objects[0].properties
    assert props.get("sourcePath", "").endswith(".pdf")
    assert "body" in props or "text" in props
