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

import hashlib
import logging
import os
import time
from datetime import UTC, datetime
from glob import glob
from pathlib import Path
from typing import Any

from mnemosyne.providers.base import EmbeddingProvider, LLMProvider

from ..alexandria.weaviate_schema import WeaviateSchemaManager
from .chunking_augmentation import compute_chunk_spans
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
        embedding_provider: EmbeddingProvider,
        llm_provider: LLMProvider | None = None,
        state_tracker: IngestionStateTracker | None = None,
        chunk_size: int = 400,
        chunk_overlap: int = 100,
        chunking_strategy: str = "semantic_consensus",
        chunking_augmentation: str = "none",
        semantic_min_chunk_size: int = 100,
        semantic_max_chunk_size: int = 1000,
        semantic_model: str | None = None,
        semantic_temperature: float = 0.2,
        semantic_request_timeout: float = 5.0,
        semantic_total_timeout: float = 30.0,
        semantic_json_max_chars: int = 12000,
        semantic_json_max_tokens: int = 512,
        semantic_json_max_prompt_tokens: int = 16000,
        section_semantic_min_length: int = 1000,
        semantic_cosine_threshold: float = 0.78,
        semantic_merge_similarity_threshold: float = 0.85,
        semantic_consensus_tolerance: int = 20,
        semantic_cosine_min_chunk_size: int = 100,
        semantic_cosine_max_chunk_size: int = 1000,
        semantic_cosine_embedding_model: str = "",
        semantic_merge_max_embed_chars: int = 2000,
        contextual_llm_provider: LLMProvider | None = None,
        contextual_llm_model: str = "",
        contextual_max_doc_chars: int = 4000,
        doc_summary_llm_model: str = "",
        doc_summary_max_chars: int = 200,
        doc_summary_temperature: float = 0.2,
        late_chunk_adapter: str = "retrieval.passage",
        late_chunk_embedding_model: str = "",
        progress_every: int | None = None,
    ):
        """
        Initialize Obsidian ingestor.

        Args:
            vault_path: Path to Obsidian vault directory
            weaviate_client: Connected Weaviate client
            embedding_provider: Provider for generating embeddings
            llm_provider: Optional provider for LLM-based tasks
            state_tracker: Optional state tracker (creates new if None)
            chunk_size: Target chunk size in characters
            chunk_overlap: Overlap between chunks
        """
        self.vault_path = vault_path
        self.weaviate_client = weaviate_client
        self.embedding_provider = embedding_provider
        self.llm_provider = llm_provider
        self.collection_name = "TheMuses"
        self.progress_every = self._resolve_progress_every(progress_every)
        self.chunking_augmentation = (chunking_augmentation or "none").lower()
        self.contextual_llm_provider = contextual_llm_provider or llm_provider
        self.contextual_llm_model = contextual_llm_model
        self.contextual_max_doc_chars = contextual_max_doc_chars
        self.doc_summary_llm_model = doc_summary_llm_model or contextual_llm_model
        self.doc_summary_max_chars = doc_summary_max_chars
        self.doc_summary_temperature = doc_summary_temperature
        self.late_chunk_adapter = late_chunk_adapter
        self.late_chunk_embedding_model = late_chunk_embedding_model

        # Initialize components
        self.cleaner = ObsidianMarkdownCleaner()
        self.recursive_chunker = TextChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self.state_tracker = state_tracker or IngestionStateTracker()

        strategy_factory = ChunkingStrategyFactory(
            llm_provider=llm_provider,
            state_tracker=self.state_tracker,
            embedding_provider=embedding_provider,
        )
        semantic_model = semantic_model or os.getenv("SEMANTIC_LLM_MODEL", "glm-4.6v-flash")
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
            semantic_json_max_chars=semantic_json_max_chars,
            semantic_json_max_tokens=semantic_json_max_tokens,
            semantic_json_max_prompt_tokens=semantic_json_max_prompt_tokens,
            section_semantic_min_length=section_semantic_min_length,
            semantic_cosine_threshold=semantic_cosine_threshold,
            semantic_merge_similarity_threshold=semantic_merge_similarity_threshold,
            semantic_consensus_tolerance=semantic_consensus_tolerance,
            semantic_cosine_min_chunk_size=semantic_cosine_min_chunk_size,
            semantic_cosine_max_chunk_size=semantic_cosine_max_chunk_size,
            semantic_cosine_embedding_model=semantic_cosine_embedding_model,
            semantic_merge_max_embed_chars=semantic_merge_max_embed_chars,
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
            mod_time = datetime.fromtimestamp(os.path.getmtime(file_path), tz=UTC)
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

            chunks, mod_time, cleaned_text = prepared
            if not chunks:
                logger.info(f"No chunks created for: {file_path}")
                return 0

            self._delete_existing_chunks(file_path)
            inserted_chunks = 0
            failed_embedding = False
            embeddings = self._generate_embeddings_for_chunks(cleaned_text, chunks)
            for chunk, embed_result in zip(chunks, embeddings, strict=False):
                embedding = embed_result.get("embedding")
                if not embedding:
                    logger.error("Embedding empty for %s chunk %s", file_path, chunk.index)
                    failed_embedding = True
                    continue
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
                        "context_header": embed_result.get("context_header"),
                        "doc_summary": embed_result.get("doc_summary"),
                        "embedding": embedding,
                    }
                )
                inserted_chunks += 1

            if not failed_embedding:
                self.state_tracker.mark_ingested(file_path, mod_time, inserted_chunks)
            else:
                logger.error("Embedding failures detected for %s; skipping state update", file_path)

            logger.info(f"Ingested {file_path}: {inserted_chunks} chunks")
            return inserted_chunks
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
        start_time = time.monotonic()

        logger.info(f"Found {len(files)} markdown files in vault")

        prepared_files: list[tuple[str, datetime, str, list[TextChunk]]] = []

        for file_path in files:
            if not self.needs_ingestion(file_path):
                files_skipped += 1
                continue

            prepared = self._prepare_chunks_for_file(file_path)
            if prepared is None:
                continue

            chunks, mod_time, cleaned_text = prepared
            if not chunks:
                logger.info(f"No chunks created for: {file_path}")
                continue

            prepared_files.append((file_path, mod_time, cleaned_text, chunks))
            files_processed += 1
            total_chunks += len(chunks)

        total_to_process = len(prepared_files)
        for index, (file_path, mod_time, cleaned_text, chunks) in enumerate(
            prepared_files, start=1
        ):
            self._delete_existing_chunks(file_path)
            inserted_chunks = 0
            failed_embedding = False
            embeddings = self._generate_embeddings_for_chunks(cleaned_text, chunks)
            for chunk, embed_result in zip(chunks, embeddings, strict=False):
                embedding = embed_result.get("embedding")
                if not embedding:
                    logger.error("Embedding empty for %s chunk %s", file_path, chunk.index)
                    failed_embedding = True
                    continue
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
                        "context_header": embed_result.get("context_header"),
                        "doc_summary": embed_result.get("doc_summary"),
                        "embedding": embedding,
                    }
                )
                inserted_chunks += 1

            if not failed_embedding:
                self.state_tracker.mark_ingested(file_path, mod_time, inserted_chunks)
            else:
                logger.error("Embedding failures detected for %s; skipping state update", file_path)
            self._log_progress(index, total_to_process, start_time)

        stats = {
            "files_processed": files_processed,
            "files_skipped": files_skipped,
            "total_files": len(files),
            "total_chunks": total_chunks,
        }

        logger.info(f"Ingestion complete: {stats}")
        return stats

    def _resolve_progress_every(self, progress_every: int | None) -> int:
        if progress_every is not None:
            return max(0, int(progress_every))
        try:
            return max(0, int(os.getenv("INGEST_PROGRESS_EVERY", "0")))
        except ValueError:
            return 0

    def _log_progress(self, processed: int, total: int, start_time: float) -> None:
        if self.progress_every <= 0 or total <= 0:
            return
        if processed % self.progress_every != 0 and processed != total:
            return

        elapsed = time.monotonic() - start_time
        rate = processed / elapsed if elapsed > 0 else 0.0
        remaining = (total - processed) / rate if rate > 0 else 0.0
        percent = (processed / total) * 100 if total else 0.0
        logger.info(
            "Ingestion progress: %s/%s files (%.1f%%). Elapsed %.1fs, ETA %.1fs",
            processed,
            total,
            percent,
            elapsed,
            remaining,
        )

    def _prepare_chunks_for_file(
        self, file_path: str
    ) -> tuple[list[TextChunk], datetime, str] | None:
        try:
            content = Path(file_path).read_text(encoding="utf-8")
            cleaned, structure = self._clean_markdown_with_structure(content)

            if not cleaned.strip():
                logger.info(f"Skipping empty file: {file_path}")
                return None

            chunks = self._chunk_text_with_structure(cleaned, file_path, structure)
            mod_time = datetime.fromtimestamp(os.path.getmtime(file_path), tz=UTC)
            return chunks, mod_time, cleaned
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
        Generate embedding for text via the configured provider.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        return self.embedding_provider.embed(model="", text=text)

    def _generate_embeddings_for_chunks(
        self, cleaned_text: str, chunks: list[TextChunk]
    ) -> list[dict[str, Any]]:
        if self.chunking_augmentation == "late":
            spans = compute_chunk_spans(
                cleaned_text,
                chunks,
                chunk_overlap=self.recursive_chunker.chunk_overlap,
            )
            if spans and len(spans) == len(chunks):
                try:
                    embeddings = self.embedding_provider.embed_late(
                        model=self.late_chunk_embedding_model,
                        text=cleaned_text,
                        chunk_spans=spans,
                        options={"adapter": self.late_chunk_adapter},
                    )
                    if len(embeddings) == len(chunks):
                        logger.info("Late chunking applied for %s chunks", len(embeddings))
                        return [{"embedding": embedding} for embedding in embeddings]
                    logger.warning(
                        "Late chunking returned %s embeddings for %s chunks; falling back",
                        len(embeddings),
                        len(chunks),
                    )
                except Exception as exc:
                    logger.warning("Late chunking failed; falling back: %s", exc)
            else:
                logger.warning("Late chunking spans unavailable; falling back")
            logger.info("Late chunking fallback to per-chunk embeddings for %s chunks", len(chunks))

        doc_summary = None
        if self.chunking_augmentation == "doc_summary":
            doc_summary = self._generate_doc_summary(cleaned_text)

        results = []
        contextual_used = 0
        for chunk in chunks:
            context_header = None
            text = chunk.text
            if self.chunking_augmentation == "contextual":
                context_header = self._generate_context_header(cleaned_text, chunk)
                if context_header:
                    text = f"{context_header}\n\n{chunk.text}"
                    contextual_used += 1
            if self.chunking_augmentation == "doc_summary" and doc_summary:
                text = f"{doc_summary}\n\n{chunk.text}"
            embedding = self._generate_embedding(text)
            results.append(
                {
                    "embedding": embedding,
                    "context_header": context_header,
                    "doc_summary": doc_summary,
                }
            )
        if self.chunking_augmentation == "contextual":
            logger.info(
                "Contextual headers generated for %s/%s chunks",
                contextual_used,
                len(chunks),
            )
        return results

    def _generate_context_header(self, cleaned_text: str, chunk: TextChunk) -> str | None:
        if not self.contextual_llm_provider:
            logger.warning("Contextual augmentation requires an LLM provider; skipping.")
            return None

        doc_text = cleaned_text[: self.contextual_max_doc_chars]
        prompt = (
            "You are generating a short context header for retrieval.\n"
            "Given the document text and the chunk, return a 1-2 line header that "
            "adds missing context (title, subject, dates, names).\n"
            "Return only the header text.\n\n"
            f"Document:\n{doc_text}\n\n"
            f"Chunk:\n{chunk.text}\n\n"
            "Header:"
        )
        try:
            response = self.contextual_llm_provider.generate(
                model=self.contextual_llm_model,
                prompt=prompt,
                options={"temperature": 0.2},
            )
        except Exception as exc:
            logger.warning("Context header generation failed; falling back: %s", exc)
            return None

        header = response.get("response", "")
        if not isinstance(header, str):
            return None
        header = header.strip()
        return header or None

    def _generate_doc_summary(self, cleaned_text: str) -> str | None:
        if not self.contextual_llm_provider:
            logger.warning("Doc summary augmentation requires an LLM provider; skipping.")
            return None

        cache_key = self._doc_summary_cache_key(cleaned_text)
        if hasattr(self.state_tracker, "get_cached_doc_summary"):
            cached = self.state_tracker.get_cached_doc_summary(cache_key)
            if cached:
                return cached

        doc_text = cleaned_text[: self.contextual_max_doc_chars]
        prompt = (
            "Summarize the document in 1-2 lines. "
            f"Keep it under {self.doc_summary_max_chars} characters. "
            "Return only the summary.\n\n"
            f"Document:\n{doc_text}\n"
        )
        try:
            response = self.contextual_llm_provider.generate(
                model=self.doc_summary_llm_model,
                prompt=prompt,
                options={"temperature": self.doc_summary_temperature},
            )
        except Exception as exc:
            logger.warning("Doc summary generation failed: %s", exc)
            return None

        summary = response.get("response", "")
        if not isinstance(summary, str):
            return None
        summary = summary.strip()
        if not summary:
            return None
        if len(summary) > self.doc_summary_max_chars:
            summary = summary[: self.doc_summary_max_chars].rstrip()

        if hasattr(self.state_tracker, "cache_doc_summary"):
            self.state_tracker.cache_doc_summary(
                cache_key=cache_key,
                summary=summary,
                model=self.doc_summary_llm_model,
                max_chars=self.doc_summary_max_chars,
                temperature=self.doc_summary_temperature,
            )
        return summary

    def _doc_summary_cache_key(self, cleaned_text: str) -> str:
        digest = hashlib.sha256(cleaned_text.encode("utf-8")).hexdigest()
        return (
            f"doc-summary-v1:{self.doc_summary_llm_model}:{self.doc_summary_max_chars}:"
            f"{self.doc_summary_temperature}:{digest}"
        )

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
            "sourceFileId": self._source_file_id(chunk_data["source_file"]),
            "sourceType": chunk_data["source_type"],
            "chunkIndex": chunk_data["chunk_index"],
            "ingestedAt": datetime.now(UTC),
            "fileModifiedAt": chunk_data["file_modified_at"],
            # Story 020: Heading metadata
            "headingPath": chunk_data.get("heading_path", ""),
            "headingLevel": chunk_data.get("heading_level", 0),
            "sectionTitle": chunk_data.get("section_title", ""),
            "contextHeader": chunk_data.get("context_header") or "",
            "docSummary": chunk_data.get("doc_summary") or "",
        }

        collection.data.insert(
            properties=properties,
            vector={"default": chunk_data["embedding"]},
        )

    def _delete_existing_chunks(self, file_path: str) -> None:
        """Remove previously ingested chunks for a file before re-ingesting."""
        from weaviate.classes.query import Filter

        collection = self.weaviate_client.collections.get(self.collection_name)
        file_id = self._source_file_id(file_path)
        delete_result = collection.data.delete_many(
            where=Filter.by_property("sourceFileId").equal(file_id)
            & Filter.by_property("sourceType").equal("obsidian")
        )
        logger.info(
            "Deleted %s existing chunks for %s (successful: %s, failed: %s)",
            delete_result.matches,
            file_path,
            delete_result.successful,
            delete_result.failed,
        )

    def _source_file_id(self, file_path: str) -> str:
        """Create a stable, exact-match identifier for a source file path."""
        return hashlib.sha1(file_path.encode("utf-8")).hexdigest()
