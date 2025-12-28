#!/usr/bin/env python3
"""
Seed Weaviate with fake Obsidian vault data using Ollama embeddings.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import ollama
import weaviate

from mnemosyne.alexandria.weaviate_schema import WeaviateSchemaManager
from mnemosyne.aletheia.ingestion_state import IngestionStateTracker
from mnemosyne.aletheia.obsidian_ingestor import ObsidianIngestor


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def main() -> int:
    vault_path = os.getenv("TEST_VAULT_PATH", "test_data/fake_vault")
    weaviate_host = os.getenv("WEAVIATE_HTTP_HOST", "localhost")
    weaviate_port = _env_int("WEAVIATE_HTTP_PORT", 8080)
    weaviate_grpc_port = _env_int("WEAVIATE_GRPC_PORT", 50051)
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    state_db_path = os.getenv("INGESTION_STATE_DB", "/tmp/ingestion_state_test.db")
    chunk_size = _env_int("CHUNK_SIZE", 400)
    chunk_overlap = _env_int("CHUNK_OVERLAP", 100)
    reset_collection = os.getenv("RESET_COLLECTION", "true").lower() in {"1", "true", "yes"}

    vault = Path(vault_path)
    if not vault.exists() or not vault.is_dir():
        print(f"Vault path not found: {vault_path}", file=sys.stderr)
        return 1

    weaviate_client = weaviate.connect_to_custom(
        http_host=weaviate_host,
        http_port=weaviate_port,
        http_secure=False,
        grpc_host=weaviate_host,
        grpc_port=weaviate_grpc_port,
        grpc_secure=False,
    )

    if not weaviate_client.is_ready():
        print("Weaviate is not ready", file=sys.stderr)
        return 1

    if reset_collection and weaviate_client.collections.exists("TheMuses"):
        weaviate_client.collections.delete("TheMuses")

    schema_manager = WeaviateSchemaManager(weaviate_client)
    schema_manager.ensure_collection_exists("TheMuses")

    ollama_client = ollama.Client(host=ollama_url)
    state_tracker = IngestionStateTracker(state_db_path)

    ingestor = ObsidianIngestor(
        vault_path=str(vault),
        weaviate_client=weaviate_client,
        ollama_client=ollama_client,
        state_tracker=state_tracker,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    stats = ingestor.ingest_vault()
    print(
        f"Seeded TheMuses with {stats['total_chunks']} chunks from {stats['files_processed']} files"
    )

    state_tracker.close()
    weaviate_client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
