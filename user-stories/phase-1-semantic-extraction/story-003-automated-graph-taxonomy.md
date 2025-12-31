# Story 003: Automated Graph Taxonomy

**As a** user
**I want** the Agent to assign "parent" and "neighbor" relationships to clusters
**So that** I can navigate my vault non-linearly

## Acceptance Criteria
- [ ] LangGraph node that analyzes cluster relationships
- [ ] Algorithm to determine parent/child hierarchy (theme generality + keyword overlap)
- [ ] Algorithm to identify neighbor clusters (semantic similarity with configurable threshold)
- [ ] Relationships stored in Neo4j with a unique constraint on `Cluster.cluster_id`
- [ ] API to query relationships (`get_children`, `get_neighbors`, `get_parents`)
- [ ] Visualization-ready output format (graph JSON with nodes + edges)
- [ ] Cycle handling defined (downgrade weakest parent edge to neighbor)
- [ ] Coverage target: >= 95% of clusters have at least one parent or neighbor
- [ ] Tests: unit tests for relationship rules + integration test for Neo4j persistence/querying
- [ ] Configurable thresholds: neighbor similarity, parent overlap, generality delta, max parents, max neighbors
- [ ] Neo4j connectivity defined via env vars: `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
- [ ] Graph updates are deterministic and idempotent per run (upsert nodes, replace edges for processed clusters)
- [ ] Weak-profile handling defined (clusters with too few terms become neighbor-only or remain orphaned)
- [ ] Neighbor edges stored once (undirected semantics) to avoid duplication

## Technical Notes

### Relationship Types
1. **Parent-Child**: Hierarchical (abstract theme → specific theme)
   - Determined by theme generality and keyword overlap relationships
   - Example: "Machine Learning" → "Neural Networks" → "Transformers"

2. **Neighbor**: Lateral (related but not hierarchical)
   - Determined by vector similarity between cluster centroids
   - Threshold: cosine similarity > 0.7 (configurable)
   - Example: "Docker Containers" ↔ "Kubernetes Orchestration"

### Data Model (Neo4j)
- Node: `(:Cluster {cluster_id, theme_summary, tags, dominant_topics, confidence_score})`
- Relationships:
  - `(:Cluster)-[:PARENT_OF {score, overlap}]->(:Cluster)`
  - `(:Cluster)-[:NEIGHBOR {score}]-(:Cluster)` (undirected semantics)
- Constraint: `UNIQUE CONSTRAINT ON (c:Cluster) ASSERT c.cluster_id IS UNIQUE`

### Algorithm Approach
- Use Cluster Profiles from Story 002 (stored in Postgres)
- Compare keyword overlap + generality score for hierarchy
- Use vector similarity for neighbor detection (threshold configurable)
- Apply graph rules to ensure consistency (no cycles, avoid orphans when possible)

### Pi 5 Feasibility Notes
- Use top-K candidate pruning (K=10) to avoid all-pairs comparisons.
- Keep similarity computations in memory for 50-200 clusters (small matrices).
- Neo4j Community Edition is sufficient; avoid heavy plugins.

### Concrete Rules (v1 Defaults)
- Token source: `dominant_topics + tags + key_entities` (lowercase, dedupe).
- Term frequency across clusters: `df(term) = clusters_containing_term / total_clusters`.
- Generality score for a cluster: average of `(1 - df(term))` over its terms.
- Keyword overlap: Jaccard similarity of token sets.
- Parent candidate filter:
  - overlap >= 0.4
  - generality_delta >= 0.1 (parent more general than child)
  - semantic similarity >= neighbor threshold
- Parent selection: keep top 2 parents by overlap; ties broken by similarity.
- Neighbor selection: keep top 5 neighbors by similarity above threshold.
- Cycle handling: if a parent edge creates a cycle, downgrade the weakest edge in the cycle
  (lowest similarity, then lowest overlap) to NEIGHBOR.
- Weak-profile handling: if a cluster has < 3 total terms, skip parent assignment and only allow neighbors.
- Edge upsert: for each run, delete existing edges for processed clusters and re-create from current rules.

### Graph JSON Output
```
{
  "nodes": [
    {"id": "cluster_id", "label": "theme_summary", "tags": [], "score": 0.0}
  ],
  "edges": [
    {"source": "cluster_id", "target": "cluster_id", "type": "PARENT_OF", "score": 0.0, "overlap": 0.0},
    {"source": "cluster_id", "target": "cluster_id", "type": "NEIGHBOR", "score": 0.0}
  ]
}
```

### Test Coverage Plan
- Unit:
  - generality score and token normalization
  - overlap and parent candidate selection
  - neighbor selection + caps
  - cycle handling downgrade rules
- Integration (real Neo4j):
  - persist clusters and edges, query via `get_children`, `get_parents`, `get_neighbors`
  - verify unique constraint on `Cluster.cluster_id`
- E2E (real services):
  - small synthetic vault -> cluster profiles -> taxonomy graph in Neo4j
  - verify graph JSON output has expected node/edge counts and non-empty relationships

### Dependencies
- Story 002 (Structured Metadata Synthesis) - provides profiles
- Neo4j for graph storage and querying
- Weaviate for vector similarity calculations

## Affected Components
- **Argus**: Relationship analysis logic
- **Alexandria**: Graph storage (Neo4j integration)
- **Iris**: Will consume this for navigation/search

## Priority
**Medium** - Enhances Phase 1 but not blocking

## Estimate
8 story points (5-8 days)

## Linear Labels
`phase-1`, `langgraph`, `graph-algorithms`, `argus`, `alexandria`

## Related Stories
- Story 002: Structured Metadata Synthesis (prerequisite)
- Story 008: The "Traceable" Showcase (visualizes these relationships)
- Story 009: Actionable Synthesis (uses relationships for note linking)
