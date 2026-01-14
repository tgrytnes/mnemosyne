"""CLI for building graph taxonomy in Neo4j."""

import logging
import os
import sys

import click
import psycopg2
import weaviate
from neo4j import GraphDatabase

from mnemosyne.alexandria.weaviate_schema import (
    ClusterCentroidCollection,
    ClusterCentroidLethe,
    TheLethe,
    TheMuses,
)
from mnemosyne.argus.cluster_profile_bootstrap import ClusterProfileBootstrapper
from mnemosyne.argus.graph_taxonomy import GraphTaxonomyConfig
from mnemosyne.argus.graph_taxonomy_pipeline import GraphTaxonomyPipeline
from mnemosyne.config.providers import ProviderConfig
from mnemosyne.providers.factory import create_llm_provider

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@click.command("graph-taxonomy")
def graph_taxonomy_cli():
    """Run graph taxonomy building."""
    run_graph_taxonomy()


def run_graph_taxonomy():
    """Run graph taxonomy building."""
    logger.info("=" * 60)
    logger.info("Graph Taxonomy Builder")
    logger.info("=" * 60)

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

    logger.info(f"Weaviate: {weaviate_host}:{weaviate_port}")
    logger.info(f"Postgres: {postgres_host}:{postgres_port}/{postgres_db}")
    logger.info(f"Neo4j: {neo4j_uri}")
    logger.info("=" * 60)

    try:
        # Connect to services
        logger.info("Connecting to Weaviate...")
        weaviate_client = weaviate.connect_to_local(
            host=weaviate_host,
            port=weaviate_port,
            grpc_port=weaviate_grpc_port,
        )

        logger.info("Connecting to Postgres...")
        postgres_conn = psycopg2.connect(
            host=postgres_host,
            port=postgres_port,
            dbname=postgres_db,
            user=postgres_user,
            password=postgres_password,
        )

        logger.info("Connecting to Neo4j...")
        neo4j_driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        llm_provider = create_llm_provider(ProviderConfig.from_env())

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
        logger.info("Building graph taxonomy...")
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

        logger.info("=" * 60)
        logger.info("Graph Taxonomy Build Complete!")
        logger.info("=" * 60)
        logger.info(f"Nodes: {len(result['nodes'])}")
        logger.info(f"Edges: {len(result['edges'])}")
        logger.info("=" * 60)

        # Cleanup
        weaviate_client.close()
        postgres_conn.close()
        neo4j_driver.close()

    except Exception as e:
        logger.error(f"Error during graph taxonomy build: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
