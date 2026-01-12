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

import click

from mnemosyne.aletheia.pdf_ingestion_state import PDFIngestionState
from mnemosyne.alexandria.weaviate_schema import WeaviateSchemaManager
from mnemosyne.config.providers import ProviderConfig
from mnemosyne.providers.base import EmbeddingProvider
from mnemosyne.providers.factory import create_embedding_provider

logger = logging.getLogger(__name__)

DEFAULT_EMBED_DIM = 1536


class PDFIngestor:
    """
    PDF and OCR ingestion pipeline.
    Uses: PyPDF2, OCRmyPDF (if available), optional embedder callable.
    """

    def __init__(
        self,
        input_dir: str,
        weaviate_client,
        embedding_provider: EmbeddingProvider,
        state_path: str | Path | None = None,
    ):
        self.input_dir = input_dir
        self.client = weaviate_client
        self.embedding_provider = embedding_provider
        resolved_state_path = _resolve_pdf_state_path(state_path, self.input_dir)
        self.state = PDFIngestionState(resolved_state_path)
        if self.client is not None:
            WeaviateSchemaManager(self.client).ensure_collection_exists("TheLethe")

    # ---------------------- Public API ---------------------- #

    def ingest_pdfs(self) -> None:
        pdf_files = glob(os.path.join(self.input_dir, "**", "*.pdf"), recursive=True)
        if not pdf_files:
            logger.info("No PDFs found in %s", self.input_dir)
            return
        for pdf_path in pdf_files:
            self.ingest_file(pdf_path)

    def ingest_file(self, pdf_path: str | Path) -> int:
        path = Path(pdf_path)
        if not path.exists() or not path.is_file():
            return 0
        if path.suffix.lower() != ".pdf":
            return 0
        try:
            stat = path.stat()
        except OSError:
            return 0
        if self.state.is_ingested(
            str(path),
            mtime=stat.st_mtime,
            size=stat.st_size,
        ):
            logger.info("Skipping already ingested PDF: %s", path)
            return 0

        collection = self.client.collections.get("TheLethe")
        try:
            text = self._extract_text(path)
        except Exception as exc:
            logger.warning("Failed to extract %s: %s", path, exc)
            return 0
        raw_text = text or ""
        cleaned = self.clean_text(raw_text)
        # Fall back to raw text if cleaning removed everything
        if not cleaned and raw_text.strip():
            cleaned = raw_text.strip()
        if not cleaned:
            logger.info("No text extracted from %s", path)
            return 0

        chunks = self.chunk_text(cleaned, chunk_size=500)
        metadata = self.extract_metadata(path)
        inserted = 0
        for idx, chunk in enumerate(chunks):
            try:
                vector = self.embedding_provider.embed(model="", text=chunk)
            except Exception as exc:
                logger.error("Embedding failed for %s chunk %s: %s", path, idx, exc)
                continue
            if not vector:
                logger.error("Embedding empty for %s chunk %s", path, idx)
                continue
            props = {
                "body": chunk,
                "sourcePath": str(path),
                "type": "pdf",
                "documentType": "pdf",
                "pageNumber": metadata.get("page_number", 1),
                "creationDate": metadata.get("creation_date", ""),
                "messageId": metadata.get("stable_id", f"{path.name}-{idx}"),
                "clusterId": -1,
                "keywords": [],
            }
            collection.data.insert(properties=props, vector={"default": vector})
            inserted += 1

        if inserted:
            self.state.mark_ingested(
                str(path),
                mtime=stat.st_mtime,
                size=stat.st_size,
            )
            self.state.save()
        return len(chunks)

    # ---------------------- Extraction ---------------------- #

    def _extract_text(self, pdf_path: Path) -> str:
        text = ""
        if self.is_text_pdf(str(pdf_path)):
            text = self.extract_text_pdf(pdf_path)
        if not text:
            text = self.extract_ocr_pdf(pdf_path)
        if not text:
            text = self._binary_fallback(pdf_path)
        return text

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
            return self._binary_fallback(pdf_path)

    def extract_ocr_pdf(self, pdf_path: Path) -> str:
        import shutil
        import subprocess

        # Check if ocrmypdf command is available
        if not shutil.which("ocrmypdf"):
            logger.warning("ocrmypdf command not found; returning empty OCR text")
            return ""

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            output_path = tmp.name
        try:
            # Run ocrmypdf as a subprocess
            result = subprocess.run(
                [
                    "ocrmypdf",
                    "--language",
                    "eng+deu+nor",
                    "--deskew",
                    "--optimize",
                    "1",
                    "--force-ocr",
                    str(pdf_path),
                    output_path,
                ],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode != 0:
                logger.warning(
                    "ocrmypdf failed for %s: %s", pdf_path, result.stderr or result.stdout
                )
                return ""
            return self.extract_text_pdf(Path(output_path))
        except subprocess.TimeoutExpired:
            logger.warning("ocrmypdf timed out for %s", pdf_path)
            return ""
        except Exception as exc:
            logger.warning("ocrmypdf subprocess failed for %s: %s", pdf_path, exc)
            return ""
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

    def chunk_text(self, text: str, chunk_size: int = 500) -> list[str]:
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

    def extract_metadata(self, pdf_path: Path) -> dict:
        data: dict = {}
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

    def _binary_fallback(self, pdf_path: Path) -> str:
        """
        Fallback for malformed PDFs: decode raw bytes to salvage text.
        """
        try:
            data = pdf_path.read_bytes()
            return data.decode("latin-1", errors="ignore")
        except Exception:
            return ""


def _resolve_pdf_state_path(state_path: str | Path | None, input_dir: str) -> Path:
    if state_path:
        return Path(state_path)
    env_path = os.getenv("PDF_INGESTION_STATE_PATH")
    if env_path:
        return Path(env_path)
    default_path = Path("/state/pdf_ingestion_state.json")
    if default_path.parent.exists() and os.access(default_path.parent, os.W_OK):
        return default_path
    return Path(input_dir) / "pdf_ingestion_state.json"


@click.command("pdf-ingest")
def pdf_ingest_cli():
    """CLI entry point for PDF ingestion."""
    import sys

    import weaviate

    # Configure logging
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Get configuration from environment
    pdf_path = os.getenv("PDF_SCAN_PATH")
    if not pdf_path:
        logger.error("PDF_SCAN_PATH environment variable not set")
        sys.exit(1)

    weaviate_host = os.getenv("WEAVIATE_HTTP_HOST", "localhost")
    weaviate_port = int(os.getenv("WEAVIATE_HTTP_PORT", "8080"))
    weaviate_grpc_port = int(os.getenv("WEAVIATE_GRPC_PORT", "50051"))

    provider_config = ProviderConfig.from_env()

    logger.info("=" * 60)
    logger.info("PDF Ingestion Pipeline")
    logger.info("=" * 60)
    logger.info(f"PDF Path: {pdf_path}")
    logger.info(f"Weaviate: {weaviate_host}:{weaviate_port}")
    logger.info(f"Embedding Provider: {provider_config.embedding_provider}")
    logger.info("=" * 60)

    # Connect to services
    logger.info("Connecting to Weaviate...")
    weaviate_client = weaviate.connect_to_local(
        host=weaviate_host,
        port=weaviate_port,
        grpc_port=weaviate_grpc_port,
    )

    embedding_provider = create_embedding_provider(provider_config)

    # Create ingestor and run
    logger.info("Starting PDF ingestion...")
    ingestor = PDFIngestor(
        input_dir=pdf_path,
        weaviate_client=weaviate_client,
        embedding_provider=embedding_provider,
    )

    try:
        ingestor.ingest_pdfs()
        logger.info("=" * 60)
        logger.info("PDF Ingestion Complete!")
        logger.info("=" * 60)
    except Exception as e:
        logger.error(f"Error during PDF ingestion: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        weaviate_client.close()
