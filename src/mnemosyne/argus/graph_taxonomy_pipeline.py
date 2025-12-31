"""Pipeline wrapper for building graph taxonomies."""

from __future__ import annotations

from dataclasses import dataclass

from mnemosyne.alexandria.cluster_profile_repository import ClusterProfileRepository
from mnemosyne.alexandria.neo4j_graph_repository import Neo4jGraphRepository
from mnemosyne.alexandria.weaviate_schema import (
    ClusterCentroidCollection,
    WeaviateSchemaManager,
)
from mnemosyne.argus.graph_taxonomy import GraphTaxonomyBuilder, GraphTaxonomyConfig
from mnemosyne.argus.scout.radar import cosine_similarity


@dataclass
class GraphTaxonomyPipeline:
    weaviate_client: object
    postgres_connection: object
    neo4j_driver: object
    config: GraphTaxonomyConfig

    def build_graph(self, cluster_ids: list[str] | None = None) -> dict[str, list[dict]]:
        schema = WeaviateSchemaManager(self.weaviate_client)
        schema.ensure_collection_exists(ClusterCentroidCollection.collection_name)

        centroid_collection = self.weaviate_client.collections.get(
            ClusterCentroidCollection.collection_name
        )
        response = centroid_collection.query.fetch_objects(include_vector=True, limit=10000)

        centroid_vectors: dict[str, list[float]] = {}
        for obj in response.objects:
            cluster_id = str(obj.properties.get("clusterId"))
            if cluster_ids and cluster_id not in cluster_ids:
                continue
            vector = obj.vector
            if isinstance(vector, dict):
                vector = vector.get("default")
            if vector:
                centroid_vectors[cluster_id] = vector

        selected_ids = list(centroid_vectors.keys())
        if cluster_ids:
            selected_ids = [
                cluster_id for cluster_id in cluster_ids if cluster_id in centroid_vectors
            ]

        similarity: dict[tuple[str, str], float] = {}
        for left_id in selected_ids:
            for right_id in selected_ids:
                if left_id == right_id:
                    continue
                score = cosine_similarity(centroid_vectors[left_id], centroid_vectors[right_id])
                similarity[(left_id, right_id)] = score

        profile_repo = ClusterProfileRepository(self.postgres_connection)
        profiles = []
        for cluster_id in selected_ids:
            profile = profile_repo.get(cluster_id)
            if profile:
                profiles.append(profile)

        builder = GraphTaxonomyBuilder(self.config)
        taxonomy = builder.build(profiles, similarity)

        graph_repo = Neo4jGraphRepository(self.neo4j_driver)
        graph_repo.ensure_constraints()
        graph_repo.upsert_clusters(profiles)
        for cluster_id in selected_ids:
            edges = [
                edge
                for edge in taxonomy.edges
                if edge.source == cluster_id or edge.target == cluster_id
            ]
            graph_repo.replace_relationships(cluster_id, edges)

        nodes = [
            {
                "id": profile.cluster_id,
                "label": profile.theme_summary,
                "tags": profile.tags,
                "score": profile.confidence_score,
            }
            for profile in profiles
        ]
        edges = [
            {
                "source": edge.source,
                "target": edge.target,
                "type": edge.edge_type,
                "score": edge.score,
                "overlap": edge.overlap,
            }
            for edge in taxonomy.edges
        ]

        return {"nodes": nodes, "edges": edges}
