"""
Obsidian vault ingestor - Main orchestration class for Story 000.

Coordinates the complete ingestion pipeline:
1. Scan vault for markdown files
2. Clean Obsidian syntax
3. Chunk into embedding-sized pieces
4. Generate embeddings via Ollama
5. Store in Weaviate TheMuses collection
6. Track state in SQLite
"""

import logging
import os
from datetime import datetime
from glob import glob
from pathlib import Path
from typing import Any

from ..alexandria.weaviate_schema import WeaviateSchemaManager
from .chunking_strategy_factory import ChunkingStrategyConfig, ChunkingStrategyFactory
from .ingestion_state import IngestionStateTracker
from .markdown_cleaner import ObsidianMarkdownCleaner
from .text_chunker import TextChunk, TextChunker

logger = logging.getLogger(__name__)


class ObsidianIngestor:
    """
    Main ingestor for Obsidian vault content.

    Processes markdown files from Obsidian vault and stores them
    in Weaviate TheMuses collection for semantic search and clustering.
    """

    def __init__(
        self,
        vault_path: str,
        weaviate_client,
        ollama_client,
        state_tracker: IngestionStateTracker | None = None,
        chunk_size: int = 400,
        chunk_overlap: int = 100,
        chunking_strategy: str = "recursive",
        semantic_min_chunk_size: int = 100,
        semantic_max_chunk_size: int = 1000,
        semantic_model: str | None = None,
        semantic_temperature: float = 0.2,
        semantic_request_timeout: float = 5.0,
        semantic_total_timeout: float = 30.0,
        section_semantic_min_length: int = 1000,
    ):
        """
        Initialize Obsidian ingestor.

        Args:
            vault_path: Path to Obsidian vault directory
            weaviate_client: Connected Weaviate client
            ollama_client: Ollama client for embeddings
            state_tracker: Optional state tracker (creates new if None)
            chunk_size: Target chunk size in characters
            chunk_overlap: Overlap between chunks
        """
        self.vault_path = vault_path
        self.weaviate_client = weaviate_client
        self.ollama_client = ollama_client
        self.collection_name = "TheMuses"

        # Initialize components
        self.cleaner = ObsidianMarkdownCleaner()
        self.recursive_chunker = TextChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self.state_tracker = state_tracker or IngestionStateTracker()

        strategy_factory = ChunkingStrategyFactory(
            ollama_client=ollama_client, state_tracker=self.state_tracker
        )
        semantic_model = semantic_model or os.getenv("SEMANTIC_LLM_MODEL", "gemma3:1b")
        strategy_config = ChunkingStrategyConfig(
            strategy=chunking_strategy,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            semantic_min_chunk_size=semantic_min_chunk_size,
            semantic_max_chunk_size=semantic_max_chunk_size,
            semantic_model=semantic_model,
            semantic_temperature=semantic_temperature,
            semantic_request_timeout=semantic_request_timeout,
            semantic_total_timeout=semantic_total_timeout,
            section_semantic_min_length=section_semantic_min_length,
        )
        self.chunker = strategy_factory.create(
            strategy_config, recursive_chunker=self.recursive_chunker
        )

        # Ensure Weaviate collection exists
        schema_manager = WeaviateSchemaManager(weaviate_client)
        schema_manager.ensure_collection_exists(self.collection_name)

    def scan_vault(self) -> list[str]:
        """
        Scan vault for all markdown files.

        Returns:
            List of absolute paths to .md files
        """
        pattern = os.path.join(self.vault_path, "**", "*.md")
        files = glob(pattern, recursive=True)
        return sorted(files)

    def needs_ingestion(self, file_path: str) -> bool:
        """
        Check if file needs (re-)ingestion.

        Returns True if:
        - File not yet ingested
        - File modified since last ingestion

        Args:
            file_path: Path to file

        Returns:
            True if file needs ingestion
        """
        try:
            mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
            return not self.state_tracker.is_ingested(file_path, mod_time)
        except Exception as e:
            logger.warning(f"Error checking file {file_path}: {e}")
            return False

    def ingest_file(self, file_path: str) -> int:
        """
        Ingest single markdown file.

        Processes file through complete pipeline:
        1. Read file
        2. Extract structure and clean markdown
        3. Chunk text with structure metadata
        4. Generate embeddings
        5. Store in Weaviate
        6. Update state tracker

        Args:
            file_path: Path to markdown file

        Returns:
            Number of chunks created
        """
        try:
            prepared = self._prepare_chunks_for_file(file_path)
            if prepared is None:
                return 0

            chunks, mod_time = prepared
            if not chunks:
                logger.info(f"No chunks created for: {file_path}")
                return 0

            for chunk in chunks:
                embedding = self._generate_embedding(chunk.text)
                self._store_chunk(
                    {
                        "text": chunk.text,
                        "source_file": chunk.source_file,
                        "chunk_index": chunk.index,
                        "source_type": "obsidian",
                        "file_modified_at": mod_time,
                        "heading_path": chunk.heading_path,
                        "heading_level": chunk.heading_level,
                        "section_title": chunk.section_title,
                        "embedding": embedding,
                    }
                )

            self.state_tracker.mark_ingested(file_path, mod_time, len(chunks))
            logger.info(f"Ingested {file_path}: {len(chunks)} chunks")
            return len(chunks)
        except Exception as e:
            logger.error(f"Error ingesting {file_path}: {e}")
            return 0

    def ingest_vault(self) -> dict[str, int]:
        """
        Ingest entire vault.

        Processes all markdown files that need ingestion.

        Returns:
            Dict with ingestion statistics
        """
        files = self.scan_vault()
        files_processed = 0
        files_skipped = 0
        total_chunks = 0

        logger.info(f"Found {len(files)} markdown files in vault")

        prepared_files: list[tuple[str, datetime, list[TextChunk]]] = []

        for file_path in files:
            if not self.needs_ingestion(file_path):
                files_skipped += 1
                continue

            prepared = self._prepare_chunks_for_file(file_path)
            if prepared is None:
                continue

            chunks, mod_time = prepared
            if not chunks:
                logger.info(f"No chunks created for: {file_path}")
                continue

            prepared_files.append((file_path, mod_time, chunks))
            files_processed += 1
            total_chunks += len(chunks)

        for file_path, mod_time, chunks in prepared_files:
            for chunk in chunks:
                embedding = self._generate_embedding(chunk.text)
                self._store_chunk(
                    {
                        "text": chunk.text,
                        "source_file": chunk.source_file,
                        "chunk_index": chunk.index,
                        "source_type": "obsidian",
                        "file_modified_at": mod_time,
                        "heading_path": chunk.heading_path,
                        "heading_level": chunk.heading_level,
                        "section_title": chunk.section_title,
                        "embedding": embedding,
                    }
                )

            self.state_tracker.mark_ingested(file_path, mod_time, len(chunks))

        stats = {
            "files_processed": files_processed,
            "files_skipped": files_skipped,
            "total_files": len(files),
            "total_chunks": total_chunks,
        }

        logger.info(f"Ingestion complete: {stats}")
        return stats

    def _prepare_chunks_for_file(
        self, file_path: str
    ) -> tuple[list[TextChunk], datetime] | None:
        try:
            content = Path(file_path).read_text(encoding="utf-8")
            cleaned, structure = self._clean_markdown_with_structure(content)

            if not cleaned.strip():
                logger.info(f"Skipping empty file: {file_path}")
                return None

            chunks = self._chunk_text_with_structure(cleaned, file_path, structure)
            mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
            return chunks, mod_time
        except Exception as e:
            logger.error(f"Error preparing chunks for {file_path}: {e}")
            return None

    def _clean_markdown(self, markdown: str) -> str:
        """Clean Obsidian syntax from markdown (backward compatibility)"""
        return self.cleaner.clean(markdown)

    def _clean_markdown_with_structure(self, markdown: str):
        """Extract structure and clean Obsidian syntax (Story 020)"""
        return self.cleaner.clean_with_structure(markdown)

    def _chunk_text(self, text: str, source_file: str) -> list[TextChunk]:
        """Chunk cleaned text (backward compatibility)"""
        return self.recursive_chunker.chunk(text, source_file)

    def _chunk_text_with_structure(self, text: str, source_file: str, structure):
        """Chunk cleaned text with structure metadata (Story 020)"""
        if isinstance(self.chunker, TextChunker):
            return self.chunker.chunk_with_structure(text, source_file, structure)
        return self.chunker.chunk(text, source_file, structure=structure)

    def _generate_embedding(self, text: str) -> list[float]:
        """
        Generate embedding for text via Ollama.

        Args:
            text: Text to embed

        Returns:
            1024-dimensional embedding vector
        """
        response = self.ollama_client.embeddings(model="qwen3-embedding:0.6b", prompt=text)
        return response["embedding"]

    def _store_chunk(self, chunk_data: dict[str, Any]) -> None:
        """
        Store chunk in Weaviate TheMuses collection.

        Args:
            chunk_data: Dict with text, metadata, and embedding
        """
        collection = self.weaviate_client.collections.get(self.collection_name)

        properties = {
            "text": chunk_data["text"],
            "sourceFile": chunk_data["source_file"],
            "sourceType": chunk_data["source_type"],
            "chunkIndex": chunk_data["chunk_index"],
            "ingestedAt": datetime.now(),
            "fileModifiedAt": chunk_data["file_modified_at"],
            # Story 020: Heading metadata
            "headingPath": chunk_data.get("heading_path", ""),
            "headingLevel": chunk_data.get("heading_level", 0),
            "sectionTitle": chunk_data.get("section_title", ""),
        }

        collection.data.insert(
            properties=properties,
            vector=chunk_data["embedding"],
        )
