# src/mnemosyne/cli/cluster.py

import argparse
import logging
import os
import sys
from datetime import datetime

import numpy as np
import weaviate
from sklearn.cluster import MiniBatchKMeans

from mnemosyne.alexandria.weaviate_schema import (
    ClusterCentroidCollection,
    TheLethe,
    TheMuses,
    WeaviateSchemaManager,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ClusteringConfig:
    """Configuration for clustering."""

    def __init__(self):
        """Load configuration from environment variables."""
        self.weaviate_host = os.getenv("WEAVIATE_HTTP_HOST", "localhost")
        self.weaviate_port = int(os.getenv("WEAVIATE_HTTP_PORT", "8080"))
        self.weaviate_grpc_port = int(os.getenv("WEAVIATE_GRPC_PORT", "50051"))
        self.n_clusters_default = int(os.getenv("N_CLUSTERS", "50"))
        self.n_clusters_muses = int(os.getenv("N_CLUSTERS_MUSES", str(self.n_clusters_default)))
        self.n_clusters_lethe = int(os.getenv("N_CLUSTERS_LETHE", str(self.n_clusters_default)))

    def resolve_n_clusters(self, collection_name: str) -> int:
        if collection_name == TheLethe.collection_name:
            return self.n_clusters_lethe
        return self.n_clusters_muses


class ClusterManager:
    """Handles the clustering process."""

    def __init__(
        self,
        client: weaviate.WeaviateClient,
        collection_name: str = TheMuses.collection_name,
        centroid_collection_name: str = ClusterCentroidCollection.collection_name,
    ):
        self.client = client
        self.collection_name = collection_name
        self.collection = self.client.collections.get(collection_name)
        self.centroid_collection = self.client.collections.get(centroid_collection_name)

    def fetch_all_vectors(self) -> tuple[np.ndarray, list[str]]:
        """Fetch all vectors and their UUIDs from the target collection."""
        logger.info("Fetching all vectors from %s collection...", self.collection_name)
        vectors = []
        uuids = []

        query_result = self.collection.iterator(include_vector=True)

        for item in query_result:
            vectors.append(item.vector["default"])
            uuids.append(str(item.uuid))

        logger.info(f"Fetched {len(vectors)} vectors.")
        return np.array(vectors), uuids

    def run_kmeans_clustering(
        self, vectors: np.ndarray, n_clusters: int
    ) -> tuple[np.ndarray, np.ndarray]:
        """Run MiniBatchKMeans clustering."""
        logger.info(f"Running MiniBatchKMeans with {n_clusters} clusters...")
        kmeans = MiniBatchKMeans(
            n_clusters=n_clusters,
            random_state=42,
            batch_size=256,
            n_init="auto",
        )
        labels = kmeans.fit_predict(vectors)
        logger.info("Clustering complete.")
        return labels, kmeans.cluster_centers_

    def update_chunk_cluster_ids(self, uuids: list[str], labels: np.ndarray) -> None:
        """Update each chunk with its assigned cluster ID."""
        logger.info("Updating cluster IDs for all chunks...")
        # Use data.update() for each chunk to properly update existing objects
        for uuid_str, label in zip(uuids, labels):
            self.collection.data.update(
                uuid=uuid_str,
                properties={"clusterId": int(label)},
            )
        logger.info("Finished updating chunk cluster IDs.")

    def update_centroids(self, centroids: np.ndarray, labels: np.ndarray) -> None:
        """Calculate and store cluster centroids."""
        logger.info("Calculating and storing cluster centroids...")

        # Clear existing centroids using a filter that matches all (clusterId >= 0)
        from weaviate.classes.query import Filter

        delete_result = self.centroid_collection.data.delete_many(
            where=Filter.by_property("clusterId").greater_or_equal(0)
        )
        logger.info(
            f"Deleted {delete_result.matches} existing centroids "
            f"(successful: {delete_result.successful}, failed: {delete_result.failed})"
        )

        # Insert new centroids with proper batch size
        import time

        centroids_to_insert = []
        for i in range(len(centroids)):
            cluster_size = np.count_nonzero(labels == i)
            if cluster_size > 0:
                centroids_to_insert.append((i, centroids[i], cluster_size))

        logger.info(f"Inserting {len(centroids_to_insert)} new centroids...")

        with self.centroid_collection.batch.fixed_size(batch_size=100) as batch:
            for cluster_id, centroid_vec, size in centroids_to_insert:
                batch.add_object(
                    vector={"default": centroid_vec.tolist()},
                    properties={
                        "clusterId": int(cluster_id),
                        "clusterSize": int(size),
                        "lastUpdated": datetime.utcnow().isoformat() + "Z",
                    },
                )

        # Verify insertion with retries
        time.sleep(0.5)
        for attempt in range(3):
            verify = self.centroid_collection.query.fetch_objects(limit=1, include_vector=True)
            if len(verify.objects) > 0:
                logger.info(f"Verified {len(centroids_to_insert)} centroids stored successfully")
                break
            logger.warning(
                f"Verification attempt {attempt + 1}: No centroids found yet, retrying..."
            )
            time.sleep(0.5)

        logger.info("Finished storing cluster centroids.")


def run_clustering(
    n_clusters: int,
    collection_name: str = TheMuses.collection_name,
    centroid_collection_name: str = ClusterCentroidCollection.collection_name,
):
    """
    Main function to run the clustering process.

    Args:
        n_clusters: The number of clusters to create.
    """
    try:
        # Validate n_clusters
        if n_clusters < 1:
            logger.error(f"Invalid n_clusters: {n_clusters}. Must be >= 1.")
            sys.exit(1)

        config = ClusteringConfig()

        logger.info("=" * 60)
        logger.info("Starting Chunk Clustering")
        logger.info("=" * 60)
        logger.info(f"Weaviate: {config.weaviate_host}:{config.weaviate_port}")
        logger.info(f"Collection: {collection_name}")
        logger.info(f"Number of clusters: {n_clusters}")
        logger.info("=" * 60)

        client = weaviate.connect_to_local(
            host=config.weaviate_host,
            port=config.weaviate_port,
            grpc_port=config.weaviate_grpc_port,
        )

        # Ensure collections exist
        schema_manager = WeaviateSchemaManager(client)
        schema_manager.ensure_collection_exists(collection_name)
        schema_manager.ensure_collection_exists(centroid_collection_name)

        manager = ClusterManager(
            client,
            collection_name=collection_name,
            centroid_collection_name=centroid_collection_name,
        )

        vectors, uuids = manager.fetch_all_vectors()
        if len(vectors) == 0:
            logger.warning("No vectors found in TheMuses collection. Aborting clustering.")
            client.close()
            return

        # Validate n_clusters against vector count
        if n_clusters > len(vectors):
            logger.warning(
                f"n_clusters ({n_clusters}) > vector count ({len(vectors)}). "
                f"Setting n_clusters = {len(vectors)}"
            )
            n_clusters = len(vectors)

        labels, centroids = manager.run_kmeans_clustering(vectors, n_clusters)
        manager.update_chunk_cluster_ids(uuids, labels)
        manager.update_centroids(centroids, labels)

        logger.info("\n" + "=" * 60)
        logger.info("Clustering Complete!")
        logger.info("=" * 60)

        client.close()

    except Exception as e:
        logger.error(f"Error during clustering: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


def main():
    """Main CLI entry point for clustering."""
    parser = argparse.ArgumentParser(
        description="Mnemosyne - Chunk Clustering",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # 'run' command
    parser_run = subparsers.add_parser("run", help="Run clustering on TheMuses collection")
    parser_run.add_argument(
        "--n-clusters",
        type=int,
        default=416,
        help="The number of clusters to create (default: 416)",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "run":
        run_clustering(args.n_clusters)


if __name__ == "__main__":
    main()
