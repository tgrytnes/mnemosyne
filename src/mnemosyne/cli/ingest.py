"""
CLI commands for Obsidian vault ingestion.

Provides commands for manual and automatic ingestion of Obsidian vault content.
"""

import logging
import os
import signal
import sys
import time
from pathlib import Path

import click
import weaviate

from mnemosyne.config.providers import ProviderConfig
from mnemosyne.providers.factory import create_embedding_provider, create_llm_provider

from ..aletheia.email_ingest import EmailIngestConfig, EmailIngestor
from ..aletheia.ingestion_reset import (
    ResetOptions,
    apply_reset_plan,
    build_reset_environment,
    build_reset_plan,
    validate_reset_options,
)
from ..aletheia.ingestion_state import IngestionStateTracker
from ..aletheia.ingestion_watch_hub import IngestionWatchConfig, IngestionWatchHub
from ..aletheia.obsidian_ingestor import ObsidianIngestor
from ..aletheia.pdf_ingestor import PDFIngestor

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

shutdown_flag = False


def ingest_signal_handler(signum, frame):
    """Handle shutdown signals for watcher mode."""
    global shutdown_flag
    logger.info("Received signal %s, shutting down watcher...", signum)
    shutdown_flag = True


def is_watch_enabled() -> bool:
    """Return True when the watch loop should run."""
    return os.getenv("INGESTOR_WATCH_ENABLED", "true").lower() not in {"false", "0", "no"}


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
        self.chunking_strategy = os.getenv("CHUNKING_STRATEGY", "semantic_consensus")
        self.chunking_augmentation = os.getenv("CHUNKING_AUGMENTATION", "none")
        self.semantic_min_chunk_size = int(os.getenv("SEMANTIC_MIN_CHUNK_SIZE", "100"))
        self.semantic_max_chunk_size = int(os.getenv("SEMANTIC_MAX_CHUNK_SIZE", "1000"))
        self.semantic_model = os.getenv("SEMANTIC_LLM_MODEL", "glm-4.6v-flash")
        self.semantic_temperature = float(os.getenv("SEMANTIC_LLM_TEMP", "0.2"))
        self.semantic_request_timeout = float(os.getenv("SEMANTIC_REQUEST_TIMEOUT", "5.0"))
        self.semantic_total_timeout = float(os.getenv("SEMANTIC_TOTAL_TIMEOUT", "30.0"))
        self.semantic_json_max_chars = int(os.getenv("SEMANTIC_JSON_MAX_CHARS", "12000"))
        self.semantic_json_max_tokens = int(os.getenv("SEMANTIC_JSON_MAX_TOKENS", "512"))
        self.semantic_json_max_prompt_tokens = int(
            os.getenv("SEMANTIC_JSON_MAX_PROMPT_TOKENS", "16000")
        )
        self.section_semantic_min_length = int(os.getenv("SECTION_SEMANTIC_MIN_LENGTH", "1000"))
        self.semantic_cosine_threshold = float(os.getenv("SEMANTIC_COSINE_THRESHOLD", "0.78"))
        self.semantic_merge_similarity_threshold = float(
            os.getenv("SEMANTIC_MERGE_SIMILARITY_THRESHOLD", "0.85")
        )
        self.semantic_consensus_tolerance = int(os.getenv("SEMANTIC_CONSENSUS_TOLERANCE", "20"))
        self.semantic_cosine_min_chunk_size = int(
            os.getenv("SEMANTIC_COSINE_MIN_CHUNK_SIZE", "100")
        )
        self.semantic_cosine_max_chunk_size = int(
            os.getenv("SEMANTIC_COSINE_MAX_CHUNK_SIZE", "1000")
        )
        self.semantic_cosine_embedding_model = os.getenv("SEMANTIC_COSINE_EMBEDDING_MODEL", "")
        self.semantic_merge_max_embed_chars = int(
            os.getenv("SEMANTIC_MERGE_MAX_EMBED_CHARS", "2000")
        )
        self.contextual_llm_provider = os.getenv("CONTEXTUAL_LLM_PROVIDER")
        self.contextual_llm_model = os.getenv("CONTEXTUAL_LLM_MODEL", "")
        self.contextual_max_doc_chars = int(os.getenv("CONTEXTUAL_MAX_DOC_CHARS", "4000"))
        self.doc_summary_llm_model = os.getenv("DOC_SUMMARY_LLM_MODEL", "")
        self.doc_summary_max_chars = int(os.getenv("DOC_SUMMARY_MAX_CHARS", "200"))
        self.doc_summary_temperature = float(os.getenv("DOC_SUMMARY_TEMPERATURE", "0.2"))
        self.late_chunk_adapter = os.getenv("LATE_CHUNK_ADAPTER", "retrieval.passage")
        self.late_chunk_embedding_model = os.getenv("LATE_CHUNK_EMBEDDING_MODEL", "")
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

        if self.chunking_augmentation.lower() not in {"none", "late", "contextual", "doc_summary"}:
            raise ValueError(
                "CHUNKING_AUGMENTATION must be one of: none, late, contextual, doc_summary."
            )

        return True


def create_ingestor(
    config: IngestionConfig,
    provider_config: ProviderConfig,
    weaviate_client=None,
) -> ObsidianIngestor:
    """
    Create ObsidianIngestor instance with configuration.

    Args:
        config: Ingestion configuration
        provider_config: Provider configuration

    Returns:
        Configured ObsidianIngestor instance
    """
    if weaviate_client is None:
        logger.info("Connecting to Weaviate...")
        weaviate_client = weaviate.connect_to_local(
            host=config.weaviate_host,
            port=config.weaviate_port,
            grpc_port=config.weaviate_grpc_port,
        )

    llm_provider = create_llm_provider(provider_config)
    embedding_provider = create_embedding_provider(provider_config)

    contextual_llm_provider = llm_provider
    contextual_provider_name = provider_config.llm_provider
    if config.contextual_llm_provider:
        contextual_provider_config = ProviderConfig.from_env()
        contextual_provider_config.llm_provider = config.contextual_llm_provider
        contextual_llm_provider = create_llm_provider(contextual_provider_config)
        contextual_provider_name = config.contextual_llm_provider

    contextual_llm_model = config.contextual_llm_model
    if (
        config.chunking_augmentation == "contextual"
        and not contextual_llm_model
        and contextual_provider_name == "fastapi"
    ):
        contextual_llm_model = "Qwen3_8B"
        logger.info(
            "Defaulting contextual LLM model to %s for provider %s.",
            contextual_llm_model,
            contextual_provider_name,
        )

    logger.info("Initializing state tracker...")
    state_tracker = IngestionStateTracker(config.state_db_path)

    logger.info("Creating ingestor...")
    ingestor = ObsidianIngestor(
        vault_path=config.vault_path,
        weaviate_client=weaviate_client,
        embedding_provider=embedding_provider,
        llm_provider=llm_provider,
        state_tracker=state_tracker,
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
        chunking_strategy=config.chunking_strategy,
        chunking_augmentation=config.chunking_augmentation,
        semantic_min_chunk_size=config.semantic_min_chunk_size,
        semantic_max_chunk_size=config.semantic_max_chunk_size,
        semantic_model=config.semantic_model,
        semantic_temperature=config.semantic_temperature,
        semantic_request_timeout=config.semantic_request_timeout,
        semantic_total_timeout=config.semantic_total_timeout,
        semantic_json_max_chars=config.semantic_json_max_chars,
        semantic_json_max_tokens=config.semantic_json_max_tokens,
        semantic_json_max_prompt_tokens=config.semantic_json_max_prompt_tokens,
        section_semantic_min_length=config.section_semantic_min_length,
        semantic_cosine_threshold=config.semantic_cosine_threshold,
        semantic_merge_similarity_threshold=config.semantic_merge_similarity_threshold,
        semantic_consensus_tolerance=config.semantic_consensus_tolerance,
        semantic_cosine_min_chunk_size=config.semantic_cosine_min_chunk_size,
        semantic_cosine_max_chunk_size=config.semantic_cosine_max_chunk_size,
        semantic_cosine_embedding_model=config.semantic_cosine_embedding_model,
        semantic_merge_max_embed_chars=config.semantic_merge_max_embed_chars,
        contextual_llm_provider=contextual_llm_provider,
        contextual_llm_model=contextual_llm_model,
        contextual_max_doc_chars=config.contextual_max_doc_chars,
        doc_summary_llm_model=config.doc_summary_llm_model,
        doc_summary_max_chars=config.doc_summary_max_chars,
        doc_summary_temperature=config.doc_summary_temperature,
        late_chunk_adapter=config.late_chunk_adapter,
        late_chunk_embedding_model=config.late_chunk_embedding_model,
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
        provider_config = ProviderConfig.from_env()

        if vault_path:
            config.vault_path = vault_path

        config.validate()

        logger.info("=" * 60)
        logger.info("Starting Manual Vault Ingestion")
        logger.info("=" * 60)
        logger.info(f"Vault: {config.vault_path}")
        logger.info(f"Weaviate: {config.weaviate_host}:{config.weaviate_port}")
        logger.info(f"LLM Provider: {provider_config.llm_provider}")
        logger.info(f"Embedding Provider: {provider_config.embedding_provider}")
        logger.info(f"State DB: {config.state_db_path}")
        logger.info(f"Chunking Augmentation: {config.chunking_augmentation}")
        logger.info("=" * 60)

        ingestor = create_ingestor(config, provider_config)

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
        provider_config = ProviderConfig.from_env()

        if vault_path:
            config.vault_path = vault_path

        config.validate()

        logger.info("=" * 60)
        logger.info("Re-Ingesting Vault with Structure Metadata")
        logger.info("=" * 60)
        logger.info(f"Vault: {config.vault_path}")
        logger.info(f"Weaviate: {config.weaviate_host}:{config.weaviate_port}")
        logger.info(f"LLM Provider: {provider_config.llm_provider}")
        logger.info(f"Embedding Provider: {provider_config.embedding_provider}")
        logger.info(f"Force mode: {force}")
        logger.info("=" * 60)

        ingestor = create_ingestor(config, provider_config)

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
    Watch ingestion sources for changes and ingest automatically.

    Args:
        vault_path: Optional path to vault (overrides env var)
    """
    hub = None
    ingestor = None
    email_ingestor = None
    pdf_ingestor = None
    weaviate_client = None

    try:
        if not is_watch_enabled():
            logger.info("Ingestor watch disabled; exiting.")
            return

        watch_config = IngestionWatchConfig()
        if vault_path:
            watch_config.vault_path = vault_path

        if not (
            watch_config.watch_vault_enabled
            or watch_config.watch_email_enabled
            or watch_config.watch_pdf_enabled
        ):
            logger.info("No ingestion watchers enabled; exiting.")
            return

        config = IngestionConfig()
        provider_config = ProviderConfig.from_env()
        if vault_path:
            config.vault_path = vault_path

        logger.info("Connecting to Weaviate...")
        weaviate_client = weaviate.connect_to_local(
            host=config.weaviate_host,
            port=config.weaviate_port,
            grpc_port=config.weaviate_grpc_port,
        )

        llm_provider = create_llm_provider(provider_config)
        embedding_provider = create_embedding_provider(provider_config)

        if watch_config.watch_vault_enabled:
            config.validate()
            ingestor = create_ingestor(config, provider_config, weaviate_client=weaviate_client)

        if watch_config.watch_email_enabled:
            email_config = EmailIngestConfig.from_env()
            email_ingestor = EmailIngestor(
                config=email_config,
                weaviate_client=weaviate_client,
                embedding_provider=embedding_provider,
                llm_provider=llm_provider,
            )

        if watch_config.watch_pdf_enabled:
            pdf_scan_path = watch_config.pdf_scan_path
            if not pdf_scan_path:
                raise ValueError("PDF_SCAN_PATH environment variable not set")
            pdf_ingestor = PDFIngestor(
                input_dir=str(pdf_scan_path),
                weaviate_client=weaviate_client,
                embedder=lambda text: embedding_provider.embed(model="", text=text),
            )

        def on_vault_change(file_path: str) -> None:
            if not ingestor:
                return
            logger.info(f"\n{'=' * 60}")
            logger.info(f"Processing vault file: {file_path}")
            logger.info("=" * 60)
            try:
                chunk_count = ingestor.ingest_file(file_path)
                logger.info(f"✓ Created {chunk_count} chunk(s)")
            except Exception as exc:
                logger.error(f"✗ Error: {exc}")

        def on_email_change(file_path: str) -> None:
            if not email_ingestor:
                return
            logger.info(f"\n{'=' * 60}")
            logger.info(f"Processing email file: {file_path}")
            logger.info("=" * 60)
            try:
                summary = email_ingestor.ingest_file(file_path)
                logger.info(
                    "✓ Email ingest loaded=%s stored=%s duplicates=%s rejected=%s",
                    summary.total_loaded,
                    summary.total_stored,
                    summary.duplicates,
                    summary.rejected,
                )
            except Exception as exc:
                logger.error(f"✗ Error: {exc}")

        def on_pdf_change(file_path: str) -> None:
            if not pdf_ingestor:
                return
            logger.info(f"\n{'=' * 60}")
            logger.info(f"Processing PDF file: {file_path}")
            logger.info("=" * 60)
            try:
                chunk_count = pdf_ingestor.ingest_file(file_path)
                logger.info(f"✓ PDF ingest created {chunk_count} chunk(s)")
            except Exception as exc:
                logger.error(f"✗ Error: {exc}")

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, ingest_signal_handler)
        signal.signal(signal.SIGINT, ingest_signal_handler)

        logger.info("=" * 60)
        logger.info("Starting Ingestion Watchers")
        logger.info("=" * 60)
        logger.info("Watch vault enabled: %s", watch_config.watch_vault_enabled)
        logger.info("Watch email enabled: %s", watch_config.watch_email_enabled)
        logger.info("Watch PDF enabled: %s", watch_config.watch_pdf_enabled)
        logger.info("=" * 60)

        hub = IngestionWatchHub(
            config=watch_config,
            on_vault_change=on_vault_change,
            on_email_change=on_email_change,
            on_pdf_change=on_pdf_change,
        )

        logger.info("\nWatcher hub started. Monitoring for changes...")
        logger.info("Press Ctrl+C to stop.\n")

        hub.start()
        while not shutdown_flag:
            time.sleep(1)

    except Exception as e:
        logger.error(f"Error during watching: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        if hub:
            logger.info("\nCleaning up...")
            hub.stop()
        if ingestor:
            ingestor.state_tracker.close()
        if weaviate_client:
            weaviate_client.close()


@click.group("ingest")
def ingest_cli():
    """Mnemosyne - Obsidian Vault Ingestion"""
    pass


@ingest_cli.command("once")
@click.option("--vault-path", help="Path to Obsidian vault (overrides OBSIDIAN_VAULT_PATH env var)")
def once(vault_path: str | None = None):
    """Ingest entire vault once (manual mode)."""
    ingest_once(vault_path)


@ingest_cli.command("watch")
@click.option("--vault-path", help="Path to Obsidian vault (overrides OBSIDIAN_VAULT_PATH env var)")
def watch(vault_path: str | None = None):
    """Watch vault for changes and ingest automatically."""
    watch_vault(vault_path)


@ingest_cli.command("re-ingest")
@click.option("--vault-path", help="Path to Obsidian vault (overrides OBSIDIAN_VAULT_PATH env var)")
@click.option(
    "--force",
    is_flag=True,
    help="Clear all ingestion state and force re-ingestion of all files",
)
def re_ingest(vault_path: str | None = None, force: bool = False):
    """Re-ingest entire vault with structure metadata."""
    re_ingest_vault(vault_path, force)


@ingest_cli.command("reset")
@click.option("--env", "env_name", type=click.Choice(["dev", "staging", "prod"]), required=True)
@click.option("--vault", is_flag=True, help="Reset vault ingestion state and data.")
@click.option("--email", is_flag=True, help="Reset email ingestion state and data.")
@click.option("--pdf", is_flag=True, help="Reset PDF ingestion state and data.")
@click.option("--weaviate", is_flag=True, help="Allow Weaviate deletions for selected targets.")
@click.option("--postgres", is_flag=True, help="Allow Postgres table truncation.")
@click.option(
    "--weaviate-collection",
    "weaviate_collections",
    multiple=True,
    help="Explicit Weaviate collection to delete (repeatable).",
)
@click.option(
    "--postgres-table",
    "postgres_tables",
    multiple=True,
    help="Postgres table to truncate (repeatable).",
)
@click.option("--dry-run", is_flag=True, help="Print actions without executing.")
@click.option("--force", is_flag=True, help="Required for staging/prod resets.")
def reset(
    env_name: str,
    vault: bool,
    email: bool,
    pdf: bool,
    weaviate: bool,
    postgres: bool,
    weaviate_collections: tuple[str, ...],
    postgres_tables: tuple[str, ...],
    dry_run: bool,
    force: bool,
):
    """Reset ingestion state/data in a controlled, environment-specific way."""
    options = ResetOptions(
        env=env_name,
        vault=vault,
        email=email,
        pdf=pdf,
        weaviate=weaviate,
        postgres=postgres,
        weaviate_collections=list(weaviate_collections),
        postgres_tables=list(postgres_tables),
        dry_run=dry_run,
        force=force,
    )

    try:
        validate_reset_options(options)
    except ValueError as exc:
        logger.error("%s", exc)
        raise SystemExit(1)

    env = build_reset_environment(env_name)
    plan = build_reset_plan(options, env)
    if not plan:
        logger.error("No reset actions were generated.")
        raise SystemExit(1)

    click.echo("Planned reset actions:")
    for action in plan:
        details = f" {action.details}" if action.details else ""
        click.echo(f"- {action.action}: {action.target}{details}")

    if dry_run:
        click.echo("Dry run enabled; no changes were made.")
        return

    apply_reset_plan(plan, env)
