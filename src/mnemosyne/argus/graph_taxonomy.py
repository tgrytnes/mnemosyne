"""Graph taxonomy utilities for Story 003 (skeleton)."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field

from mnemosyne.alexandria.the_gates import ClusterProfile


@dataclass(frozen=True)
class GraphEdge:
    source: str
    target: str
    edge_type: str
    score: float
    overlap: float | None = None


@dataclass
class GraphTaxonomyConfig:
    neighbor_similarity_threshold: float = 0.7
    parent_overlap_threshold: float = 0.4
    parent_generality_delta: float = 0.1
    max_parents: int = 2
    max_neighbors: int = 5
    top_k_candidates: int = 10
    min_terms_for_parents: int = 3


@dataclass
class GraphTaxonomyResult:
    parents: dict[str, list[str]] = field(default_factory=dict)
    children: dict[str, list[str]] = field(default_factory=dict)
    neighbors: dict[str, list[str]] = field(default_factory=dict)
    edges: list[GraphEdge] = field(default_factory=list)


def tokenize_profile_terms(profile: ClusterProfile) -> set[str]:
    """Return the normalized term set for a cluster profile."""
    terms: set[str] = set()
    for term in profile.dominant_topics + profile.tags + profile.key_entities:
        if not isinstance(term, str):
            continue
        cleaned = term.strip().lower()
        if cleaned:
            terms.add(cleaned)
    return terms


def jaccard_overlap(left: set[str], right: set[str]) -> float:
    """Compute Jaccard overlap between two sets."""
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def compute_generality_scores(term_sets: dict[str, set[str]]) -> dict[str, float]:
    """Compute generality scores for each cluster."""
    if not term_sets:
        return {}
    total_clusters = len(term_sets)
    term_counts = Counter(
        term for terms in term_sets.values() for term in terms
    )

    scores: dict[str, float] = {}
    for cluster_id, terms in term_sets.items():
        if not terms:
            scores[cluster_id] = 0.0
            continue
        values = [(1 - (term_counts[term] / total_clusters)) for term in terms]
        scores[cluster_id] = sum(values) / len(values)
    return scores


def resolve_parent_cycles(edges: list[GraphEdge]) -> list[GraphEdge]:
    """Resolve cycles in parent relationships by downgrading weakest edges."""
    parent_edges = [edge for edge in edges if edge.edge_type == "PARENT_OF"]
    other_edges = [edge for edge in edges if edge.edge_type != "PARENT_OF"]

    def find_cycle(edges_list: list[GraphEdge]) -> list[GraphEdge] | None:
        adjacency: dict[str, list[str]] = defaultdict(list)
        edge_map: dict[tuple[str, str], GraphEdge] = {}
        nodes: set[str] = set()
        for edge in edges_list:
            adjacency[edge.source].append(edge.target)
            edge_map[(edge.source, edge.target)] = edge
            nodes.add(edge.source)
            nodes.add(edge.target)

        visited: set[str] = set()
        stack: list[str] = []
        stack_edges: list[GraphEdge] = []
        on_stack: set[str] = set()

        def dfs(node: str) -> list[GraphEdge] | None:
            visited.add(node)
            on_stack.add(node)
            stack.append(node)

            for neighbor in adjacency.get(node, []):
                edge = edge_map[(node, neighbor)]
                if neighbor not in visited:
                    stack_edges.append(edge)
                    cycle = dfs(neighbor)
                    if cycle:
                        return cycle
                    stack_edges.pop()
                elif neighbor in on_stack:
                    idx = stack.index(neighbor)
                    cycle_edges = stack_edges[idx:] + [edge]
                    return cycle_edges

            stack.pop()
            on_stack.remove(node)
            return None

        for node in nodes:
            if node in visited:
                continue
            cycle = dfs(node)
            if cycle:
                return cycle
        return None

    while True:
        cycle_edges = find_cycle(parent_edges)
        if not cycle_edges:
            break
        weakest = min(
            cycle_edges,
            key=lambda edge: (edge.score, edge.overlap or 0.0),
        )
        parent_edges.remove(weakest)
        other_edges.append(
            GraphEdge(
                source=weakest.source,
                target=weakest.target,
                edge_type="NEIGHBOR",
                score=weakest.score,
                overlap=weakest.overlap,
            )
        )

    return parent_edges + other_edges


def _similarity_score(
    similarity: dict[tuple[str, str], float], left: str, right: str
) -> float:
    if (left, right) in similarity:
        return similarity[(left, right)]
    if (right, left) in similarity:
        return similarity[(right, left)]
    return 0.0


class GraphTaxonomyBuilder:
    """Build parent/neighbor relationships from profiles and similarity scores."""

    def __init__(self, config: GraphTaxonomyConfig | None = None) -> None:
        self.config = config or GraphTaxonomyConfig()

    def build(
        self,
        profiles: Iterable[ClusterProfile],
        similarity: dict[tuple[str, str], float],
    ) -> GraphTaxonomyResult:
        profile_list = list(profiles)
        cluster_ids = [profile.cluster_id for profile in profile_list]
        term_sets = {
            profile.cluster_id: tokenize_profile_terms(profile) for profile in profile_list
        }
        generality = compute_generality_scores(term_sets)

        parent_edges: list[GraphEdge] = []

        for child_id in cluster_ids:
            child_terms = term_sets.get(child_id, set())
            if len(child_terms) < self.config.min_terms_for_parents:
                continue

            candidates: list[tuple[str, float, float]] = []
            for parent_id in cluster_ids:
                if parent_id == child_id:
                    continue
                similarity_score = _similarity_score(similarity, child_id, parent_id)
                if similarity_score < self.config.neighbor_similarity_threshold:
                    continue
                overlap = jaccard_overlap(child_terms, term_sets.get(parent_id, set()))
                if overlap < self.config.parent_overlap_threshold:
                    continue
                generality_gap = generality.get(child_id, 0.0) - generality.get(parent_id, 0.0)
                if generality_gap < self.config.parent_generality_delta:
                    continue
                candidates.append((parent_id, overlap, similarity_score))

            candidates.sort(key=lambda item: (-item[1], -item[2], item[0]))
            for parent_id, overlap, similarity_score in candidates[: self.config.max_parents]:
                parent_edges.append(
                    GraphEdge(
                        source=parent_id,
                        target=child_id,
                        edge_type="PARENT_OF",
                        score=similarity_score,
                        overlap=overlap,
                    )
                )

        resolved_edges = resolve_parent_cycles(parent_edges)
        final_parent_edges = [edge for edge in resolved_edges if edge.edge_type == "PARENT_OF"]
        downgraded_edges = [edge for edge in resolved_edges if edge.edge_type == "NEIGHBOR"]

        parents: dict[str, list[str]] = {cluster_id: [] for cluster_id in cluster_ids}
        children: dict[str, list[str]] = {cluster_id: [] for cluster_id in cluster_ids}
        for edge in final_parent_edges:
            parents[edge.target].append(edge.source)
            children[edge.source].append(edge.target)

        neighbors: dict[str, list[str]] = {cluster_id: [] for cluster_id in cluster_ids}
        neighbor_scores: dict[tuple[str, str], float] = {}

        def add_neighbor(left: str, right: str, score: float) -> None:
            if right not in neighbors[left]:
                neighbors[left].append(right)
            neighbor_scores[(left, right)] = score

        for edge in downgraded_edges:
            add_neighbor(edge.source, edge.target, edge.score)
            add_neighbor(edge.target, edge.source, edge.score)

        for cluster_id in cluster_ids:
            if len(neighbors[cluster_id]) >= self.config.max_neighbors:
                continue
            candidate_neighbors: list[tuple[str, float]] = []
            for other_id in cluster_ids:
                if other_id == cluster_id:
                    continue
                if other_id in parents.get(cluster_id, []) or other_id in children.get(
                    cluster_id, []
                ):
                    continue
                similarity_score = _similarity_score(similarity, cluster_id, other_id)
                if similarity_score < self.config.neighbor_similarity_threshold:
                    continue
                candidate_neighbors.append((other_id, similarity_score))

            candidate_neighbors.sort(key=lambda item: (-item[1], item[0]))
            for other_id, similarity_score in candidate_neighbors:
                if len(neighbors[cluster_id]) >= self.config.max_neighbors:
                    break
                if other_id in neighbors[cluster_id]:
                    continue
                add_neighbor(cluster_id, other_id, similarity_score)

        neighbor_edges: list[GraphEdge] = []
        seen_pairs: set[tuple[str, str]] = set()
        for source_id, neighbor_list in neighbors.items():
            for target_id in neighbor_list:
                pair = tuple(sorted((source_id, target_id)))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                score = neighbor_scores.get((source_id, target_id))
                if score is None:
                    score = _similarity_score(similarity, source_id, target_id)
                neighbor_edges.append(
                    GraphEdge(
                        source=pair[0],
                        target=pair[1],
                        edge_type="NEIGHBOR",
                        score=score,
                    )
                )

        edges = final_parent_edges + neighbor_edges
        return GraphTaxonomyResult(
            parents=parents,
            children=children,
            neighbors=neighbors,
            edges=edges,
        )
