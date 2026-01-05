"""Raw email ingestion into Weaviate (TheLethe) for Story 031."""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from weaviate.classes.config import DataType, Property

from mnemosyne.aletheia.chunking_strategy_factory import (
    ChunkingStrategyConfig,
    ChunkingStrategyFactory,
)
from mnemosyne.aletheia.email_cleaner import contains_mojibake, truncate_body
from mnemosyne.aletheia.email_ingestion_state import EmailIngestionState
from mnemosyne.aletheia.email_parser import parse_eml_file, parse_mbox_file
from mnemosyne.aletheia.models import Email, EmailChunk
from mnemosyne.aletheia.text_chunker import TextChunker
from mnemosyne.alexandria.weaviate_schema import TheLethe, WeaviateSchemaManager

logger = logging.getLogger(__name__)


@dataclass
class EmailIngestConfig:
    source_dir: Path
    state_path: Path = Path("/state/email_ingestion_state.json")
    max_chars: int = 8000
    min_body_chars: int = 20
    collection_name: str = TheLethe.collection_name
    chunking_strategy: str = "semantic"
    chunk_size: int = 400
    chunk_overlap: int = 100
    semantic_min_chunk_size: int = 100
    semantic_max_chunk_size: int = 1000
    semantic_model: str = "gemma3:1b"
    semantic_temperature: float = 0.2
    semantic_request_timeout: float = 5.0
    semantic_total_timeout: float = 30.0
    section_semantic_min_length: int = 1000

    @classmethod
    def from_env(cls) -> EmailIngestConfig:
        if os.getenv("EMAIL_TSV"):
            raise ValueError("EMAIL_TSV is no longer supported; use SOURCE_DIR instead")

        source_dir = os.getenv("SOURCE_DIR")
        if not source_dir:
            raise ValueError("SOURCE_DIR environment variable not set")

        return cls(
            source_dir=Path(source_dir),
            state_path=Path(
                os.getenv("EMAIL_INGESTION_STATE_PATH", "/state/email_ingestion_state.json")
            ),
            max_chars=int(os.getenv("EMAIL_MAX_CHARS", "8000")),
            min_body_chars=int(os.getenv("EMAIL_MIN_BODY_CHARS", "20")),
            collection_name=os.getenv("EMAIL_COLLECTION_NAME", TheLethe.collection_name),
            chunking_strategy=os.getenv("CHUNKING_STRATEGY", "semantic"),
            chunk_size=int(os.getenv("CHUNK_SIZE", "400")),
            chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "100")),
            semantic_min_chunk_size=int(os.getenv("SEMANTIC_MIN_CHUNK_SIZE", "100")),
            semantic_max_chunk_size=int(os.getenv("SEMANTIC_MAX_CHUNK_SIZE", "1000")),
            semantic_model=os.getenv("SEMANTIC_LLM_MODEL", "gemma3:1b"),
            semantic_temperature=float(os.getenv("SEMANTIC_TEMPERATURE", "0.2")),
            semantic_request_timeout=float(os.getenv("SEMANTIC_REQUEST_TIMEOUT", "5.0")),
            semantic_total_timeout=float(os.getenv("SEMANTIC_TOTAL_TIMEOUT", "30.0")),
            section_semantic_min_length=int(os.getenv("SECTION_SEMANTIC_MIN_LENGTH", "1000")),
        )


@dataclass
class IngestSummary:
    total_loaded: int
    total_stored: int
    duplicates: int
    rejected: int


class EmailIngestor:
    def __init__(
        self,
        config: EmailIngestConfig,
        weaviate_client,
        embedder: Callable[[str], list[float]],
        ollama_client=None,
    ) -> None:
        self.config = config
        self.client = weaviate_client
        self.embedder = embedder
        self.ollama_client = ollama_client
        self.state = EmailIngestionState(config.state_path)

        WeaviateSchemaManager(self.client).ensure_collection_exists(config.collection_name)
        self._ensure_schema()
        self.chunker = self._build_chunker()

    def _build_chunker(self):
        strategy = (self.config.chunking_strategy or "semantic").lower()
        recursive = TextChunker(
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
        )

        if strategy == "recursive":
            return recursive

        if self.ollama_client is None:
            raise ValueError("ollama_client is required for semantic or hybrid chunking")

        factory = ChunkingStrategyFactory(self.ollama_client, state_tracker=None)
        cfg = ChunkingStrategyConfig(
            strategy=strategy,
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
            semantic_min_chunk_size=self.config.semantic_min_chunk_size,
            semantic_max_chunk_size=self.config.semantic_max_chunk_size,
            semantic_model=self.config.semantic_model,
            semantic_temperature=self.config.semantic_temperature,
            semantic_request_timeout=self.config.semantic_request_timeout,
            semantic_total_timeout=self.config.semantic_total_timeout,
            section_semantic_min_length=self.config.section_semantic_min_length,
        )
        return factory.create(cfg, recursive_chunker=recursive)

    def _ensure_schema(self) -> None:
        collection = self.client.collections.get(self.config.collection_name)
        try:
            existing = {p.name for p in collection.config.get().properties}
        except Exception:
            existing = set()

        for prop in TheLethe.properties:
            name = prop["name"]
            if name in existing:
                continue
            dtype = prop["dataType"][0]
            if dtype == "int":
                data_type = DataType.INT
            elif dtype == "text[]":
                data_type = getattr(DataType, "TEXT_ARRAY", DataType.TEXT)
            elif dtype == "date":
                data_type = DataType.DATE
            else:
                data_type = DataType.TEXT
            collection.config.add_property(Property(name=name, data_type=data_type))

    def run(self) -> IngestSummary:
        collection = self.client.collections.get(self.config.collection_name)

        total_loaded = 0
        total_stored = 0
        duplicates = 0
        rejected = 0

        for email in self._iter_emails(self.config.source_dir):
            total_loaded += 1

            body = truncate_body(email.body, max_chars=self.config.max_chars)
            if contains_mojibake(body) or len(body.strip()) < self.config.min_body_chars:
                rejected += 1
                continue

            if self.state.is_ingested(email.unique_id):
                duplicates += 1
                continue

            chunks = self.chunker.chunk(body, source_file=email.source_path)
            if not chunks:
                rejected += 1
                continue

            for chunk in chunks:
                if not chunk.text.strip():
                    continue
                chunk_item = EmailChunk(
                    parent_email_unique_id=email.unique_id,
                    chunk_text=chunk.text,
                    chunk_index=chunk.index,
                    parent_subject=email.subject,
                    parent_sender=email.sender,
                    parent_date=email.date,
                    parent_source_path=email.source_path,
                )

                vec = self.embedder(chunk_item.chunk_text)
                props = {
                    "subject": chunk_item.parent_subject,
                    "body": chunk_item.chunk_text,
                    "sender": chunk_item.parent_sender,
                    "date": chunk_item.parent_date,
                    "clusterId": -1,
                    "keywords": [],
                    "type": "email",
                    "messageId": email.message_id or email.unique_id,
                    "sourcePath": chunk_item.parent_source_path,
                    "documentType": chunk_item.document_type,
                    "chunkIndex": chunk_item.chunk_index,
                }
                collection.data.insert(properties=props, vector=vec)
                total_stored += 1

            self.state.mark_ingested(email.unique_id)
            self.state.save()

        return IngestSummary(
            total_loaded=total_loaded,
            total_stored=total_stored,
            duplicates=duplicates,
            rejected=rejected,
        )

    def cluster_and_label(self) -> list[dict]:
        return []

    def _iter_emails(self, source_dir: Path) -> Iterable[Email]:
        for path in sorted(source_dir.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() == ".eml":
                email = parse_eml_file(path)
                if email:
                    yield email
            elif path.suffix.lower() == ".mbox":
                yield from parse_mbox_file(path)


def main() -> None:
    """CLI entry point for email ingestion."""
    import ollama
    import weaviate

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    try:
        config = EmailIngestConfig.from_env()
    except ValueError as exc:
        logger.error("%s", exc)
        sys.exit(1)

    weaviate_host = os.getenv("WEAVIATE_HTTP_HOST", "localhost")
    weaviate_port = int(os.getenv("WEAVIATE_HTTP_PORT", "8080"))
    weaviate_grpc_port = int(os.getenv("WEAVIATE_GRPC_PORT", "50051"))
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    embedding_model = os.getenv("OLLAMA_EMBEDDING_MODEL", "qwen3-embedding:0.6b")

    logger.info("=" * 60)
    logger.info("Email Ingestion Pipeline")
    logger.info("=" * 60)
    logger.info("Source dir: %s", config.source_dir)
    logger.info("State path: %s", config.state_path)
    logger.info("Weaviate: %s:%s", weaviate_host, weaviate_port)
    logger.info("Ollama: %s", ollama_url)
    logger.info("Embedding model: %s", embedding_model)
    logger.info("Chunking strategy: %s", config.chunking_strategy)
    logger.info("=" * 60)

    weaviate_client = weaviate.connect_to_local(
        host=weaviate_host,
        port=weaviate_port,
        grpc_port=weaviate_grpc_port,
    )
    ollama_client = ollama.Client(host=ollama_url)

    def embedder(text: str) -> list[float]:
        response = ollama_client.embeddings(model=embedding_model, prompt=text)
        return response["embedding"]

    ingestor = EmailIngestor(
        config=config,
        weaviate_client=weaviate_client,
        embedder=embedder,
        ollama_client=ollama_client,
    )

    try:
        summary = ingestor.run()
        logger.info("=" * 60)
        logger.info("Email ingestion complete")
        logger.info("Loaded: %s", summary.total_loaded)
        logger.info("Stored: %s", summary.total_stored)
        logger.info("Duplicates: %s", summary.duplicates)
        logger.info("Rejected: %s", summary.rejected)
        logger.info("=" * 60)
    except Exception as exc:
        logger.error("Error during email ingestion: %s", exc)
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        weaviate_client.close()


if __name__ == "__main__":
    main()
