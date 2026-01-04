"""CLI for Scout pattern detection."""

import logging
import os
import sys

import ollama
import weaviate

from mnemosyne.argus.scout.radar import ConceptPrototype
from mnemosyne.argus.scout.scout_runner import ScoutConfig, ScoutRunner

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Run Scout pattern detection."""
    logger.info("=" * 60)
    logger.info("Scout Pattern Detection")
    logger.info("=" * 60)

    # Get configuration from environment
    weaviate_host = os.getenv("WEAVIATE_HTTP_HOST", "localhost")
    weaviate_port = int(os.getenv("WEAVIATE_HTTP_PORT", "8080"))
    weaviate_grpc_port = int(os.getenv("WEAVIATE_GRPC_PORT", "50051"))
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    embedding_model = os.getenv("OLLAMA_EMBEDDING_MODEL", "qwen3-embedding:0.6b")

    logger.info(f"Weaviate: {weaviate_host}:{weaviate_port}")
    logger.info(f"Ollama: {ollama_url}")
    logger.info(f"Embedding Model: {embedding_model}")
    logger.info("=" * 60)

    # Connect to services
    logger.info("Connecting to Weaviate...")
    weaviate_client = weaviate.connect_to_local(
        host=weaviate_host,
        port=weaviate_port,
        grpc_port=weaviate_grpc_port,
    )

    logger.info("Connecting to Ollama...")
    ollama_client = ollama.Client(host=ollama_url)

    # Create embedder function
    def embedder(text: str) -> list[float]:
        """Generate embedding using Ollama."""
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
        threshold=0.05,  # Threshold for detecting project candidates
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

    logger.info("Running Scout pattern detection...")
    runner = ScoutRunner(client=weaviate_client, embedder=embedder, config=config)

    try:
        summary = runner.run()
        logger.info("=" * 60)
        logger.info("Scout Run Complete!")
        logger.info("=" * 60)
        logger.info(f"Run ID: {summary.run_id}")
        logger.info(f"Clusters analyzed: {summary.clusters_analyzed}")
        logger.info(f"Duration: {summary.duration_seconds:.2f}s")
        logger.info("Detections by type:")
        for pattern_type, count in summary.detections_by_type.items():
            logger.info(f"  {pattern_type}: {count}")
        if summary.errors:
            logger.warning(f"Errors encountered: {len(summary.errors)}")
            for error in summary.errors[:5]:  # Show first 5 errors
                logger.warning(f"  {error}")
        logger.info("=" * 60)
    except Exception as e:
        logger.error(f"Error during Scout run: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        weaviate_client.close()


if __name__ == "__main__":
    main()
