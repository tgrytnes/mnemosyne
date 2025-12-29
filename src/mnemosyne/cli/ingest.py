"""
CLI commands for Obsidian vault ingestion.

Provides commands for manual and automatic ingestion of Obsidian vault content.
"""

import logging
import os
import sys
from pathlib import Path

import ollama
import weaviate

from ..aletheia.ingestion_state import IngestionStateTracker
from ..aletheia.obsidian_ingestor import ObsidianIngestor
from ..aletheia.vault_watcher import VaultWatcher

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class IngestionConfig:
    """Configuration for Obsidian vault ingestion."""

    def __init__(self):
        """Load configuration from environment variables."""
        self.vault_path = os.getenv("OBSIDIAN_VAULT_PATH")
        self.weaviate_host = os.getenv("WEAVIATE_HTTP_HOST", "localhost")
        self.weaviate_port = int(os.getenv("WEAVIATE_HTTP_PORT", "8080"))
        self.weaviate_grpc_port = int(os.getenv("WEAVIATE_GRPC_PORT", "50051"))
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.state_db_path = os.getenv("INGESTION_STATE_DB", "ingestion_state.db")
        self.chunk_size = int(os.getenv("CHUNK_SIZE", "400"))
        self.chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "100"))
        self.chunking_strategy = os.getenv("CHUNKING_STRATEGY", "recursive")
        self.semantic_min_chunk_size = int(os.getenv("SEMANTIC_MIN_CHUNK_SIZE", "100"))
        self.semantic_max_chunk_size = int(os.getenv("SEMANTIC_MAX_CHUNK_SIZE", "1000"))
        self.semantic_model = os.getenv("SEMANTIC_LLM_MODEL", "qwen3:0.6b")
        self.semantic_temperature = float(os.getenv("SEMANTIC_LLM_TEMP", "0.2"))
        self.semantic_request_timeout = float(os.getenv("SEMANTIC_REQUEST_TIMEOUT", "5.0"))
        self.semantic_total_timeout = float(os.getenv("SEMANTIC_TOTAL_TIMEOUT", "30.0"))
        self.section_semantic_min_length = int(os.getenv("SECTION_SEMANTIC_MIN_LENGTH", "1000"))
        self.watch_debounce = float(os.getenv("WATCH_DEBOUNCE_SECONDS", "2.0"))

    def validate(self) -> bool:
        """
        Validate configuration.

        Returns:
            True if configuration is valid

        Raises:
            ValueError: If configuration is invalid
        """
        if not self.vault_path:
            raise ValueError(
                "OBSIDIAN_VAULT_PATH environment variable not set. "
                "Please set it to your Obsidian vault directory."
            )

        vault = Path(self.vault_path)
        if not vault.exists():
            raise ValueError(f"Vault path does not exist: {self.vault_path}")

        if not vault.is_dir():
            raise ValueError(f"Vault path is not a directory: {self.vault_path}")

        return True


def create_ingestor(config: IngestionConfig) -> ObsidianIngestor:
    """
    Create ObsidianIngestor instance with configuration.

    Args:
        config: Ingestion configuration

    Returns:
        Configured ObsidianIngestor instance
    """
    logger.info("Connecting to Weaviate...")
    weaviate_client = weaviate.connect_to_local(
        host=config.weaviate_host,
        port=config.weaviate_port,
        grpc_port=config.weaviate_grpc_port,
    )

    logger.info("Connecting to Ollama...")
    ollama_client = ollama.Client(host=config.ollama_base_url)

    logger.info("Initializing state tracker...")
    state_tracker = IngestionStateTracker(config.state_db_path)

    logger.info("Creating ingestor...")
    ingestor = ObsidianIngestor(
        vault_path=config.vault_path,
        weaviate_client=weaviate_client,
        ollama_client=ollama_client,
        state_tracker=state_tracker,
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
        chunking_strategy=config.chunking_strategy,
        semantic_min_chunk_size=config.semantic_min_chunk_size,
        semantic_max_chunk_size=config.semantic_max_chunk_size,
        semantic_model=config.semantic_model,
        semantic_temperature=config.semantic_temperature,
        semantic_request_timeout=config.semantic_request_timeout,
        semantic_total_timeout=config.semantic_total_timeout,
        section_semantic_min_length=config.section_semantic_min_length,
    )

    return ingestor


def ingest_once(vault_path: str | None = None):
    """
    Ingest entire vault once (manual mode).

    Args:
        vault_path: Optional path to vault (overrides env var)
    """
    try:
        config = IngestionConfig()

        if vault_path:
            config.vault_path = vault_path

        config.validate()

        logger.info("=" * 60)
        logger.info("Starting Manual Vault Ingestion")
        logger.info("=" * 60)
        logger.info(f"Vault: {config.vault_path}")
        logger.info(f"Weaviate: {config.weaviate_host}:{config.weaviate_port}")
        logger.info(f"Ollama: {config.ollama_base_url}")
        logger.info(f"State DB: {config.state_db_path}")
        logger.info("=" * 60)

        ingestor = create_ingestor(config)

        logger.info("\nScanning vault for markdown files...")
        files = ingestor.scan_vault()
        logger.info(f"Found {len(files)} markdown files")

        logger.info("\nStarting ingestion...")
        stats = ingestor.ingest_vault()

        logger.info("\n" + "=" * 60)
        logger.info("Ingestion Complete!")
        logger.info("=" * 60)
        logger.info(f"Total files: {stats['total_files']}")
        logger.info(f"Files processed: {stats['files_processed']}")
        logger.info(f"Files skipped: {stats['files_skipped']}")
        logger.info(f"Total chunks created: {stats['total_chunks']}")
        logger.info("=" * 60)

        # Cleanup
        ingestor.state_tracker.close()
        ingestor.weaviate_client.close()

    except Exception as e:
        logger.error(f"Error during ingestion: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


def re_ingest_vault(vault_path: str | None = None, force: bool = False):
    """
    Re-ingest entire vault, bypassing state tracker.

    Useful for adding structure metadata to existing chunks after Story 020.
    This will delete and re-create all chunks for processed files.

    Args:
        vault_path: Optional path to vault (overrides env var)
        force: If True, delete existing chunks before re-ingestion
    """
    try:
        config = IngestionConfig()

        if vault_path:
            config.vault_path = vault_path

        config.validate()

        logger.info("=" * 60)
        logger.info("Re-Ingesting Vault with Structure Metadata")
        logger.info("=" * 60)
        logger.info(f"Vault: {config.vault_path}")
        logger.info(f"Weaviate: {config.weaviate_host}:{config.weaviate_port}")
        logger.info(f"Ollama: {config.ollama_base_url}")
        logger.info(f"Force mode: {force}")
        logger.info("=" * 60)

        ingestor = create_ingestor(config)

        logger.info("\nScanning vault for markdown files...")
        files = ingestor.scan_vault()
        logger.info(f"Found {len(files)} markdown files")

        if force:
            logger.info("\n⚠️  Force mode: This will delete and re-create all chunks")
            logger.info("Clearing ingestion state...")
            # Clear state tracker to force re-ingestion
            ingestor.state_tracker.clear_all()

        logger.info("\nStarting re-ingestion...")
        stats = ingestor.ingest_vault()

        logger.info("\n" + "=" * 60)
        logger.info("Re-Ingestion Complete!")
        logger.info("=" * 60)
        logger.info(f"Total files: {stats['total_files']}")
        logger.info(f"Files processed: {stats['files_processed']}")
        logger.info(f"Files skipped: {stats['files_skipped']}")
        logger.info(f"Total chunks created: {stats['total_chunks']}")
        logger.info("=" * 60)
        logger.info(
            "\n✓ All chunks now include structure metadata "
            "(headingPath, headingLevel, sectionTitle)"
        )

        # Cleanup
        ingestor.state_tracker.close()
        ingestor.weaviate_client.close()

    except Exception as e:
        logger.error(f"Error during re-ingestion: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


def watch_vault(vault_path: str | None = None):
    """
    Watch vault for changes and ingest automatically.

    Args:
        vault_path: Optional path to vault (overrides env var)
    """
    try:
        config = IngestionConfig()

        if vault_path:
            config.vault_path = vault_path

        config.validate()

        logger.info("=" * 60)
        logger.info("Starting Vault Watcher")
        logger.info("=" * 60)
        logger.info(f"Vault: {config.vault_path}")
        logger.info(f"Weaviate: {config.weaviate_host}:{config.weaviate_port}")
        logger.info(f"Ollama: {config.ollama_base_url}")
        logger.info(f"State DB: {config.state_db_path}")
        logger.info(f"Debounce: {config.watch_debounce}s")
        logger.info("=" * 60)

        ingestor = create_ingestor(config)

        # Define callback for file changes
        def on_file_change(file_path: str):
            """Process a single file when it changes."""
            logger.info(f"\n{'=' * 60}")
            logger.info(f"Processing: {file_path}")
            logger.info("=" * 60)

            try:
                chunk_count = ingestor.ingest_file(file_path)
                logger.info(f"✓ Created {chunk_count} chunk(s)")
            except Exception as e:
                logger.error(f"✗ Error: {e}")

        # Create and start watcher
        watcher = VaultWatcher(
            vault_path=config.vault_path,
            on_file_change=on_file_change,
            debounce_seconds=config.watch_debounce,
        )

        logger.info("\nWatcher started. Monitoring for changes...")
        logger.info("Press Ctrl+C to stop.\n")

        # Run forever
        watcher.run_forever()

        # Cleanup on exit
        logger.info("\nCleaning up...")
        ingestor.state_tracker.close()
        ingestor.weaviate_client.close()

    except Exception as e:
        logger.error(f"Error during watching: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


def main():
    """Main CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Mnemosyne - Obsidian Vault Ingestion",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Ingest entire vault once (manual mode)
  python -m mnemosyne.cli.ingest once

  # Watch vault for changes (automatic mode)
  python -m mnemosyne.cli.ingest watch

  # Specify vault path explicitly
  python -m mnemosyne.cli.ingest once --vault-path /path/to/vault

  # Re-ingest vault with structure metadata (Story 020)
  python -m mnemosyne.cli.ingest re-ingest --force

Environment Variables:
  OBSIDIAN_VAULT_PATH     Path to Obsidian vault (required)
  WEAVIATE_HTTP_HOST      Weaviate host (default: localhost)
  WEAVIATE_HTTP_PORT      Weaviate HTTP port (default: 8080)
  WEAVIATE_GRPC_PORT      Weaviate gRPC port (default: 50051)
  OLLAMA_BASE_URL         Ollama API URL (default: http://localhost:11434)
  INGESTION_STATE_DB      State database path (default: ingestion_state.db)
  CHUNK_SIZE              Chunk size in characters (default: 400)
  CHUNK_OVERLAP           Chunk overlap in characters (default: 100)
  WATCH_DEBOUNCE_SECONDS  Debounce time for file events (default: 2.0)
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # 'once' command
    parser_once = subparsers.add_parser("once", help="Ingest entire vault once (manual mode)")
    parser_once.add_argument(
        "--vault-path", help="Path to Obsidian vault (overrides OBSIDIAN_VAULT_PATH env var)"
    )

    # 'watch' command
    parser_watch = subparsers.add_parser(
        "watch", help="Watch vault for changes and ingest automatically"
    )
    parser_watch.add_argument(
        "--vault-path", help="Path to Obsidian vault (overrides OBSIDIAN_VAULT_PATH env var)"
    )

    # 're-ingest' command (Story 020)
    parser_reingest = subparsers.add_parser(
        "re-ingest",
        help="Re-ingest entire vault with structure metadata (Story 020)",
    )
    parser_reingest.add_argument(
        "--vault-path", help="Path to Obsidian vault (overrides OBSIDIAN_VAULT_PATH env var)"
    )
    parser_reingest.add_argument(
        "--force",
        action="store_true",
        help="Clear all ingestion state and force re-ingestion of all files",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "once":
        ingest_once(args.vault_path)
    elif args.command == "watch":
        watch_vault(args.vault_path)
    elif args.command == "re-ingest":
        re_ingest_vault(args.vault_path, args.force)


if __name__ == "__main__":
    main()
