"""
Integration test for Story 026: OCR path for scanned PDFs.
Requires OCRmyPDF, Weaviate, and Ollama running.
"""

import shutil
from pathlib import Path

import pytest

# Skip entire module if ocrmypdf is not available
# Note: ocrmypdf may fail to import if leptonica/tesseract are not installed
try:
    import ocrmypdf # noqa: F401
except (ImportError, Exception) as e:
    pytest.skip(f"ocrmypdf not available: {e}", allow_module_level=True)


@pytest.mark.integration
@pytest.mark.weaviate
@pytest.mark.ollama
def test_ocr_pdf_ingestion(tmp_path, weaviate_client, ollama_client):
    from mnemosyne.aletheia.pdf_ingestor import PDFIngestor  # to be implemented
    from mnemosyne.alexandria.weaviate_schema import WeaviateSchemaManager

    # Use a sample scanned PDF (place one in test_data/fake_pdfs)
    scanned_pdf = tmp_path / "scanned.pdf"
    src_pdf = (
        Path(__file__).resolve().parents[3] / "test_data" / "fake_pdfs" / "doc_12_scan_log.pdf"
    )
    shutil.copy(src_pdf, scanned_pdf)

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
    assert objs.objects, "No objects stored in TheLethe"
    props = objs.objects[0].properties
    assert props.get("sourcePath", "").endswith(".pdf")
    assert props.get("documentType") == "pdf"
