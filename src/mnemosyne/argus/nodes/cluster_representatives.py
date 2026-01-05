# src/mnemosyne/argus/nodes/cluster_representatives.py

import logging
from typing import TypedDict

import numpy as np
import weaviate
from weaviate.classes.query import Filter

from mnemosyne.alexandria.the_gates.chunk_representation import ChunkRepresentation
from mnemosyne.alexandria.weaviate_schema import ClusterCentroidCollection, TheMuses

logger = logging.getLogger(__name__)


class ClusterRepresentativesState(TypedDict):
    cluster_id: int
    representative_chunks: list[ChunkRepresentation]
    error: str | None


class GetClusterRepresentatives:
    def __init__(
        self,
        client: weaviate.WeaviateClient,
        *,
        chunk_collection_name: str = TheMuses.collection_name,
        centroid_collection_name: str = ClusterCentroidCollection.collection_name,
        text_property: str = "text",
        source_property: str = "sourceFile",
        heading_property: str | None = "headingPath",
        chunk_index_property: str = "chunkIndex",
    ):
        self.client = client
        self.chunk_collection = self.client.collections.get(chunk_collection_name)
        self.centroid_collection = self.client.collections.get(centroid_collection_name)
        self.text_property = text_property
        self.source_property = source_property
        self.heading_property = heading_property
        self.chunk_index_property = chunk_index_property

    def _get_cluster_centroid_vector(self, cluster_id: int) -> np.ndarray | None:
        """
        Get the centroid vector for a given cluster_id.
        Tries to get a cached centroid first, otherwise computes it.
        """
        # Try to get from cached centroids first
        response = self.centroid_collection.query.fetch_objects(
            filters=Filter.by_property("clusterId").equal(cluster_id),
            limit=1,
            include_vector=True,  # CRITICAL: Must request vectors explicitly
        )
        if response.objects and response.objects[0].vector:
            # Safely access vector with get() to handle missing 'default' key
            vector_data = response.objects[0].vector.get("default")
            if vector_data:
                return np.array(vector_data)
            # Fallback: try direct access if vector is a list
            if isinstance(response.objects[0].vector, list):
                return np.array(response.objects[0].vector)

        # If not cached, compute it on the fly
        logger.warning(
            f"Centroid for cluster {cluster_id} not found in cache. Computing on the fly."
        )

        # Use fetch_objects with filter instead of iterator (which doesn't support filters)
        response = self.chunk_collection.query.fetch_objects(
            filters=Filter.by_property("clusterId").equal(cluster_id),
            include_vector=True,
            limit=10000,  # Large limit to get all vectors in cluster
        )

        if not response.objects:
            return None

        all_vectors = [obj.vector["default"] for obj in response.objects]
        return np.mean(all_vectors, axis=0)

    def __call__(self, state: ClusterRepresentativesState) -> ClusterRepresentativesState:
        cluster_id = state.get("cluster_id")
        if cluster_id is None:
            return {**state, "error": "cluster_id not found in state", "representative_chunks": []}

        logger.info(f"Getting representative chunks for cluster_id: {cluster_id}")

        centroid_vector = self._get_cluster_centroid_vector(cluster_id)

        if centroid_vector is None:
            logger.warning(f"Could not find or compute centroid for cluster {cluster_id}.")
            return {**state, "representative_chunks": []}

        # Query for 5 nearest neighbors to the centroid
        try:
            response = self.muses_collection.query.near_vector(
                near_vector=centroid_vector.tolist(),
                limit=5,
                return_metadata=["distance"],
            )

            representative_chunks = []
            for item in response.objects:
                props = item.properties
                chunk = ChunkRepresentation(
                    chunk_id=str(item.uuid),
                    source_file=props.get(self.source_property, ""),
                    text=(props.get(self.text_property, "") or "")[:200],
                    heading_path=(
                        props.get(self.heading_property, "") if self.heading_property else ""
                    ),
                    distance_from_centroid=item.metadata.distance,
                    chunk_index=props.get(self.chunk_index_property, -1),
                )
                representative_chunks.append(chunk)

            representative_chunks.sort(key=lambda x: (x.distance_from_centroid, x.chunk_index))

            return {**state, "representative_chunks": representative_chunks, "error": None}

        except Exception as e:
            logger.error(f"Error querying Weaviate for cluster {cluster_id}: {e}")
            return {**state, "error": str(e), "representative_chunks": []}
