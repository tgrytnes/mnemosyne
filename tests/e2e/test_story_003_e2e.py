"""
E2E tests for Story 003 - Automated Graph Taxonomy with Neo4j.
"""

import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import pytest
from weaviate.classes.query import Filter

from mnemosyne.alexandria.cluster_profile_repository import ClusterProfileRepository
from mnemosyne.alexandria.the_gates import ClusterProfile
from mnemosyne.alexandria.weaviate_schema import (
    ClusterCentroidLethe,
    WeaviateSchemaManager,
)
from mnemosyne.argus.graph_taxonomy import GraphTaxonomyConfig
from mnemosyne.argus.graph_taxonomy_pipeline import GraphTaxonomyPipeline


@pytest.mark.e2e
@pytest.mark.postgres
@pytest.mark.weaviate
def test_story_003_builds_taxonomy_graph(
    weaviate_client, postgres_connection, neo4j_driver, fake_vault_path
):
    schema = WeaviateSchemaManager(weaviate_client)
    schema.ensure_collection_exists(ClusterCentroidLethe.collection_name)

    collection = weaviate_client.collections.get(ClusterCentroidLethe.collection_name)
    collection.data.delete_many(where=Filter.by_property("clusterId").greater_or_equal(0))

    now = datetime.now(UTC)
    collection.data.insert(
        properties={"clusterId": 1, "clusterSize": 8, "lastUpdated": now},
        vector={"default": [1.0, 0.0]},
    )
    collection.data.insert(
        properties={"clusterId": 2, "clusterSize": 6, "lastUpdated": now},
        vector={"default": [0.9, 0.1]},
    )
    collection.data.insert(
        properties={"clusterId": 3, "clusterSize": 5, "lastUpdated": now},
        vector={"default": [0.0, 1.0]},
    )

    project_notes = _load_named_notes(
        fake_vault_path,
        "projects",
        [
            "project_alpha.md",
            "project_beta.md",
            "project_gamma.md",
            "project_delta.md",
            "deploy_plan.md",
            "retro_issues.md",
        ],
    )
    knowledge_notes = _load_named_notes(
        fake_vault_path,
        "knowledge",
        [
            "embedding_models.md",
            "weaviate_schema.md",
            "taxonomy_heuristics.md",
            "vector_cleanup.md",
            "retrieval_failures.md",
            "neo4j_notes.md",
        ],
    )
    journal_notes = _load_named_notes(
        fake_vault_path,
        "journal",
        [
            "meeting_notes.md",
            "standup_2024-02-15.md",
            "meeting_2024-03-01.md",
            "standup_2024-03-05.md",
            "experiment_2024-03-10.md",
            "brain_dump_chaos.md",
        ],
    )

    project_terms = _extract_terms(project_notes, limit=6)
    knowledge_terms = _extract_terms(knowledge_notes, limit=6)
    journal_terms = _extract_terms(journal_notes, limit=6)

    profile_repo = ClusterProfileRepository(postgres_connection)
    profile_repo.ensure_table()
    profile_repo.save(
        ClusterProfile(
            cluster_id="1",
            theme_summary="Lethe: Project planning",
            dominant_topics=project_terms[:3],
            tags=["project"],
            key_entities=project_terms[:2],
            confidence_score=0.7,
            representative_note_ids=_note_ids(project_notes),
            created_at=now,
            metadata={"source": "lethe", "section": "projects"},
        ),
        source="lethe",
    )
    profile_repo.save(
        ClusterProfile(
            cluster_id="2",
            theme_summary="Lethe: Project execution",
            dominant_topics=project_terms[:6],
            tags=["project"],
            key_entities=project_terms[:3],
            confidence_score=0.6,
            representative_note_ids=_note_ids(project_notes),
            created_at=now,
            metadata={"source": "lethe", "section": "projects"},
        ),
        source="lethe",
    )
    profile_repo.save(
        ClusterProfile(
            cluster_id="3",
            theme_summary="Lethe: Knowledge and journal mix",
            dominant_topics=knowledge_terms[:3] + journal_terms[:2],
            tags=["knowledge"],
            key_entities=journal_terms[:2],
            confidence_score=0.5,
            representative_note_ids=_note_ids(journal_notes + knowledge_notes),
            created_at=now,
            metadata={"source": "lethe", "section": "mixed"},
        ),
        source="lethe",
    )
    profile_repo.save(
        ClusterProfile(
            cluster_id="1",
            theme_summary="Muses: Should be ignored",
            dominant_topics=project_terms[:2],
            tags=["muses"],
            key_entities=project_terms[:1],
            confidence_score=0.9,
            representative_note_ids=_note_ids(project_notes),
            created_at=now,
            metadata={"source": "muses", "section": "projects"},
        ),
        source="muses",
    )

    config = GraphTaxonomyConfig(
        neighbor_similarity_threshold=0.7,
        parent_overlap_threshold=0.4,
        parent_generality_delta=0.1,
        max_parents=2,
        max_neighbors=5,
        top_k_candidates=10,
    )

    pipeline = GraphTaxonomyPipeline(
        weaviate_client=weaviate_client,
        postgres_connection=postgres_connection,
        neo4j_driver=neo4j_driver,
        config=config,
    )

    graph = pipeline.build_graph(cluster_ids=["1", "2", "3"])

    assert len(graph["nodes"]) == 3
    assert all("Lethe" in node["label"] for node in graph["nodes"])
    assert any(edge["type"] == "PARENT_OF" for edge in graph["edges"])
    assert any(
        edge["source"] == "1" and edge["target"] == "2" and edge["type"] == "PARENT_OF"
        for edge in graph["edges"]
    )


def _load_named_notes(base_path: Path, subdir: str, filenames: list[str]) -> list[str]:
    folder = base_path / subdir
    notes = []
    for name in filenames:
        path = folder / name
        if not path.exists():
            pytest.fail(f"Expected note missing: {path}")
        notes.append(path.read_text(encoding="utf-8"))
    return notes


def _note_ids(notes: list[str]) -> list[str]:
    return [f"note-{index}" for index in range(len(notes))]


def _extract_terms(notes: list[str], limit: int) -> list[str]:
    text = " ".join(notes).lower()
    tokens = re.findall(r"[a-z][a-z0-9-]+", text)
    stopwords = {
        "about",
        "after",
        "again",
        "also",
        "and",
        "are",
        "been",
        "before",
        "but",
        "data",
        "does",
        "for",
        "from",
        "have",
        "into",
        "note",
        "notes",
        "that",
        "this",
        "with",
        "your",
    }
    filtered = [token for token in tokens if len(token) > 3 and token not in stopwords]
    counts = Counter(filtered)
    return [token for token, _ in counts.most_common(limit)]
