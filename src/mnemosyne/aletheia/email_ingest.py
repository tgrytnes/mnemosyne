"""Email ingestion into Weaviate (The Lethe) for Story 024."""

from __future__ import annotations

import csv
import hashlib
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from weaviate.classes.config import DataType, Property

from mnemosyne.aletheia.email_cleaner import clean_email_body, contains_mojibake, truncate_body
from mnemosyne.alexandria.weaviate_schema import WeaviateSchemaManager


@dataclass
class EmailIngestConfig:
    tsv_path: Path
    max_chars: int = 8000
    min_body_chars: int = 20
    collection_name: str = "TheLethe"
    dedup: bool = True


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
    ) -> None:
        self.config = config
        self.client = weaviate_client
        self.embedder = embedder
        WeaviateSchemaManager(self.client).ensure_collection_exists(config.collection_name)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        collection = self.client.collections.get(self.config.collection_name)
        try:
            existing = {p.name for p in collection.config.get().properties}
        except Exception:
            existing = set()
        needed = {
            "subject": "text",
            "body": "text",
            "sender": "text",
            "date": "text",
            "clusterId": "int",
            "keywords": "text[]",
            "type": "text",
            "messageId": "text",
            "sourcePath": "text",
        }
        for name, dtype in needed.items():
            if name in existing:
                continue
            dt = DataType.TEXT
            if dtype == "int":
                dt = DataType.INT
            if dtype == "text[]":
                dt = getattr(DataType, "TEXT_ARRAY", DataType.TEXT)
            collection.config.add_property(Property(name=name, data_type=dt))

    def run(self) -> IngestSummary:
        collection = self.client.collections.get(self.config.collection_name)
        seen_ids: set[str] = set()
        total_loaded = 0
        total_stored = 0
        duplicates = 0
        rejected = 0

        for email in self._load_tsv(self.config.tsv_path):
            total_loaded += 1
            if contains_mojibake(email["body"]):
                rejected += 1
                continue
            body = truncate_body(email["body"], max_chars=self.config.max_chars)
            if len(body.strip()) < self.config.min_body_chars:
                rejected += 1
                continue

            msg_id = email.get("message_id") or ""
            stable = msg_id or hashlib.sha256(f"{email['subject']}{body}".encode()).hexdigest()
            if self.config.dedup and stable in seen_ids:
                duplicates += 1
                continue
            seen_ids.add(stable)

            vec = self.embedder(body)
            props = {
                "subject": email["subject"],
                "body": body,
                "sender": email.get("sender"),
                "date": email.get("date"),
                "clusterId": -1,
                "keywords": [],
                "type": "unknown",
                "messageId": msg_id or stable,
                "sourcePath": email.get("source") or "",
            }
            collection.data.insert(properties=props, vector=vec)
            total_stored += 1

        return IngestSummary(
            total_loaded=total_loaded,
            total_stored=total_stored,
            duplicates=duplicates,
            rejected=rejected,
        )

    def cluster_and_label(self) -> list[dict]:
        collection = self.client.collections.get(self.config.collection_name)
        objs = collection.query.fetch_objects(limit=100)
        if not objs.objects:
            return []
        return [{"id": obj.uuid, "keywords": []} for obj in objs.objects]

    def _load_tsv(self, path: Path) -> Iterable[dict]:
        with path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                subject = row.get("subject", "") or ""
                body_raw = row.get("body", "") or ""
                source = row.get("source", "") or ""
                message_id = row.get("message_id", "") or ""
                date = row.get("date", "") or ""
                cleaned_body = clean_email_body(body_raw)
                yield {
                    "subject": subject,
                    "body": cleaned_body,
                    "source": source,
                    "message_id": message_id,
                    "date": date,
                }


def main():
    """CLI entry point for email ingestion."""
    import logging
    import os
    import sys

    import ollama
    import weaviate

    # Configure logging
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger(__name__)

    # Get configuration from environment
    email_tsv = os.getenv("EMAIL_TSV")
    if not email_tsv:
        logger.error("EMAIL_TSV environment variable not set")
        sys.exit(1)

    weaviate_host = os.getenv("WEAVIATE_HTTP_HOST", "localhost")
    weaviate_port = int(os.getenv("WEAVIATE_HTTP_PORT", "8080"))
    weaviate_grpc_port = int(os.getenv("WEAVIATE_GRPC_PORT", "50051"))
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    embedding_model = os.getenv("OLLAMA_EMBEDDING_MODEL", "qwen3-embedding:0.6b")

    logger.info("=" * 60)
    logger.info("Email Ingestion Pipeline")
    logger.info("=" * 60)
    logger.info(f"Email TSV: {email_tsv}")
    logger.info(f"Weaviate: {weaviate_host}:{weaviate_port}")
    logger.info(f"Ollama: {ollama_url}")
    logger.info(f"Embedding Model: {embedding_model}")
    logger.info("=" * 60)

    # Connect to services
    logger.info("Connecting to Weaviate...")
    weaviate_client = weaviate.connect_to_local(
        host=weaviate_host,
        port=weaviate_port,
        grpc_port=weaviate_grpc_port,
    )

    logger.info("Connecting to Ollama...")
    ollama_client = ollama.Client(host=ollama_url)

    # Create embedder function
    def embedder(text: str) -> list[float]:
        """Generate embedding using Ollama."""
        response = ollama_client.embeddings(model=embedding_model, prompt=text)
        return response["embedding"]

    # Create config and ingestor
    config = EmailIngestConfig(tsv_path=Path(email_tsv))

    logger.info("Starting email ingestion...")
    ingestor = EmailIngestor(config=config, weaviate_client=weaviate_client, embedder=embedder)

    try:
        summary = ingestor.run()
        logger.info("=" * 60)
        logger.info("Email Ingestion Complete!")
        logger.info("=" * 60)
        logger.info(f"Total loaded: {summary.total_loaded}")
        logger.info(f"Total stored: {summary.total_stored}")
        logger.info(f"Duplicates: {summary.duplicates}")
        logger.info(f"Rejected: {summary.rejected}")
        logger.info("=" * 60)
    except Exception as e:
        logger.error(f"Error during email ingestion: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        weaviate_client.close()


if __name__ == "__main__":
    main()
