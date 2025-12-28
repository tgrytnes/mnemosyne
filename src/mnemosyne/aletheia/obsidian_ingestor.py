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

import os
from glob import glob
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging

from .markdown_cleaner import ObsidianMarkdownCleaner
from .text_chunker import TextChunker, TextChunk
from .ingestion_state import IngestionStateTracker
from ..alexandria.weaviate_schema import WeaviateSchemaManager

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
        state_tracker: Optional[IngestionStateTracker] = None,
        chunk_size: int = 400,
        chunk_overlap: int = 100,
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
        self.chunker = TextChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self.state_tracker = state_tracker or IngestionStateTracker()

        # Ensure Weaviate collection exists
        schema_manager = WeaviateSchemaManager(weaviate_client)
        schema_manager.ensure_collection_exists(self.collection_name)

    def scan_vault(self) -> List[str]:
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
        2. Clean markdown
        3. Chunk text
        4. Generate embeddings
        5. Store in Weaviate
        6. Update state tracker

        Args:
            file_path: Path to markdown file

        Returns:
            Number of chunks created
        """
        try:
            # Read file
            content = Path(file_path).read_text(encoding="utf-8")

            # Clean markdown
            cleaned = self._clean_markdown(content)

            if not cleaned.strip():
                logger.info(f"Skipping empty file: {file_path}")
                return 0

            # Chunk text
            chunks = self._chunk_text(cleaned, file_path)

            if not chunks:
                logger.info(f"No chunks created for: {file_path}")
                return 0

            # Process each chunk
            for chunk in chunks:
                # Generate embedding
                embedding = self._generate_embedding(chunk.text)

                # Store in Weaviate
                self._store_chunk(
                    {
                        "text": chunk.text,
                        "source_file": chunk.source_file,
                        "chunk_index": chunk.index,
                        "source_type": "obsidian",
                        "file_modified_at": datetime.fromtimestamp(os.path.getmtime(file_path)),
                        "embedding": embedding,
                    }
                )

            # Update state tracker
            mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
            self.state_tracker.mark_ingested(file_path, mod_time, len(chunks))

            logger.info(f"Ingested {file_path}: {len(chunks)} chunks")
            return len(chunks)

        except Exception as e:
            logger.error(f"Error ingesting {file_path}: {e}")
            return 0

    def ingest_vault(self) -> Dict[str, int]:
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

        for file_path in files:
            if self.needs_ingestion(file_path):
                chunk_count = self.ingest_file(file_path)
                if chunk_count > 0:
                    files_processed += 1
                    total_chunks += chunk_count
            else:
                files_skipped += 1

        stats = {
            "files_processed": files_processed,
            "files_skipped": files_skipped,
            "total_files": len(files),
            "total_chunks": total_chunks,
        }

        logger.info(f"Ingestion complete: {stats}")
        return stats

    def _clean_markdown(self, markdown: str) -> str:
        """Clean Obsidian syntax from markdown"""
        return self.cleaner.clean(markdown)

    def _chunk_text(self, text: str, source_file: str) -> List[TextChunk]:
        """Chunk cleaned text"""
        return self.chunker.chunk(text, source_file)

    def _generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text via Ollama.

        Args:
            text: Text to embed

        Returns:
            1024-dimensional embedding vector
        """
        response = self.ollama_client.embeddings(model="qwen3-embedding:0.6b", prompt=text)
        return response["embedding"]

    def _store_chunk(self, chunk_data: Dict[str, Any]) -> None:
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
        }

        collection.data.insert(
            properties=properties,
            vector=chunk_data["embedding"],
        )
