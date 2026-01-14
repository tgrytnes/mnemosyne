"""Periodic scheduler for batch agents (cluster, scout, graph, monitor, PM, gatekeeper)."""

import logging
import os
import signal
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

import click
import psycopg2
import weaviate
from neo4j import GraphDatabase

from mnemosyne.aletheia.agents.project_manager import ProjectManagerAgent
from mnemosyne.aletheia.obsidian_sync.obsidian_sync import ObsidianSyncManager
from mnemosyne.alexandria.communication_intents import PMIntentQueue
from mnemosyne.alexandria.message_outbox import MessageOutbox
from mnemosyne.alexandria.sql_gatekeeper import GatekeeperConfig, SQLProjectGatekeeper
from mnemosyne.alexandria.weaviate_schema import (
    ClusterCentroidCollection,
    ClusterCentroidLethe,
    TheLethe,
    TheMuses,
)
from mnemosyne.argus.cluster_profile_bootstrap import ClusterProfileBootstrapper
from mnemosyne.argus.graph_taxonomy import GraphTaxonomyConfig
from mnemosyne.argus.graph_taxonomy_pipeline import GraphTaxonomyPipeline
from mnemosyne.argus.scout.monitor_agent import (
    MonitorAgent,
    MonitorConfig,
    MonitorStateStore,
    PostgresProjectRepository,
    ProposalQueue,
    WeaviateDiscoveryReader,
)
from mnemosyne.argus.scout.radar import ConceptPrototype
from mnemosyne.argus.scout.scout_runner import ScoutConfig, ScoutRunner
from mnemosyne.cli.cluster import ClusteringConfig, run_clustering
from mnemosyne.config.providers import ProviderConfig
from mnemosyne.providers.factory import create_embedding_provider, create_llm_provider

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global flag for graceful shutdown
shutdown_flag = False


def _parse_bool(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return value.lower() not in {"false", "0", "no"}


@dataclass
class JobSpec:
    name: str
    interval_seconds: int
    enabled: bool
    run: Callable[[], None]
    last_run: datetime | None = None


class SchedulerConfig:
    """Configuration for periodic batch jobs."""

    def __init__(self) -> None:
        self.cluster_interval_hours = int(os.getenv("CLUSTER_INTERVAL_HOURS", "24"))
        self.scout_interval_hours = int(os.getenv("SCOUT_INTERVAL_HOURS", "24"))
        self.graph_taxonomy_interval_hours = int(os.getenv("GRAPH_TAXONOMY_INTERVAL_HOURS", "24"))
        self.monitor_interval_minutes = int(os.getenv("MONITOR_INTERVAL_MINUTES", "60"))
        self.gatekeeper_interval_minutes = int(os.getenv("GATEKEEPER_INTERVAL_MINUTES", "60"))
        self.pm_check_interval_minutes = int(os.getenv("PM_CHECK_INTERVAL_MINUTES", "30"))
        self.pm_pressure_update_interval_hours = int(
            os.getenv("PM_PRESSURE_UPDATE_INTERVAL_HOURS", "1")
        )
        self.pm_obsidian_sync_interval_minutes = int(
            os.getenv("PM_OBSIDIAN_SYNC_INTERVAL_MINUTES", "15")
        )

        self.cluster_enabled = _parse_bool(os.getenv("CLUSTER_ENABLED"), True)
        self.scout_enabled = _parse_bool(os.getenv("SCOUT_ENABLED"), True)
        self.graph_taxonomy_enabled = _parse_bool(os.getenv("GRAPH_TAXONOMY_ENABLED"), True)
        self.monitor_enabled = _parse_bool(os.getenv("MONITOR_ENABLED"), True)
        self.gatekeeper_enabled = _parse_bool(os.getenv("GATEKEEPER_ENABLED"), True)
        self.pm_check_enabled = _parse_bool(os.getenv("PM_CHECK_ENABLED"), True)
        self.pm_pressure_update_enabled = _parse_bool(os.getenv("PM_PRESSURE_UPDATE_ENABLED"), True)
        self.pm_obsidian_sync_enabled = _parse_bool(os.getenv("PM_OBSIDIAN_SYNC_ENABLED"), True)


class PeriodicScheduler:
    """Scheduler that runs jobs when their interval is due."""

    def __init__(self, jobs: list[JobSpec], now_provider: Callable[[], datetime] | None = None):
        self._jobs = jobs
        self._now = now_provider or datetime.now
        self._running = False

    def run_once(self) -> None:
        if self._running:
            return
        self._running = True
        now = self._now()
        try:
            for job in self._jobs:
                if not job.enabled:
                    continue
                if job.last_run and (now - job.last_run).total_seconds() <= job.interval_seconds:
                    continue
                try:
                    job.run()
                except Exception as exc:
                    logger.error("Scheduled job %s failed: %s", job.name, exc)
                finally:
                    job.last_run = now
        finally:
            self._running = False


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    global shutdown_flag
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_flag = True


def is_scheduler_enabled() -> bool:
    """Return True when the scheduler loop should run."""
    return os.getenv("SCHEDULER_ENABLED", "true").lower() not in {"false", "0", "no"}


def idle_until_shutdown():
    """Keep the scheduler container alive when disabled."""
    logger.info("Scheduler is disabled; entering idle mode.")
    while not shutdown_flag:
        time.sleep(60)


def run_clustering_task():
    """Run clustering task."""
    logger.info("=" * 60)
    logger.info("Running periodic clustering task")
    logger.info("=" * 60)
    try:
        config = ClusteringConfig()
        clustering_targets = [
            (
                TheMuses.collection_name,
                ClusterCentroidCollection.collection_name,
                config.n_clusters_muses,
            ),
            (
                TheLethe.collection_name,
                ClusterCentroidLethe.collection_name,
                config.n_clusters_lethe,
            ),
        ]
        for collection_name, centroid_name, n_clusters in clustering_targets:
            logger.info(
                "Clustering %s with %s clusters",
                collection_name,
                n_clusters,
            )
            run_clustering(
                n_clusters,
                collection_name=collection_name,
                centroid_collection_name=centroid_name,
            )
        logger.info("Clustering task completed successfully")
    except Exception as exc:
        logger.exception("Clustering task failed: %s", exc)
        raise


def run_scout_task():
    """Run Scout pattern detection task."""
    logger.info("=" * 60)
    logger.info("Running periodic Scout pattern detection")
    logger.info("=" * 60)

    weaviate_client = None
    try:
        # Get configuration from environment
        weaviate_host = os.getenv("WEAVIATE_HTTP_HOST", "localhost")
        weaviate_port = int(os.getenv("WEAVIATE_HTTP_PORT", "8080"))
        weaviate_grpc_port = int(os.getenv("WEAVIATE_GRPC_PORT", "50051"))

        provider_config = ProviderConfig.from_env()

        # Connect to services
        weaviate_client = weaviate.connect_to_local(
            host=weaviate_host,
            port=weaviate_port,
            grpc_port=weaviate_grpc_port,
        )

        embedding_provider = create_embedding_provider(provider_config)

        # Create embedder function
        def embedder(text: str) -> list[float]:
            return embedding_provider.embed(model="", text=text)

        # Define project concept patterns
        project_positives = [
            "Renovate the house: budget, timeline, contractors, materials.",
            "Plan education goals: coursework, tuition, schedule, deadlines.",
            "Design a training program with weekly sessions and milestones.",
            "Build a home lab docker project: services, deploy, test.",
            "Launch a product: requirements, development, testing, release.",
            "Organize an event: venue, schedule, speakers, logistics.",
        ]

        project_negatives = [
            "Historical summary and background notes.",
            "Glossary of database schema definitions.",
            "Recipe notes and cooking techniques.",
            "Random thoughts and observations.",
            "Reading notes from a book.",
        ]

        project_concept = ConceptPrototype(
            key="project_private",
            positive_texts=project_positives,
            negative_texts=project_negatives,
            threshold=0.05,
        )

        # Configure and run Scout
        config = ScoutConfig(
            project_concepts=[project_concept],
            emerging_window_days=30,
            emerging_min_recent=3,
            emerging_max_previous=1,
            orphan_min_neighbors=1,
            contradiction_similarity_threshold=0.75,
            contradiction_polarity_threshold=0.5,
            dedup_similarity_threshold=0.8,
            cluster_representation_k=5,
        )

        runner = ScoutRunner(client=weaviate_client, embedder=embedder, config=config)
        summary = runner.run()

        logger.info(f"Scout task completed: {summary.clusters_analyzed} clusters analyzed")
        logger.info(f"Detections: {summary.detections_by_type}")

    except Exception as exc:
        logger.exception("Scout task failed: %s", exc)
        raise
    finally:
        if weaviate_client:
            weaviate_client.close()


def run_graph_taxonomy_task():
    """Run graph taxonomy building task."""
    logger.info("=" * 60)
    logger.info("Running periodic graph taxonomy building")
    logger.info("=" * 60)

    weaviate_client = None
    postgres_conn = None
    neo4j_driver = None
    try:
        # Get configuration from environment
        graph_taxonomy_source = os.getenv("GRAPH_TAXONOMY_SOURCE", "lethe").lower()
        weaviate_host = os.getenv("WEAVIATE_HTTP_HOST", "localhost")
        weaviate_port = int(os.getenv("WEAVIATE_HTTP_PORT", "8080"))
        weaviate_grpc_port = int(os.getenv("WEAVIATE_GRPC_PORT", "50051"))

        postgres_host = os.getenv("POSTGRES_HOST", "localhost")
        postgres_port = int(os.getenv("POSTGRES_PORT", "5432"))
        postgres_db = os.getenv("POSTGRES_DB", "mnemosyne_dev")
        postgres_user = os.getenv("POSTGRES_USER", "postgres")
        postgres_password = os.getenv("POSTGRES_PASSWORD", "")

        neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        neo4j_password = os.getenv("NEO4J_PASSWORD", "neo4j")

        provider_config = ProviderConfig.from_env()

        # Connect to services
        weaviate_client = weaviate.connect_to_local(
            host=weaviate_host,
            port=weaviate_port,
            grpc_port=weaviate_grpc_port,
        )

        postgres_conn = psycopg2.connect(
            host=postgres_host,
            port=postgres_port,
            dbname=postgres_db,
            user=postgres_user,
            password=postgres_password,
        )

        neo4j_driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        llm_provider = create_llm_provider(provider_config)

        # Configure graph taxonomy
        config = GraphTaxonomyConfig()
        if graph_taxonomy_source == "lethe":
            centroid_collection_name = ClusterCentroidLethe.collection_name
            chunk_collection_name = TheLethe.collection_name
            text_property = "body"
            source_property = "sourcePath"
            heading_property = "subject"
            chunk_index_property = "chunkIndex"
        else:
            centroid_collection_name = ClusterCentroidCollection.collection_name
            chunk_collection_name = TheMuses.collection_name
            text_property = "text"
            source_property = "sourceFile"
            heading_property = "headingPath"
            chunk_index_property = "chunkIndex"
        logger.info("Graph taxonomy source: %s", graph_taxonomy_source)

        bootstrapper = ClusterProfileBootstrapper(
            weaviate_client=weaviate_client,
            postgres_connection=postgres_conn,
            llm_provider=llm_provider,
            profile_source=graph_taxonomy_source,
            centroid_collection_name=centroid_collection_name,
            chunk_collection_name=chunk_collection_name,
            text_property=text_property,
            source_property=source_property,
            heading_property=heading_property,
            chunk_index_property=chunk_index_property,
        )

        # Build graph
        pipeline = GraphTaxonomyPipeline(
            weaviate_client=weaviate_client,
            postgres_connection=postgres_conn,
            neo4j_driver=neo4j_driver,
            config=config,
            centroid_collection_name=centroid_collection_name,
            profile_source=graph_taxonomy_source,
            profile_bootstrapper=bootstrapper,
        )

        result = pipeline.build_graph()

        logger.info(
            f"Graph taxonomy task completed: "
            f"{len(result['nodes'])} nodes, {len(result['edges'])} edges"
        )

    except Exception as exc:
        logger.exception("Graph taxonomy task failed: %s", exc)
        raise
    finally:
        if weaviate_client:
            weaviate_client.close()
        if postgres_conn:
            postgres_conn.close()
        if neo4j_driver:
            neo4j_driver.close()


def run_monitor_agent_task() -> dict[str, object]:
    """Run monitor agent proposal generation task."""
    logger.info("=" * 60)
    logger.info("Running periodic Monitor Agent")
    logger.info("=" * 60)

    defaults = MonitorConfig()
    confidence_threshold = float(
        os.getenv("MONITOR_CONFIDENCE_THRESHOLD", str(defaults.confidence_threshold))
    )
    scan_limit = int(os.getenv("MONITOR_SCAN_LIMIT", str(defaults.scan_limit)))
    config = MonitorConfig(
        confidence_threshold=confidence_threshold,
        scan_limit=scan_limit,
        cooldown_days=defaults.cooldown_days,
        max_asks=defaults.max_asks,
        confidence_delta=defaults.confidence_delta,
    )

    weaviate_client = None
    postgres_conn = None
    try:
        # Get configuration from environment
        weaviate_host = os.getenv("WEAVIATE_HTTP_HOST", "localhost")
        weaviate_port = int(os.getenv("WEAVIATE_HTTP_PORT", "8080"))
        weaviate_grpc_port = int(os.getenv("WEAVIATE_GRPC_PORT", "50051"))

        postgres_host = os.getenv("POSTGRES_HOST", "localhost")
        postgres_port = int(os.getenv("POSTGRES_PORT", "5432"))
        postgres_db = os.getenv("POSTGRES_DB", "mnemosyne_dev")
        postgres_user = os.getenv("POSTGRES_USER", "postgres")
        postgres_password = os.getenv("POSTGRES_PASSWORD", "")

        # Connect to services
        weaviate_client = weaviate.connect_to_local(
            host=weaviate_host,
            port=weaviate_port,
            grpc_port=weaviate_grpc_port,
        )

        postgres_conn = psycopg2.connect(
            host=postgres_host,
            port=postgres_port,
            dbname=postgres_db,
            user=postgres_user,
            password=postgres_password,
        )

        reader = WeaviateDiscoveryReader(weaviate_client)
        projects = PostgresProjectRepository(postgres_conn)
        proposal_queue = ProposalQueue(postgres_conn)
        state_store = MonitorStateStore(postgres_conn)
        intent_queue = PMIntentQueue(postgres_conn)

        agent = MonitorAgent(
            discovery_reader=reader,
            project_repository=projects,
            proposal_queue=proposal_queue,
            state_store=state_store,
            intent_queue=intent_queue,
            config=config,
        )
        agent.run()

        pending_count = len(proposal_queue.list_by_status("pending"))
        logger.info(f"Monitor agent completed: {pending_count} proposals pending")

        return {"pending_proposals": pending_count, "config": config}
    except Exception as exc:
        logger.exception("Monitor agent task failed: %s", exc)
        raise
    finally:
        if weaviate_client:
            weaviate_client.close()
        if postgres_conn:
            postgres_conn.close()


def _gatekeeper_config_from_env() -> GatekeeperConfig:
    auto_reject = os.getenv("GATEKEEPER_AUTO_REJECT_THRESHOLD")
    auto_approve = os.getenv("GATEKEEPER_AUTO_APPROVE_THRESHOLD")
    rollback_days = os.getenv("GATEKEEPER_ROLLBACK_WINDOW_DAYS")

    def _maybe_float(value: str | None, fallback: float) -> float:
        if value is None:
            return fallback
        return float(value)

    def _maybe_int(value: str | None, fallback: int) -> int:
        if value is None:
            return fallback
        return int(value)

    defaults = GatekeeperConfig()
    return GatekeeperConfig(
        auto_reject_threshold=_maybe_float(auto_reject, defaults.auto_reject_threshold),
        auto_approve_threshold=_maybe_float(auto_approve, defaults.auto_approve_threshold),
        rollback_window_days=_maybe_int(rollback_days, defaults.rollback_window_days),
    )


def _connect_postgres():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "mnemosyne_dev"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )


def run_gatekeeper_task() -> dict[str, int]:
    """Run gatekeeper auto-approval task."""
    logger.info("=" * 60)
    logger.info("Running periodic Gatekeeper")
    logger.info("=" * 60)

    postgres_conn = None
    try:
        postgres_conn = _connect_postgres()
        proposal_queue = ProposalQueue(postgres_conn)
        intent_queue = PMIntentQueue(postgres_conn)
        gatekeeper = SQLProjectGatekeeper(
            postgres_conn,
            proposal_queue=proposal_queue,
            intent_queue=intent_queue,
            config=_gatekeeper_config_from_env(),
        )
        counts = gatekeeper.process_pending()
        logger.info(
            "Gatekeeper processed: %s auto-approved, %s awaiting approval, %s rejected",
            counts.get("auto_approved", 0),
            counts.get("awaiting_approval", 0),
            counts.get("rejected", 0),
        )
        return counts
    except Exception as exc:
        logger.exception("Gatekeeper task failed: %s", exc)
        raise
    finally:
        if postgres_conn:
            postgres_conn.close()


def _build_project_manager_agent(db_conn):
    message_outbox_path = os.getenv("MESSAGE_OUTBOX_PATH", "message_outbox.db")
    message_outbox = MessageOutbox(message_outbox_path)
    proposal_queue = ProposalQueue(db_conn)
    intent_queue = PMIntentQueue(db_conn)
    gatekeeper = SQLProjectGatekeeper(
        db_conn,
        proposal_queue=proposal_queue,
        intent_queue=intent_queue,
        config=_gatekeeper_config_from_env(),
    )
    agent = ProjectManagerAgent(
        db_conn=db_conn,
        message_outbox=message_outbox,
        gatekeeper=gatekeeper,
        intent_queue=intent_queue,
    )
    return agent, message_outbox


def run_pm_check_cycle_task() -> None:
    """Run Project Manager check cycle and process pending intents."""
    logger.info("=" * 60)
    logger.info("Running Project Manager check cycle")
    logger.info("=" * 60)

    postgres_conn = None
    message_outbox = None
    try:
        postgres_conn = _connect_postgres()
        agent, message_outbox = _build_project_manager_agent(postgres_conn)
        agent.process_intents(limit=int(os.getenv("PM_INTENT_BATCH_SIZE", "10")))
        agent.run_pm_check_cycle()
    except Exception as exc:
        logger.exception("PM check cycle task failed: %s", exc)
        raise
    finally:
        if message_outbox:
            message_outbox.close()
        if postgres_conn:
            postgres_conn.close()


def run_pm_pressure_update_task() -> None:
    """Run Project Manager pressure score update."""
    logger.info("=" * 60)
    logger.info("Running Project Manager pressure score update")
    logger.info("=" * 60)

    postgres_conn = None
    message_outbox = None
    try:
        postgres_conn = _connect_postgres()
        agent, message_outbox = _build_project_manager_agent(postgres_conn)
        agent._update_pressure_scores()
    except Exception as exc:
        logger.exception("PM pressure update task failed: %s", exc)
        raise
    finally:
        if message_outbox:
            message_outbox.close()
        if postgres_conn:
            postgres_conn.close()


def _fetch_projects_for_obsidian_sync(db_conn) -> list[dict[str, object]]:
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, title, description, discovered_by, discovery_id,
                   cluster_ids, confidence_score, status, importance, urgency,
                   deadline, work_estimate, pressure_score, verified_by_user,
                   created_at, updated_at, obsidian_file_path,
                   last_synced_to_obsidian, last_synced_from_obsidian
            FROM projects
            ORDER BY created_at ASC
            """
        )
        rows = cur.fetchall() or []

    projects = []
    for row in rows:
        projects.append(
            {
                "id": row[0],
                "title": row[1],
                "description": row[2],
                "discovered_by": row[3],
                "discovery_id": row[4],
                "cluster_ids": row[5],
                "confidence_score": row[6],
                "status": row[7],
                "importance": row[8],
                "urgency": row[9],
                "deadline": row[10],
                "work_estimate": row[11],
                "pressure_score": row[12],
                "verified_by_user": row[13],
                "created_at": row[14],
                "updated_at": row[15],
                "obsidian_file_path": row[16],
                "last_synced_to_obsidian": row[17],
                "last_synced_from_obsidian": row[18],
            }
        )
    return projects


def run_pm_obsidian_sync_task() -> dict[str, int]:
    """Run SQL -> Obsidian sync for all projects."""
    logger.info("=" * 60)
    logger.info("Running Project Manager SQL -> Obsidian sync")
    logger.info("=" * 60)

    postgres_conn = None
    try:
        vault_path = os.getenv("OBSIDIAN_VAULT_PATH")
        if not vault_path:
            raise ValueError("OBSIDIAN_VAULT_PATH must be set for Obsidian sync")

        postgres_conn = _connect_postgres()
        sync_manager = ObsidianSyncManager(
            db_conn=postgres_conn,
            vault_path=vault_path,
            projects_folder=os.getenv("OBSIDIAN_PROJECTS_FOLDER", "Projects"),
            sync_cooldown_seconds=int(os.getenv("OBSIDIAN_SYNC_COOLDOWN_SECONDS", "30")),
            conflict_strategy=os.getenv("OBSIDIAN_SYNC_CONFLICT_STRATEGY", "sql_wins"),
        )
        projects = _fetch_projects_for_obsidian_sync(postgres_conn)
        results = sync_manager.sync_all_projects_to_obsidian(projects)
        logger.info("Obsidian sync completed for %s projects", len(results))
        return {"projects_synced": len(results)}
    except Exception as exc:
        logger.exception("PM Obsidian sync task failed: %s", exc)
        raise
    finally:
        if postgres_conn:
            postgres_conn.close()


def build_jobs(config: SchedulerConfig) -> list[JobSpec]:
    return [
        JobSpec(
            name="cluster",
            interval_seconds=config.cluster_interval_hours * 3600,
            enabled=config.cluster_enabled,
            run=run_clustering_task,
        ),
        JobSpec(
            name="scout",
            interval_seconds=config.scout_interval_hours * 3600,
            enabled=config.scout_enabled,
            run=run_scout_task,
        ),
        JobSpec(
            name="graph_taxonomy",
            interval_seconds=config.graph_taxonomy_interval_hours * 3600,
            enabled=config.graph_taxonomy_enabled,
            run=run_graph_taxonomy_task,
        ),
        JobSpec(
            name="monitor",
            interval_seconds=config.monitor_interval_minutes * 60,
            enabled=config.monitor_enabled,
            run=run_monitor_agent_task,
        ),
        JobSpec(
            name="gatekeeper",
            interval_seconds=config.gatekeeper_interval_minutes * 60,
            enabled=config.gatekeeper_enabled,
            run=run_gatekeeper_task,
        ),
        JobSpec(
            name="pm_check",
            interval_seconds=config.pm_check_interval_minutes * 60,
            enabled=config.pm_check_enabled,
            run=run_pm_check_cycle_task,
        ),
        JobSpec(
            name="pm_pressure_update",
            interval_seconds=config.pm_pressure_update_interval_hours * 3600,
            enabled=config.pm_pressure_update_enabled,
            run=run_pm_pressure_update_task,
        ),
        JobSpec(
            name="pm_obsidian_sync",
            interval_seconds=config.pm_obsidian_sync_interval_minutes * 60,
            enabled=config.pm_obsidian_sync_enabled,
            run=run_pm_obsidian_sync_task,
        ),
    ]


@click.command("scheduler")
@click.option(
    "--once",
    is_flag=True,
    help="Run a single scheduler cycle and exit.",
)
def scheduler_cli(once: bool):
    """Main scheduler loop."""
    global shutdown_flag

    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    config = SchedulerConfig()

    if once:
        os.environ["SCHEDULER_RUN_ONCE"] = "true"

    jobs = build_jobs(config)

    logger.info("=" * 60)
    logger.info("Mnemosyne Periodic Scheduler")
    logger.info("=" * 60)
    logger.info(
        "Tasks: Cluster + Scout + Graph taxonomy + Monitor + Gatekeeper + PM + Obsidian sync"
    )
    logger.info("=" * 60)

    if not is_scheduler_enabled():
        idle_until_shutdown()
        sys.exit(0)

    scheduler = PeriodicScheduler(jobs=jobs)
    iteration = 0

    while not shutdown_flag:
        iteration += 1
        logger.info(f"\n{'=' * 60}")
        logger.info(f"Starting iteration {iteration} at {datetime.now().isoformat()}")
        logger.info(f"{'=' * 60}")

        scheduler.run_once()

        # Sleep until next iteration
        logger.info(f"\n{'=' * 60}")
        logger.info(f"Iteration {iteration} complete")
        logger.info("Next run in 60 seconds")
        logger.info(f"{'=' * 60}\n")

        if once:
            break

        # Sleep in small increments to allow responsive shutdown
        sleep_remaining = 60
        while sleep_remaining > 0 and not shutdown_flag:
            sleep_time = min(60, sleep_remaining)  # Check every minute
            time.sleep(sleep_time)
            sleep_remaining -= sleep_time

    logger.info("Scheduler shutting down gracefully")
    sys.exit(0)


if __name__ == "__main__":
    scheduler_cli()
