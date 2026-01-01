"""
PDF and OCR ingestion pipeline for Story 026.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import tempfile
from glob import glob
from pathlib import Path
from typing import Callable, Dict, List

from mnemosyne.alexandria.weaviate_schema import WeaviateSchemaManager

logger = logging.getLogger(__name__)


class PDFIngestor:
    """
    PDF and OCR ingestion pipeline.
    Uses: PyPDF2, OCRmyPDF (if available), optional embedder callable.
    """

    def __init__(self, input_dir: str, weaviate_client, embedder: Callable[[str], List[float]]):
        self.input_dir = input_dir
        self.client = weaviate_client
        self.embedder = embedder
        if self.client is not None:
            WeaviateSchemaManager(self.client).ensure_collection_exists("TheLethe")

    # ---------------------- Public API ---------------------- #

    def ingest_pdfs(self) -> None:
        pdf_files = glob(os.path.join(self.input_dir, "**", "*.pdf"), recursive=True)
        if not pdf_files:
            logger.info("No PDFs found in %s", self.input_dir)
            return

        collection = self.client.collections.get("TheLethe")

        for pdf_path in pdf_files:
            pdf_path = Path(pdf_path)
            try:
                text = self._extract_text(pdf_path)
            except Exception as exc:
                logger.warning("Failed to extract %s: %s", pdf_path, exc)
                continue

            cleaned = self.clean_text(text)
            if not cleaned:
                logger.info("No text extracted from %s", pdf_path)
                continue

            chunks = self.chunk_text(cleaned, chunk_size=500)
            metadata = self.extract_metadata(pdf_path)
            for idx, chunk in enumerate(chunks):
                vector = self._safe_embed(chunk)
                props = {
                    "body": chunk,
                    "sourcePath": str(pdf_path),
                    "type": "pdf",
                    "documentType": "pdf",
                    "pageNumber": metadata.get("page_number", 1),
                    "creationDate": metadata.get("creation_date", ""),
                    "messageId": metadata.get("stable_id", f"{pdf_path.name}-{idx}"),
                    "clusterId": -1,
                    "keywords": [],
                }
                collection.data.insert(properties=props, vector=vector)

    # ---------------------- Extraction ---------------------- #

    def _extract_text(self, pdf_path: Path) -> str:
        if self.is_text_pdf(str(pdf_path)):
            return self.extract_text_pdf(pdf_path)
        return self.extract_ocr_pdf(pdf_path)

    def is_text_pdf(self, pdf_path: str) -> bool:
        try:
            text = self._extract_first_page_text(pdf_path)
            return len(text.strip()) > 0
        except Exception:
            return False

    def extract_text_pdf(self, pdf_path: Path) -> str:
        try:
            with open(pdf_path, "rb") as f:
                reader = self._load_pypdf2().PdfReader(f)
                texts = []
                for page in reader.pages:
                    txt = page.extract_text() or ""
                    texts.append(txt)
                return "\n".join(texts)
        except Exception as exc:
            logger.warning("PyPDF2 extraction failed for %s: %s", pdf_path, exc)
            return ""

    def extract_ocr_pdf(self, pdf_path: Path) -> str:
        try:
            import ocrmypdf
        except ImportError:
            logger.warning("ocrmypdf not installed; returning empty OCR text")
            return ""

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            output_path = tmp.name
        try:
            ocrmypdf.ocr(
                str(pdf_path),
                output_path,
                language=["eng", "deu", "nor"],
                deskew=True,
                optimize=1,
                force_ocr=True,
                skip_text=False,
            )
            return self.extract_text_pdf(Path(output_path))
        finally:
            try:
                os.remove(output_path)
            except FileNotFoundError:
                pass

    # ---------------------- Cleaning & Chunking ---------------------- #

    def clean_text(self, text: str) -> str:
        text = text or ""
        text = re.sub(r"[^\w\s.,!?;:()\-\'\"€$%&/]", " ", text)
        ocr_corrections = {
            r"\bl\b": "I",
            r"\bO\b": "0",
            "–": "-",
            "’": "'",
            "“": '"',
            "”": '"',
        }
        for pattern, replacement in ocr_corrections.items():
            text = re.sub(pattern, replacement, text)
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"\n\d{1,3}\n", "\n", text)
        text = re.sub(r"Page\s+\d+", " ", text, flags=re.IGNORECASE)
        return text.strip()

    def chunk_text(self, text: str, chunk_size: int = 500) -> List[str]:
        words = text.split()
        chunks = []
        current = []
        for word in words:
            current.append(word)
            if len(current) >= chunk_size:
                chunks.append(" ".join(current))
                current = []
        if current:
            chunks.append(" ".join(current))
        return chunks if chunks else [text]

    # ---------------------- Metadata ---------------------- #

    def extract_metadata(self, pdf_path: Path) -> Dict:
        data: Dict = {}
        try:
            with open(pdf_path, "rb") as f:
                reader = self._load_pypdf2().PdfReader(f)
                meta = reader.metadata or {}
                data["title"] = meta.get("/Title", "")
                data["author"] = meta.get("/Author", "")
                data["creation_date"] = meta.get("/CreationDate", "")
                data["page_count"] = len(reader.pages)
        except Exception as exc:
            logger.warning("Metadata extraction failed for %s: %s", pdf_path, exc)
        data["page_number"] = data.get("page_count", 1)
        stable = hashlib.sha256(str(pdf_path).encode("utf-8")).hexdigest()
        data["stable_id"] = stable
        return data

    # ---------------------- Helpers ---------------------- #

    def _safe_embed(self, text: str) -> List[float]:
        try:
            return self.embedder(text)
        except Exception as exc:
            logger.warning("Embedding failed, returning zero vector: %s", exc)
            return []

    # ---------------------- Internal helpers ---------------------- #

    def _load_pypdf2(self):
        import importlib

        return importlib.import_module("PyPDF2")

    def _extract_first_page_text(self, pdf_path: str) -> str:
        with open(pdf_path, "rb") as f:
            reader = self._load_pypdf2().PdfReader(f)
            if not reader.pages:
                return ""
            return reader.pages[0].extract_text() or ""
