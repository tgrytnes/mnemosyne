"""Periodic scheduler for clustering and Scout pattern detection."""

import logging
import os
import signal
import sys
import time
from datetime import datetime

import ollama
import weaviate

from mnemosyne.argus.scout.radar import ConceptPrototype
from mnemosyne.argus.scout.scout_runner import ScoutConfig, ScoutRunner
from mnemosyne.cli.cluster import run_clustering

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
        n_clusters = int(os.getenv("N_CLUSTERS", "50"))
        run_clustering(n_clusters)
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
    logger.info("Tasks: Clustering + Scout pattern detection")
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
