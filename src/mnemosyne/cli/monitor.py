import argparse
import logging
import os
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class MonitorCLIConfig:
    """Configuration for running the Monitor Agent."""

    def __init__(self) -> None:
        self.confidence_threshold = float(os.getenv("MONITOR_CONFIDENCE_THRESHOLD", "0.7"))
        self.scan_limit = int(os.getenv("MONITOR_SCAN_LIMIT", "200"))
        self.cooldown_days = int(os.getenv("MONITOR_COOLDOWN_DAYS", "14"))
        self.max_asks = int(os.getenv("MONITOR_MAX_ASKS", "3"))
        self.confidence_delta = float(os.getenv("MONITOR_CONFIDENCE_DELTA", "0.15"))
        self.queue_db_path = os.getenv("MONITOR_QUEUE_DB_PATH", "monitor_queue.db")
        self.state_db_path = os.getenv("MONITOR_STATE_DB_PATH", "monitor_state.db")
        self.outbox_db_path = os.getenv("MONITOR_OUTBOX_DB_PATH", "monitor_outbox.db")
        self.weaviate_host = os.getenv("WEAVIATE_HTTP_HOST", "localhost")
        self.weaviate_port = int(os.getenv("WEAVIATE_HTTP_PORT", "8080"))
        self.weaviate_grpc_port = int(os.getenv("WEAVIATE_GRPC_PORT", "50051"))
        self.postgres_host = os.getenv("POSTGRES_HOST", "localhost")
        self.postgres_port = int(os.getenv("POSTGRES_PORT", "5432"))
        self.postgres_db = os.getenv("POSTGRES_DB", "mnemosyne")
        self.postgres_user = os.getenv("POSTGRES_USER", "postgres")
        self.postgres_password = os.getenv("POSTGRES_PASSWORD", "postgres")


def run_monitor() -> None:
    try:
        config = MonitorCLIConfig()

        logger.info("=" * 60)
        logger.info("Starting Monitor Agent")
        logger.info("=" * 60)
        logger.info(
            "Weaviate: %s:%s (grpc %s)",
            config.weaviate_host,
            config.weaviate_port,
            config.weaviate_grpc_port,
        )
        logger.info(
            "Postgres: %s:%s/%s",
            config.postgres_host,
            config.postgres_port,
            config.postgres_db,
        )
        logger.info("=" * 60)

        import psycopg2
        import weaviate

        from mnemosyne.alexandria.weaviate_schema import Discoveries, WeaviateSchemaManager
        from mnemosyne.argus.scout.monitor_agent import (
            MessageOutbox,
            MonitorAgent,
            MonitorConfig,
            MonitorStateStore,
            PostgresProjectRepository,
            ProposalQueue,
            WeaviateDiscoveryReader,
        )

        weaviate_client = weaviate.connect_to_local(
            host=config.weaviate_host,
            port=config.weaviate_port,
            grpc_port=config.weaviate_grpc_port,
        )
        WeaviateSchemaManager(weaviate_client).ensure_collection_exists(Discoveries.collection_name)

        postgres_connection = psycopg2.connect(
            host=config.postgres_host,
            port=config.postgres_port,
            database=config.postgres_db,
            user=config.postgres_user,
            password=config.postgres_password,
        )

        proposal_queue = ProposalQueue(postgres_connection)
        state_store = MonitorStateStore(postgres_connection)
        outbox = MessageOutbox(postgres_connection)

        reader = WeaviateDiscoveryReader(weaviate_client)
        projects = PostgresProjectRepository(postgres_connection)
        agent = MonitorAgent(
            discovery_reader=reader,
            project_repository=projects,
            proposal_queue=proposal_queue,
            state_store=state_store,
            outbox=outbox,
            config=MonitorConfig(
                confidence_threshold=config.confidence_threshold,
                scan_limit=config.scan_limit,
                cooldown_days=config.cooldown_days,
                max_asks=config.max_asks,
                confidence_delta=config.confidence_delta,
            ),
        )

        agent.run()

        proposal_queue.close()
        state_store.close()
        outbox.close()
        postgres_connection.close()
        weaviate_client.close()

    except Exception as exc:
        logger.error("Monitor CLI failed: %s", exc)
        import traceback

        traceback.print_exc()
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mnemosyne - Monitor Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    subparsers.add_parser("run", help="Run a single monitor reconciliation pass")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "run":
        run_monitor()


if __name__ == "__main__":
    main()
