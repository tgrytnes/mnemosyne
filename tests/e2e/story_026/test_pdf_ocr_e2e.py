"""
E2E test for Story 026: mixed PDF ingestion (text + scanned) end-to-end.
Requires Weaviate + Ollama + OCRmyPDF.
"""

import shutil
from pathlib import Path

import pytest

# Skip entire module if ocrmypdf is not available
# Note: ocrmypdf may fail to import if leptonica/tesseract are not installed
try:
    import ocrmypdf
except (ImportError, Exception) as e:
    pytest.skip(f"ocrmypdf not available: {e}", allow_module_level=True)


@pytest.mark.e2e
@pytest.mark.weaviate
@pytest.mark.ollama
def test_mixed_pdf_ingestion_end_to_end(tmp_path, weaviate_client, ollama_client):
    """
    Flow:
    - Place mixed PDFs (text + scanned) in input dir
    - Run ingest_pdfs
    - Verify TheLethe contains chunks with metadata (filename, page_number, creation_date)
    """
    from mnemosyne.aletheia.pdf_ingestor import PDFIngestor  # to be implemented
    from mnemosyne.alexandria.weaviate_schema import WeaviateSchemaManager

    # Copy mixed PDFs from test_data
    src_dir = Path(__file__).resolve().parents[4] / "test_data" / "fake_pdfs"
    for name in ["doc_01_project_brief.pdf", "doc_12_scan_log.pdf"]:
        shutil.copy(src_dir / name, tmp_path / name)

    ingestor = PDFIngestor(
        input_dir=str(tmp_path),
        weaviate_client=weaviate_client,
        embedder=lambda txt: ollama_client.embeddings(model="qwen3-embedding:0.6b", prompt=txt)[
            "embedding"
        ],
    )

    WeaviateSchemaManager(weaviate_client).ensure_collection_exists("TheLethe")
    ingestor.ingest_pdfs()

    collection = weaviate_client.collections.get("TheLethe")
    objs = collection.query.fetch_objects(limit=10)
    assert len(objs.objects) >= 2
    for obj in objs.objects:
        props = obj.properties
        assert props.get("sourcePath", "").endswith(".pdf")
        assert props.get("pageNumber") is not None or props.get("page_number") is not None
        assert props.get("documentType") == "pdf"
        assert props.get("creationDate") is not None or props.get("creation_date") is not None
