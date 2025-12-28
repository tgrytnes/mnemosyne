"""CLI commands for quality assurance and evaluation.

Provides commands for generating quality reports, comparing strategies, and benchmarking.
"""

import logging
import sys
from pathlib import Path

import numpy as np
import weaviate

from mnemosyne.iris.chunking_quality import ChunkingQualityAnalyzer
from mnemosyne.iris.embedding_quality import EmbeddingQualityAnalyzer

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def generate_quality_report(
    output_path: Path, weaviate_host: str = "localhost", weaviate_port: int = 8080
) -> None:
    """Generate comprehensive quality report.

    Args:
        output_path: Path to output markdown file
        weaviate_host: Weaviate host
        weaviate_port: Weaviate HTTP port
    """
    logger.info("Generating quality report...")

    # Connect to Weaviate
    client = weaviate.connect_to_local(host=weaviate_host, port=weaviate_port)

    try:
        # Fetch chunks and vectors from Weaviate
        collection = client.collections.get("TheMuses")
        results = collection.query.fetch_objects(limit=1000, include_vector=True)

        chunks = [obj.properties.get("text", "") for obj in results.objects]
        vectors = np.array([obj.vector["default"] for obj in results.objects])

        # Compute embedding quality
        logger.info("Computing embedding quality metrics...")
        embedding_analyzer = EmbeddingQualityAnalyzer(vectors)
        embedding_metrics = embedding_analyzer.analyze()

        # Compute chunking quality
        logger.info("Computing chunking quality metrics...")
        chunking_analyzer = ChunkingQualityAnalyzer(chunks, vectors)
        chunking_metrics = chunking_analyzer.analyze()

        # Generate markdown report
        logger.info(f"Writing report to {output_path}...")
        with open(output_path, "w") as f:
            f.write("# Mnemosyne Quality Report\n\n")

            f.write("## Embedding Quality\n")
            f.write(f"- Avg pairwise similarity: {embedding_metrics.avg_pairwise_similarity:.3f}\n")
            f.write(f"- Similarity std: {embedding_metrics.similarity_std:.3f}\n")
            f.write(f"- Vector space coverage: {embedding_metrics.vector_space_coverage:.1%}\n")
            f.write(f"- Dimensionality usage: {embedding_metrics.dimensionality_usage:.1%}\n")
            collapse_status = "Yes" if embedding_metrics.embedding_collapse_detected else "No"
            f.write(f"- Embedding collapse detected: {collapse_status}\n")
            f.write(f"- Avg vector magnitude: {embedding_metrics.avg_vector_magnitude:.3f}\n")
            f.write(f"- Magnitude std: {embedding_metrics.magnitude_std:.3f}\n\n")

            f.write("## Chunking Quality\n")
            f.write(f"- Avg chunk size: {chunking_metrics.avg_chunk_size:.0f} chars\n")
            f.write(f"- Chunk size std: {chunking_metrics.chunk_size_std:.0f} chars\n")
            f.write(f"- Min chunk size: {chunking_metrics.min_chunk_size} chars\n")
            f.write(f"- Max chunk size: {chunking_metrics.max_chunk_size} chars\n")
            f.write(f"- Semantic coherence: {chunking_metrics.semantic_coherence:.3f}\n")
            f.write(f"- Boundary quality: {chunking_metrics.boundary_quality:.1%}\n")

        logger.info(f"Quality report generated successfully at {output_path}")

    finally:
        client.close()


def main():
    """Main entry point for CLI."""
    if len(sys.argv) < 2:
        print("Usage: python -m mnemosyne.cli.quality <command> [options]")
        print("\nCommands:")
        print("  report --output <file>    Generate quality report")
        sys.exit(1)

    command = sys.argv[1]

    if command == "report":
        # Parse output argument
        if "--output" not in sys.argv:
            print("Error: --output argument is required")
            sys.exit(1)

        output_idx = sys.argv.index("--output") + 1
        if output_idx >= len(sys.argv):
            print("Error: --output requires a file path")
            sys.exit(1)

        output_path = Path(sys.argv[output_idx])
        generate_quality_report(output_path)

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
