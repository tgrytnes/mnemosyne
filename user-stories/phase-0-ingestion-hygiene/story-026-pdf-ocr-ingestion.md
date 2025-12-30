# Story 026: PDF & OCR Document Ingestion

**As a** user with scanned documents and PDFs
**I want** text extracted via OCR and stored in my knowledge base
**So that** scanned papers, receipts, and PDFs are searchable alongside my notes

## Acceptance Criteria
- [ ] Accepts PDF files from designated directory
- [ ] Detects if PDF is text-based or image-based
- [ ] Text PDFs: Extract text directly (fast)
- [ ] Image PDFs: Apply OCR using OCRmyPDF
- [ ] Multi-language OCR support (EN, DE, NO)
- [ ] Extracted text cleaned and normalized
- [ ] Chunks embedded and stored in Weaviate (The Lethe - Archive)
- [ ] Preserves metadata: filename, page numbers, creation date
- [ ] Handles batch processing of 100+ PDFs
- [ ] Performance: <30 seconds per text PDF, <2 minutes per scanned PDF

## Technical Notes

### Architecture (Based on Aletheia README)

```python
class PDFIngestor:
    """
    PDF and OCR ingestion pipeline
    Uses: Tika, OCRmyPDF, Unstructured.io
    """
    def __init__(self, input_dir: str, weaviate_client: Client):
        self.input_dir = input_dir
        self.client = weaviate_client
        self.collection_name = "TheLethe"  # Archive

    def ingest_pdfs(self):
        pdf_files = glob(f"{self.input_dir}/**/*.pdf", recursive=True)

        for pdf_path in pdf_files:
            print(f"Processing: {os.path.basename(pdf_path)}")

            # 1. Detect PDF type
            if self.is_text_pdf(pdf_path):
                text = self.extract_text_pdf(pdf_path)
            else:
                text = self.extract_ocr_pdf(pdf_path)

            # 2. Clean extracted text
            cleaned = self.clean_text(text)

            # 3. Chunk
            chunks = self.chunk_text(cleaned, chunk_size=500)

            # 4. Embed and store
            for idx, chunk in enumerate(chunks):
                embedding = self.get_embedding(chunk)

                self.store_chunk({
                    "text": chunk,
                    "source_file": pdf_path,
                    "page_number": None,  # TODO: extract from metadata
                    "chunk_index": idx,
                    "document_type": "pdf",
                    "vector": embedding
                })

    def is_text_pdf(self, pdf_path: str) -> bool:
        """
        Detect if PDF has extractable text layers
        """
        try:
            import PyPDF2
            with open(pdf_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                first_page = reader.pages[0]
                text = first_page.extract_text()
                return len(text.strip()) > 50  # Threshold
        except Exception:
            return False  # Assume image PDF if detection fails
```

### Text PDF Extraction (Tika)

```python
def extract_text_pdf(self, pdf_path: str) -> str:
    """
    Extract text from text-based PDFs using Apache Tika
    """
    from tika import parser

    parsed = parser.from_file(pdf_path)
    text = parsed.get('content', '')

    return text.strip()
```

### OCR Extraction (OCRmyPDF)

```python
def extract_ocr_pdf(self, pdf_path: str) -> str:
    """
    Apply OCR to scanned PDFs using OCRmyPDF
    """
    import ocrmypdf
    import tempfile

    # Create temp file for OCR output
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
        output_path = tmp.name

    # Run OCR
    ocrmypdf.ocr(
        pdf_path,
        output_path,
        language=['eng', 'deu', 'nor'],  # EN, DE, NO
        deskew=True,
        optimize=1,
        force_ocr=True,
        skip_text=False
    )

    # Extract text from OCR'd PDF
    text = self.extract_text_pdf(output_path)

    # Cleanup
    os.remove(output_path)

    return text
```

### Alternative: Unstructured.io

```python
def extract_with_unstructured(self, pdf_path: str) -> str:
    """
    Use unstructured.io for advanced PDF parsing
    Handles tables, images, complex layouts
    """
    from unstructured.partition.pdf import partition_pdf

    elements = partition_pdf(
        filename=pdf_path,
        strategy="hi_res",  # High resolution for scanned docs
        languages=["eng", "deu", "nor"]
    )

    # Combine all text elements
    text = "\n\n".join([str(el) for el in elements])

    return text
```

### Text Cleaning

```python
def clean_text(self, text: str) -> str:
    """
    Clean OCR artifacts and normalize text
    """
    # Remove OCR noise
    text = re.sub(r'[^\w\s.,!?;:()\-\'"€$%&/]', '', text)

    # Fix common OCR errors
    ocr_corrections = {
        r'\bl\b': 'I',  # lowercase L mistaken for I
        r'\bO\b': '0',  # capital O mistaken for zero (context-dependent)
        r'–': '-',      # em dash to regular dash
        r''': "'",      # smart quotes to regular
    }
    for pattern, replacement in ocr_corrections.items():
        text = re.sub(pattern, replacement, text)

    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)

    # Remove page numbers (heuristic: standalone numbers)
    text = re.sub(r'\n\d{1,3}\n', '\n', text)

    return text.strip()
```

### Metadata Extraction

```python
def extract_metadata(self, pdf_path: str) -> Dict:
    """
    Extract PDF metadata (author, title, dates)
    """
    import PyPDF2

    with open(pdf_path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        metadata = reader.metadata

        return {
            "title": metadata.get('/Title', ''),
            "author": metadata.get('/Author', ''),
            "subject": metadata.get('/Subject', ''),
            "creation_date": metadata.get('/CreationDate', ''),
            "page_count": len(reader.pages)
        }
```

### Weaviate Schema Extension

```python
# Extend TheLethe schema with document type
schema_extension = {
    "properties": [
        {
            "name": "documentType",
            "dataType": ["text"],
            "description": "Type: pdf, email, note, etc."
        },
        {
            "name": "pageNumber",
            "dataType": ["int"],
            "description": "Page number in source document"
        },
        {
            "name": "pdfMetadata",
            "dataType": ["object"],
            "description": "PDF metadata (title, author, etc.)"
        }
    ]
}
```

### Docker Integration (OCRmyPDF)

```dockerfile
# Aletheia Dockerfile
FROM python:3.11-slim

# Install OCR dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-deu \
    tesseract-ocr-nor \
    ghostscript \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip install \
    ocrmypdf \
    PyPDF2 \
    apache-tika \
    unstructured[pdf] \
    weaviate-client \
    langchain

WORKDIR /app
COPY . .

CMD ["python", "-m", "aletheia.pdf_ingestor"]
```

### Batch Processing Strategy

```python
def batch_process(self, batch_size: int = 10):
    """
    Process PDFs in batches to avoid memory issues
    """
    pdf_files = glob(f"{self.input_dir}/**/*.pdf", recursive=True)

    for i in range(0, len(pdf_files), batch_size):
        batch = pdf_files[i:i+batch_size]

        print(f"Processing batch {i//batch_size + 1} ({len(batch)} files)")

        for pdf_path in batch:
            try:
                self.ingest_pdf(pdf_path)
            except Exception as e:
                log_error(f"Failed to process {pdf_path}: {e}")
                continue

        # Garbage collection to free memory
        import gc
        gc.collect()
```

### Quality Assurance

```python
def validate_extraction(self, text: str, pdf_path: str) -> bool:
    """
    Check if OCR quality is acceptable
    """
    # Check minimum length
    if len(text) < 100:
        log_warning(f"Low text extraction for {pdf_path}: {len(text)} chars")
        return False

    # Check for excessive gibberish (OCR artifacts)
    words = text.split()
    valid_words = sum(1 for word in words if word.isalpha() and len(word) > 2)
    gibberish_ratio = 1 - (valid_words / max(len(words), 1))

    if gibberish_ratio > 0.5:
        log_warning(f"High gibberish ratio for {pdf_path}: {gibberish_ratio:.2f}")
        return False

    return True
```

### Performance Optimization

```python
# Parallel processing for large batches
from concurrent.futures import ProcessPoolExecutor

def parallel_ingest(self, pdf_files: List[str], workers: int = 4):
    """
    Process multiple PDFs in parallel
    """
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(self.ingest_pdf, pdf) for pdf in pdf_files]

        for future in futures:
            try:
                future.result()
            except Exception as e:
                log_error(f"Parallel processing error: {e}")
```

### Usage Example

```python
# docker-compose.yml
services:
  aletheia-pdf:
    build: ./Aletheia
    volumes:
      - /path/to/pdfs:/data/pdfs:ro
      - ./data/weaviate:/weaviate-data
    environment:
      PDF_INPUT_DIR: /data/pdfs
      WEAVIATE_URL: http://weaviate:8080
      OLLAMA_URL: http://ollama:11434
      OCR_LANGUAGES: eng,deu,nor
```

### Dependencies
- Apache Tika or PyPDF2 for text extraction
- OCRmyPDF with Tesseract (eng, deu, nor language packs)
- Unstructured.io (optional, advanced parsing)
- Ollama for embeddings
- Weaviate (The Lethe collection)

## Affected Components
- **Aletheia**: PDF/OCR ingestion pipeline
- **Alexandria**: The Lethe (archive storage)

## Priority
**Medium** - Important for document archives, not blocking MVP

## Estimate
8 story points (5-8 days)

## Linear Labels
`phase-0`, `ingestion`, `pdf`, `ocr`, `aletheia`

## Related Stories
- Story 000: Obsidian Vault Ingestion (similar embedding workflow)
- Story 024: Email Archive Ingestion (similar cleaning pipeline)
- Aletheia README mentions Tika, OCRmyPDF, Unstructured.io

## References
- Aletheia README: Cleaning Stack (OCR, PDF-to-Text)
- OCRmyPDF: https://ocrmypdf.readthedocs.io/
- Apache Tika: https://tika.apache.org/
- Unstructured.io: https://unstructured.io/
