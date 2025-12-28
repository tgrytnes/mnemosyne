"""
CLI for quality metrics and reporting.

Usage:
    python -m mnemosyne.cli.quality report --output quality_report.md
    python -m mnemosyne.cli.quality report --ground-truth data/ground_truth.json
"""

import os
import sys
from pathlib import Path

import click
import weaviate
from dotenv import load_dotenv

from mnemosyne.iris.quality_metrics import QualityMetricsOrchestrator, QualityReportFormatter


def get_weaviate_client() -> weaviate.WeaviateClient:
    """Create and return connected Weaviate client."""
    load_dotenv()

    weaviate_url = os.getenv("WEAVIATE_URL", "http://localhost:8080")

    client = weaviate.connect_to_custom(
        http_host=weaviate_url.replace("http://", "").replace("https://", "").split(":")[0],
        http_port=int(weaviate_url.split(":")[-1]) if ":" in weaviate_url else 8080,
        http_secure=False,
        grpc_host=weaviate_url.replace("http://", "").replace("https://", "").split(":")[0],
        grpc_port=50051,
        grpc_secure=False,
    )

    return client


@click.group()
def cli():
    """Quality metrics and reporting CLI."""
    pass


@cli.command()
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default="quality_report.md",
    help="Output file path (default: quality_report.md)",
)
@click.option(
    "--ground-truth",
    "-g",
    type=click.Path(exists=True),
    default=None,
    help="Path to ground truth dataset JSON",
)
@click.option(
    "--collection",
    "-c",
    type=str,
    default="TheMuses",
    help="Weaviate collection name (default: TheMuses)",
)
@click.option(
    "--sample-size",
    "-s",
    type=int,
    default=1000,
    help="Max chunks to analyze (default: 1000, use 0 for all)",
)
def report(output: str, ground_truth: str, collection: str, sample_size: int):
    """
    Generate comprehensive quality report.

    Analyzes embedding quality, chunking quality, and optionally
    retrieval performance (if ground truth dataset provided).
    """
    click.echo("🔍 Generating Mnemosyne Quality Report...")
    click.echo()

    # Connect to Weaviate
    click.echo(f"📊 Connecting to Weaviate collection: {collection}")
    try:
        client = get_weaviate_client()
    except Exception as e:
        click.echo(f"❌ Failed to connect to Weaviate: {e}", err=True)
        sys.exit(1)

    # Create orchestrator
    orchestrator = QualityMetricsOrchestrator(client, collection_name=collection)

    # Parse ground truth path
    gt_path = Path(ground_truth) if ground_truth else None

    # Generate report
    click.echo(f"⚙️  Analyzing {sample_size if sample_size > 0 else 'all'} chunks...")
    try:
        report_obj = orchestrator.generate_report(
            ground_truth_path=gt_path,
            sample_size=sample_size if sample_size > 0 else None,
        )
    except Exception as e:
        click.echo(f"❌ Failed to generate report: {e}", err=True)
        client.close()
        sys.exit(1)

    # Format as Markdown
    formatter = QualityReportFormatter()
    markdown_report = formatter.format_markdown(report_obj)

    # Write to file
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown_report)

    click.echo()
    click.echo(f"✅ Report generated: {output_path}")
    click.echo()
    click.echo("📈 Summary:")
    click.echo(f"   - Chunks analyzed: {report_obj.num_chunks}")

    if report_obj.embedding_metrics:
        em = report_obj.embedding_metrics
        click.echo(
            f"   - Avg pairwise similarity: {em['avg_pairwise_similarity']:.3f}"
        )
        click.echo(
            f"   - Vector space coverage: {em['vector_space_coverage']:.1%}"
        )

    if report_obj.retrieval_metrics:
        rm = report_obj.retrieval_metrics
        click.echo(f"   - Recall@10: {rm['recall_at_10']:.3f}")
        click.echo(f"   - NDCG@10: {rm['ndcg_at_10']:.3f}")

    if report_obj.chunking_metrics:
        cm = report_obj.chunking_metrics
        click.echo(f"   - Avg chunk size: {cm['avg_chunk_size']:.0f} chars")
        click.echo(
            f"   - Boundary quality: {cm['boundary_quality']:.1%}"
        )

    client.close()


@cli.command()
@click.argument("output_path", type=click.Path())
def create_ground_truth(output_path: str):
    """
    Create a sample ground truth dataset.

    Creates a template JSON file with example query-document pairs
    that you can customize for your vault.
    """
    from mnemosyne.iris.retrieval_evaluation import create_sample_ground_truth

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    create_sample_ground_truth(path)

    click.echo(f"✅ Sample ground truth created: {path}")
    click.echo()
    click.echo("📝 Next steps:")
    click.echo("   1. Edit the JSON file with queries relevant to your vault")
    click.echo("   2. Add relevant document paths for each query")
    click.echo("   3. Run: python -m mnemosyne.cli.quality report --ground-truth " + output_path)


if __name__ == "__main__":
    cli()
