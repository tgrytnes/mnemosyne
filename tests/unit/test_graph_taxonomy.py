"""
Unit tests for Story 003 automated graph taxonomy rules.
"""

from datetime import datetime

from mnemosyne.alexandria.the_gates import ClusterProfile
from mnemosyne.argus.graph_taxonomy import (
    GraphEdge,
    GraphTaxonomyBuilder,
    GraphTaxonomyConfig,
    compute_generality_scores,
    jaccard_overlap,
    resolve_parent_cycles,
    tokenize_profile_terms,
)


def _profile(
    cluster_id: str,
    dominant_topics: list[str] | None = None,
    tags: list[str] | None = None,
    key_entities: list[str] | None = None,
) -> ClusterProfile:
    return ClusterProfile(
        cluster_id=cluster_id,
        theme_summary=f"summary-{cluster_id}",
        dominant_topics=dominant_topics or [],
        tags=tags or [],
        key_entities=key_entities or [],
        confidence_score=0.5,
        representative_note_ids=[f"note-{cluster_id}"],
        created_at=datetime(2025, 1, 1),
        metadata={},
    )


def test_tokenize_profile_terms_lowercase_and_dedupe():
    profile = _profile(
        "c1",
        dominant_topics=["Machine Learning", "Project"],
        tags=["project", "Research"],
        key_entities=["Neural Networks", "Project"],
    )

    terms = tokenize_profile_terms(profile)

    assert terms == {"machine learning", "project", "research", "neural networks"}


def test_generality_scores_reflect_term_frequency():
    profiles = [
        _profile("parent", dominant_topics=["project", "planning"]),
        _profile(
            "child",
            dominant_topics=["project", "planning", "timeline", "budget"],
        ),
        _profile("other", dominant_topics=["project", "planning", "notes"]),
    ]

    term_sets = {profile.cluster_id: tokenize_profile_terms(profile) for profile in profiles}
    scores = compute_generality_scores(term_sets)

    assert scores["parent"] < scores["child"]


def test_jaccard_overlap_matches_expected_ratio():
    assert jaccard_overlap({"a", "b"}, {"a"}) == 0.5
    assert jaccard_overlap({"a"}, {"a"}) == 1.0
    assert jaccard_overlap(set(), set()) == 1.0


def test_parent_selection_prefers_more_general_cluster():
    profiles = [
        _profile("parent", dominant_topics=["project", "planning"]),
        _profile(
            "child",
            dominant_topics=["project", "planning", "timeline", "budget"],
        ),
        _profile("other", dominant_topics=["project", "planning", "notes"]),
    ]

    similarity = {
        ("parent", "child"): 0.9,
        ("child", "parent"): 0.9,
        ("other", "child"): 0.8,
        ("child", "other"): 0.8,
        ("parent", "other"): 0.75,
        ("other", "parent"): 0.75,
    }

    config = GraphTaxonomyConfig(max_parents=1)
    builder = GraphTaxonomyBuilder(config)
    graph = builder.build(profiles, similarity)

    assert graph.parents["child"] == ["parent"]


def test_neighbor_selection_respects_threshold_and_cap():
    profiles = [
        _profile("a", dominant_topics=["a"]),
        _profile("b", dominant_topics=["b"]),
        _profile("c", dominant_topics=["c"]),
        _profile("d", dominant_topics=["d"]),
    ]

    similarity = {
        ("a", "b"): 0.9,
        ("b", "a"): 0.9,
        ("a", "c"): 0.8,
        ("c", "a"): 0.8,
        ("a", "d"): 0.6,
        ("d", "a"): 0.6,
    }

    config = GraphTaxonomyConfig(
        parent_overlap_threshold=1.0,
        neighbor_similarity_threshold=0.7,
        max_neighbors=2,
    )
    builder = GraphTaxonomyBuilder(config)
    graph = builder.build(profiles, similarity)

    assert graph.neighbors["a"] == ["b", "c"]


def test_cycle_handling_downgrades_weakest_edge():
    edges = [
        GraphEdge(source="a", target="b", edge_type="PARENT_OF", score=0.9, overlap=0.6),
        GraphEdge(source="b", target="c", edge_type="PARENT_OF", score=0.8, overlap=0.5),
        GraphEdge(source="c", target="a", edge_type="PARENT_OF", score=0.7, overlap=0.4),
    ]

    resolved = resolve_parent_cycles(edges)

    downgraded = [
        edge
        for edge in resolved
        if edge.source == "c" and edge.target == "a" and edge.edge_type == "NEIGHBOR"
    ]

    assert len(downgraded) == 1
    assert sum(edge.edge_type == "PARENT_OF" for edge in resolved) == 2
