#!/usr/bin/env python3
"""
Re-ingestion Script for Story 020: Hierarchical Structure Preservation

This script re-processes existing chunks in Weaviate to add structure metadata
(headingPath, headingLevel, sectionTitle) without re-generating embeddings.

Usage:
    # Dry run (no changes)
    python scripts/reingest_with_structure.py --dry-run

    # Re-ingest all Obsidian chunks
    python scripts/reingest_with_structure.py --source-type obsidian

    # Re-ingest specific vault
    python scripts/reingest_with_structure.py --vault-path /path/to/vault

    # Re-ingest with progress bar
    python scripts/reingest_with_structure.py --verbose

Prerequisites:
    - Weaviate running on localhost:8080
    - Original markdown files still available at sourceFile paths
    - Backup recommended before running (use --dry-run first)

What This Does:
    1. Fetches existing chunks from Weaviate (by sourceType)
    2. Groups chunks by sourceFile
    3. For each file:
        - Reads original markdown file
        - Extracts document structure
        - Updates chunk metadata with structure info
    4. Updates chunks in Weaviate (preserves vectors)

What This Doesn't Do:
    - Re-generate embeddings (vectors preserved)
    - Re-chunk documents (existing chunks kept)
    - Change chunk text content
    - Delete or add new chunks
"""

import argparse
import logging
import sys
from collections import defaultdict
from pathlib import Path

import weaviate
from weaviate.classes.query import Filter

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.mnemosyne.aletheia.structure_extractor import StructureExtractor
from src.mnemosyne.aletheia.text_chunker import TextChunker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class StructureReIngester:
    """Re-ingest existing chunks with structure metadata."""

    def __init__(
        self,
        weaviate_client: weaviate.WeaviateClient,
        collection_name: str = "TheMuses",
        dry_run: bool = False,
    ):
        self.client = weaviate_client
        self.collection_name = collection_name
        self.dry_run = dry_run
        self.structure_extractor = StructureExtractor()
        self.chunker = TextChunker()

        self.stats = {
            "files_processed": 0,
            "chunks_updated": 0,
            "chunks_failed": 0,
            "files_not_found": 0,
        }

    def fetch_chunks_by_source_type(self, source_type: str) -> list[dict]:
        """Fetch all chunks for a given source type."""
        logger.info(f"Fetching chunks with sourceType={source_type}...")

        collection = self.client.collections.get(self.collection_name)
        results = collection.query.fetch_objects(
            filters=Filter.by_property("sourceType").equal(source_type),
            limit=10000,  # Adjust if you have more chunks
        )

        chunks = []
        for obj in results.objects:
            chunks.append(
                {
                    "uuid": obj.uuid,
                    "properties": obj.properties,
                    "vector": obj.vector,  # Preserve existing vector
                }
            )

        logger.info(f"Fetched {len(chunks)} chunks")
        return chunks

    def group_chunks_by_file(self, chunks: list[dict]) -> dict[str, list[dict]]:
        """Group chunks by sourceFile."""
        grouped = defaultdict(list)
        for chunk in chunks:
            source_file = chunk["properties"].get("sourceFile")
            if source_file:
                grouped[source_file].append(chunk)
        return dict(grouped)

    def read_original_file(self, file_path: str) -> str | None:
        """Read the original markdown file."""
        try:
            path = Path(file_path)
            if not path.exists():
                logger.warning(f"File not found: {file_path}")
                self.stats["files_not_found"] += 1
                return None

            return path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
            return None

    def extract_structure_for_chunks(self, original_text: str, chunks: list[dict]) -> list[dict]:
        """Extract structure and assign to chunks."""
        # Extract document structure
        structure = self.structure_extractor.extract_structure(original_text)

        # Assign structure to each chunk based on character position
        updated_chunks = []
        for chunk in chunks:
            chunk_text = chunk["properties"].get("text", "")
            chunk_index = chunk["properties"].get("chunkIndex", 0)

            # Find chunk position in original text (approximate)
            # This is a simplified approach - for production, you'd want exact position tracking
            chunk_start = original_text.find(chunk_text[:100])  # Use first 100 chars

            if chunk_start == -1:
                # Chunk text not found in original - skip structure
                logger.warning(f"Could not locate chunk {chunk_index} in original text")
                updated_chunks.append(chunk)
                continue

            # Get heading at this position
            heading = structure.get_heading_at_pos(chunk_start)

            # Update chunk properties
            updated_chunk = chunk.copy()
            if heading:
                updated_chunk["properties"]["headingPath"] = structure.get_heading_path(heading)
                updated_chunk["properties"]["headingLevel"] = heading.level
                updated_chunk["properties"]["sectionTitle"] = heading.title
            else:
                # No heading found - set defaults
                updated_chunk["properties"]["headingPath"] = None
                updated_chunk["properties"]["headingLevel"] = 0
                updated_chunk["properties"]["sectionTitle"] = None

            updated_chunks.append(updated_chunk)

        return updated_chunks

    def update_chunks_in_weaviate(self, chunks: list[dict]) -> int:
        """Update chunks in Weaviate with new structure metadata."""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would update {len(chunks)} chunks")
            return len(chunks)

        collection = self.client.collections.get(self.collection_name)
        updated_count = 0

        for chunk in chunks:
            try:
                # Update chunk properties (preserving vector)
                collection.data.update(
                    uuid=chunk["uuid"],
                    properties={
                        "headingPath": chunk["properties"].get("headingPath"),
                        "headingLevel": chunk["properties"].get("headingLevel"),
                        "sectionTitle": chunk["properties"].get("sectionTitle"),
                    },
                    # Vector is NOT updated - it's preserved automatically
                )
                updated_count += 1
            except Exception as e:
                logger.error(f"Failed to update chunk {chunk['uuid']}: {e}")
                self.stats["chunks_failed"] += 1

        return updated_count

    def reingest_file(self, source_file: str, chunks: list[dict]) -> None:
        """Re-ingest a single file's chunks with structure metadata."""
        logger.info(f"Processing {source_file} ({len(chunks)} chunks)...")

        # Read original file
        original_text = self.read_original_file(source_file)
        if not original_text:
            return

        # Extract structure and assign to chunks
        updated_chunks = self.extract_structure_for_chunks(original_text, chunks)

        # Update in Weaviate
        updated_count = self.update_chunks_in_weaviate(updated_chunks)

        self.stats["files_processed"] += 1
        self.stats["chunks_updated"] += updated_count
        logger.info(f"Updated {updated_count}/{len(chunks)} chunks")

    def reingest_all(self, source_type: str = "obsidian") -> None:
        """Re-ingest all chunks of a given source type."""
        logger.info(f"Starting re-ingestion for sourceType={source_type}")
        logger.info(f"Dry run: {self.dry_run}")

        # Fetch all chunks
        chunks = self.fetch_chunks_by_source_type(source_type)
        if not chunks:
            logger.warning(f"No chunks found with sourceType={source_type}")
            return

        # Group by file
        chunks_by_file = self.group_chunks_by_file(chunks)
        logger.info(f"Processing {len(chunks_by_file)} unique files")

        # Process each file
        for source_file, file_chunks in chunks_by_file.items():
            try:
                self.reingest_file(source_file, file_chunks)
            except Exception as e:
                logger.error(f"Error processing {source_file}: {e}")
                self.stats["files_not_found"] += 1

        # Print summary
        self.print_summary()

    def print_summary(self) -> None:
        """Print re-ingestion summary."""
        logger.info("\n" + "=" * 60)
        logger.info("Re-Ingestion Summary")
        logger.info("=" * 60)
        logger.info(f"Files processed: {self.stats['files_processed']}")
        logger.info(f"Chunks updated: {self.stats['chunks_updated']}")
        logger.info(f"Chunks failed: {self.stats['chunks_failed']}")
        logger.info(f"Files not found: {self.stats['files_not_found']}")
        logger.info("=" * 60)

        if self.dry_run:
            logger.info("\n⚠️  DRY RUN - No changes were made to Weaviate")
        else:
            logger.info("\n✓ Re-ingestion complete")


def main():
    parser = argparse.ArgumentParser(
        description="Re-ingest existing chunks with structure metadata"
    )
    parser.add_argument(
        "--source-type",
        default="obsidian",
        help="Source type to re-ingest (default: obsidian)",
    )
    parser.add_argument(
        "--collection",
        default="TheMuses",
        help="Weaviate collection name (default: TheMuses)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying Weaviate",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--weaviate-url",
        default="http://localhost:8080",
        help="Weaviate URL (default: http://localhost:8080)",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Connect to Weaviate
    logger.info(f"Connecting to Weaviate at {args.weaviate_url}...")
    try:
        client = weaviate.connect_to_local(
            host="localhost",
            port=8080,
        )
    except Exception as e:
        logger.error(f"Failed to connect to Weaviate: {e}")
        logger.error("Make sure Weaviate is running: docker-compose up weaviate -d")
        sys.exit(1)

    logger.info("✓ Connected to Weaviate")

    # Create re-ingester
    reingester = StructureReIngester(
        weaviate_client=client,
        collection_name=args.collection,
        dry_run=args.dry_run,
    )

    # Run re-ingestion
    try:
        reingester.reingest_all(source_type=args.source_type)
    except KeyboardInterrupt:
        logger.warning("\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Re-ingestion failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        client.close()

    # Exit with appropriate code
    if reingester.stats["chunks_failed"] > 0:
        logger.warning(f"\n⚠️  Completed with {reingester.stats['chunks_failed']} failures")
        sys.exit(1)


if __name__ == "__main__":
    main()
