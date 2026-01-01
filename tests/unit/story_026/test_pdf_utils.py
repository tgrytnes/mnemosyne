"""
Unit tests for Story 026: PDF/OCR ingestion utilities.
"""

class DummyPDFIngestor:
    """Minimal wrapper to call functions once implemented."""

    def __init__(self):
        from mnemosyne.aletheia.pdf_ingestor import PDFIngestor  # to be implemented

        self.ingestor = PDFIngestor(input_dir="", weaviate_client=None, embedder=lambda _: [])

    def clean_text(self, text: str) -> str:
        return self.ingestor.clean_text(text)

    def chunk_text(self, text: str, chunk_size: int = 500):
        return self.ingestor.chunk_text(text, chunk_size)

    def extract_metadata(self, pdf_path: str):
        return self.ingestor.extract_metadata(pdf_path)

    def is_text_pdf(self, pdf_path: str) -> bool:
        return self.ingestor.is_text_pdf(pdf_path)


def test_clean_text_removes_noise_and_normalizes():
    ingestor = DummyPDFIngestor()
    noisy = "Hęllo â€™ wor1d\n\nPage 1\n\n   "
    cleaned = ingestor.clean_text(noisy)
    assert "Hello" in cleaned or "Hęllo" in cleaned
    assert "Page 1" not in cleaned  # page number heuristics
    assert "  " not in cleaned


def test_chunk_text_respects_chunk_size():
    ingestor = DummyPDFIngestor()
    text = " ".join(["word"] * 1200)
    chunks = ingestor.chunk_text(text, chunk_size=200)
    assert len(chunks) > 1
    assert all(len(c.split()) <= 220 for c in chunks)  # allow small overlap


def test_is_text_pdf_detection(mocker, tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_text("fake")
    mocker.patch(
        "mnemosyne.aletheia.pdf_ingestor.PDFIngestor._extract_first_page_text",
        return_value="some text here",
    )
    ingestor = DummyPDFIngestor()
    assert ingestor.is_text_pdf(str(pdf_path)) is True
