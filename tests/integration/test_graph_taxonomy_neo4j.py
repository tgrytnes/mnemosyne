"""
Integration tests for Neo4j graph persistence in Story 003.
"""

from datetime import datetime

import pytest

from mnemosyne.alexandria.neo4j_graph_repository import Neo4jGraphRepository
from mnemosyne.alexandria.the_gates import ClusterProfile
from mnemosyne.argus.graph_taxonomy import GraphEdge


@pytest.mark.integration
def test_neo4j_relationship_roundtrip(neo4j_driver):
    repo = Neo4jGraphRepository(neo4j_driver)
    repo.ensure_constraints()

    with neo4j_driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")

    profiles = [
        ClusterProfile(
            cluster_id="cluster-1",
            theme_summary="Project planning",
            dominant_topics=["project", "planning"],
            tags=["project"],
            key_entities=["timeline"],
            confidence_score=0.7,
            representative_note_ids=["note-1"],
            created_at=datetime(2025, 1, 1),
            metadata={},
        ),
        ClusterProfile(
            cluster_id="cluster-2",
            theme_summary="Project execution",
            dominant_topics=["execution", "milestones"],
            tags=["project"],
            key_entities=["milestone"],
            confidence_score=0.6,
            representative_note_ids=["note-2"],
            created_at=datetime(2025, 1, 1),
            metadata={},
        ),
        ClusterProfile(
            cluster_id="cluster-3",
            theme_summary="Delivery risks",
            dominant_topics=["risk"],
            tags=["risk"],
            key_entities=["deadline"],
            confidence_score=0.5,
            representative_note_ids=["note-3"],
            created_at=datetime(2025, 1, 1),
            metadata={},
        ),
    ]

    repo.upsert_clusters(profiles)

    edges = [
        GraphEdge(
            source="cluster-1",
            target="cluster-2",
            edge_type="PARENT_OF",
            score=0.91,
            overlap=0.5,
        ),
        GraphEdge(
            source="cluster-1",
            target="cluster-3",
            edge_type="NEIGHBOR",
            score=0.74,
        ),
    ]

    repo.replace_relationships("cluster-1", edges)

    assert repo.get_children("cluster-1") == ["cluster-2"]
    assert repo.get_parents("cluster-2") == ["cluster-1"]
    assert repo.get_neighbors("cluster-1") == ["cluster-3"]
