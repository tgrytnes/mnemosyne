"""Periodic scheduler for clustering, Scout pattern detection, and graph taxonomy."""

import logging
import os
import signal
import sys
import time
from datetime import datetime

import ollama
import psycopg2
import weaviate
from neo4j import GraphDatabase

from mnemosyne.alexandria.weaviate_schema import (
    ClusterCentroidCollection,
    ClusterCentroidLethe,
    TheLethe,
    TheMuses,
)
from mnemosyne.argus.graph_taxonomy import GraphTaxonomyConfig
from mnemosyne.argus.graph_taxonomy_pipeline import GraphTaxonomyPipeline
from mnemosyne.argus.scout.monitor_agent import (
    MessageOutbox,
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

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global flag for graceful shutdown
shutdown_flag = False


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    global shutdown_flag
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_flag = True


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
    except Exception as e:
        logger.error(f"Clustering task failed: {e}")
        import traceback

        traceback.print_exc()


def run_scout_task():
    """Run Scout pattern detection task."""
    logger.info("=" * 60)
    logger.info("Running periodic Scout pattern detection")
    logger.info("=" * 60)

    try:
        # Get configuration from environment
        weaviate_host = os.getenv("WEAVIATE_HTTP_HOST", "localhost")
        weaviate_port = int(os.getenv("WEAVIATE_HTTP_PORT", "8080"))
        weaviate_grpc_port = int(os.getenv("WEAVIATE_GRPC_PORT", "50051"))
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        embedding_model = os.getenv("OLLAMA_EMBEDDING_MODEL", "qwen3-embedding:0.6b")

        # Connect to services
        weaviate_client = weaviate.connect_to_local(
            host=weaviate_host,
            port=weaviate_port,
            grpc_port=weaviate_grpc_port,
        )

        ollama_client = ollama.Client(host=ollama_url)

        # Create embedder function
        def embedder(text: str) -> list[float]:
            response = ollama_client.embeddings(model=embedding_model, prompt=text)
            return response["embedding"]

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

        weaviate_client.close()

    except Exception as e:
        logger.error(f"Scout task failed: {e}")
        import traceback

        traceback.print_exc()


def run_graph_taxonomy_task():
    """Run graph taxonomy building task."""
    logger.info("=" * 60)
    logger.info("Running periodic graph taxonomy building")
    logger.info("=" * 60)

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

        # Configure graph taxonomy
        config = GraphTaxonomyConfig()
        centroid_collection_name = (
            ClusterCentroidLethe.collection_name
            if graph_taxonomy_source == "lethe"
            else ClusterCentroidCollection.collection_name
        )
        logger.info("Graph taxonomy source: %s", graph_taxonomy_source)

        # Build graph
        pipeline = GraphTaxonomyPipeline(
            weaviate_client=weaviate_client,
            postgres_connection=postgres_conn,
            neo4j_driver=neo4j_driver,
            config=config,
            centroid_collection_name=centroid_collection_name,
            profile_source=graph_taxonomy_source,
        )

        result = pipeline.build_graph()

        logger.info(
            f"Graph taxonomy task completed: "
            f"{len(result['nodes'])} nodes, {len(result['edges'])} edges"
        )

        # Cleanup
        weaviate_client.close()
        postgres_conn.close()
        neo4j_driver.close()

    except Exception as e:
        logger.error(f"Graph taxonomy task failed: {e}")
        import traceback

        traceback.print_exc()


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
        outbox = MessageOutbox(postgres_conn)

        agent = MonitorAgent(
            discovery_reader=reader,
            project_repository=projects,
            proposal_queue=proposal_queue,
            state_store=state_store,
            outbox=outbox,
            config=config,
        )
        agent.run()

        pending_count = len(proposal_queue.list_by_status("pending"))
        logger.info(f"Monitor agent completed: {pending_count} proposals pending")

        return {"pending_proposals": pending_count, "config": config}
    except Exception as e:
        logger.error(f"Monitor agent task failed: {e}")
        import traceback

        traceback.print_exc()
        return {"pending_proposals": 0, "config": config}
    finally:
        if weaviate_client:
            weaviate_client.close()
        if postgres_conn:
            postgres_conn.close()


def main():
    """Main scheduler loop."""
    global shutdown_flag

    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Get configuration from environment
    interval_hours = int(os.getenv("SCHEDULER_INTERVAL_HOURS", "24"))
    interval_seconds = interval_hours * 3600

    logger.info("=" * 60)
    logger.info("Mnemosyne Periodic Scheduler")
    logger.info("=" * 60)
    logger.info(f"Interval: {interval_hours} hours ({interval_seconds} seconds)")
    logger.info("Tasks: Clustering + Scout pattern detection + Graph taxonomy + Monitor agent")
    logger.info("=" * 60)

    iteration = 0

    while not shutdown_flag:
        iteration += 1
        logger.info(f"\n{'=' * 60}")
        logger.info(f"Starting iteration {iteration} at {datetime.now().isoformat()}")
        logger.info(f"{'=' * 60}")

        # Run clustering
        run_clustering_task()

        if shutdown_flag:
            break

        # Run Scout
        run_scout_task()

        if shutdown_flag:
            break

        # Run graph taxonomy
        run_graph_taxonomy_task()

        if shutdown_flag:
            break

        # Run monitor agent
        run_monitor_agent_task()

        if shutdown_flag:
            break

        # Sleep until next iteration
        logger.info(f"\n{'=' * 60}")
        logger.info(f"Iteration {iteration} complete")
        logger.info(f"Next run in {interval_hours} hours ({interval_seconds} seconds)")
        logger.info(f"{'=' * 60}\n")

        # Sleep in small increments to allow responsive shutdown
        sleep_remaining = interval_seconds
        while sleep_remaining > 0 and not shutdown_flag:
            sleep_time = min(60, sleep_remaining)  # Check every minute
            time.sleep(sleep_time)
            sleep_remaining -= sleep_time

    logger.info("Scheduler shutting down gracefully")
    sys.exit(0)


if __name__ == "__main__":
    main()
