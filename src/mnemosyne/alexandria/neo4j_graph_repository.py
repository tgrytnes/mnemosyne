"""Neo4j graph persistence for cluster taxonomy (skeleton)."""

from __future__ import annotations

from collections.abc import Iterable

from mnemosyne.alexandria.the_gates import ClusterProfile
from mnemosyne.argus.graph_taxonomy import GraphEdge


class Neo4jGraphRepository:
    """Persist cluster nodes and relationships in Neo4j."""

    def __init__(self, driver: object) -> None:
        self.driver = driver

    def ensure_constraints(self) -> None:
        query = (
            "CREATE CONSTRAINT cluster_id_unique IF NOT EXISTS "
            "FOR (c:Cluster) REQUIRE c.cluster_id IS UNIQUE"
        )
        with self.driver.session() as session:
            session.run(query)

    def upsert_clusters(self, profiles: Iterable[ClusterProfile]) -> None:
        rows = []
        for profile in profiles:
            rows.append(
                {
                    "cluster_id": profile.cluster_id,
                    "theme_summary": profile.theme_summary,
                    "dominant_topics": profile.dominant_topics,
                    "tags": profile.tags,
                    "key_entities": profile.key_entities,
                    "confidence_score": profile.confidence_score,
                }
            )
        if not rows:
            return
        query = (
            "UNWIND $rows AS row "
            "MERGE (c:Cluster {cluster_id: row.cluster_id}) "
            "SET c.theme_summary = row.theme_summary, "
            "    c.dominant_topics = row.dominant_topics, "
            "    c.tags = row.tags, "
            "    c.key_entities = row.key_entities, "
            "    c.confidence_score = row.confidence_score"
        )
        with self.driver.session() as session:
            session.run(query, rows=rows)

    def replace_relationships(self, cluster_id: str, edges: Iterable[GraphEdge]) -> None:
        edges_list = [
            {
                "source": edge.source,
                "target": edge.target,
                "edge_type": edge.edge_type,
                "score": edge.score,
                "overlap": edge.overlap,
            }
            for edge in edges
        ]
        with self.driver.session() as session:
            session.run(
                "MATCH (c:Cluster {cluster_id: $cluster_id})-[r:PARENT_OF|NEIGHBOR]-() " "DELETE r",
                cluster_id=cluster_id,
            )
            if not edges_list:
                return
            session.run(
                "UNWIND $edges AS edge "
                "MATCH (source:Cluster {cluster_id: edge.source}) "
                "MATCH (target:Cluster {cluster_id: edge.target}) "
                "CALL { "
                "  WITH source, target, edge "
                "  WITH source, target, edge WHERE edge.edge_type = 'PARENT_OF' "
                "  MERGE (source)-[r:PARENT_OF]->(target) "
                "  SET r.score = edge.score, r.overlap = edge.overlap "
                "} "
                "CALL { "
                "  WITH source, target, edge "
                "  WITH source, target, edge WHERE edge.edge_type = 'NEIGHBOR' "
                "  MERGE (source)-[r:NEIGHBOR]->(target) "
                "  SET r.score = edge.score "
                "} ",
                edges=edges_list,
            )

    def get_children(self, cluster_id: str) -> list[str]:
        query = (
            "MATCH (:Cluster {cluster_id: $cluster_id})-[:PARENT_OF]->(child:Cluster) "
            "RETURN child.cluster_id AS cluster_id"
        )
        with self.driver.session() as session:
            result = session.run(query, cluster_id=cluster_id)
            values = [record["cluster_id"] for record in result]
        return sorted(values)

    def get_parents(self, cluster_id: str) -> list[str]:
        query = (
            "MATCH (parent:Cluster)-[:PARENT_OF]->(:Cluster {cluster_id: $cluster_id}) "
            "RETURN parent.cluster_id AS cluster_id"
        )
        with self.driver.session() as session:
            result = session.run(query, cluster_id=cluster_id)
            values = [record["cluster_id"] for record in result]
        return sorted(values)

    def get_neighbors(self, cluster_id: str) -> list[str]:
        query = (
            "MATCH (c:Cluster {cluster_id: $cluster_id})-[:NEIGHBOR]-(neighbor:Cluster) "
            "RETURN neighbor.cluster_id AS cluster_id"
        )
        with self.driver.session() as session:
            result = session.run(query, cluster_id=cluster_id)
            values = [record["cluster_id"] for record in result]
        return sorted(values)
