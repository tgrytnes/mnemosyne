# Story 003: Automated Graph Taxonomy

**As a** user
**I want** the Agent to assign "parent" and "neighbor" relationships to clusters
**So that** I can navigate my vault non-linearly

## Acceptance Criteria
- [ ] LangGraph node that analyzes cluster relationships
- [ ] Algorithm to determine parent/child hierarchy (e.g., theme abstraction levels)
- [ ] Algorithm to identify neighbor clusters (e.g., semantic similarity)
- [ ] Relationships stored as a graph structure in The Ananke with a defined table name and unique constraint on `cluster_id`
- [ ] API to query relationships (`get_children`, `get_neighbors`, `get_parents`)
- [ ] Visualization-ready output format (graph JSON with nodes + edges)
- [ ] Cycle handling defined (break weakest edge or downgrade to neighbor)
- [ ] Coverage target: >= 95% of clusters have at least one parent or neighbor
- [ ] Performance target: process 50 clusters in <= 3 minutes on RPi 5
- [ ] Tests: unit tests for relationship rules + integration test for graph persistence

## Technical Notes

### Relationship Types
1. **Parent-Child**: Hierarchical (abstract theme → specific theme)
   - Determined by theme generality and keyword subset relationships
   - Example: "Machine Learning" → "Neural Networks" → "Transformers"

2. **Neighbor**: Lateral (related but not hierarchical)
   - Determined by vector similarity between cluster centroids
   - Threshold: cosine similarity > 0.7
   - Example: "Docker Containers" ↔ "Kubernetes Orchestration"

### Data Model
```python
class ClusterRelationship(BaseModel):
    cluster_id: str
    parent_ids: List[str]
    child_ids: List[str]
    neighbor_ids: List[str]
    relationship_strengths: Dict[str, float]  # cluster_id → similarity score
```

### Algorithm Approach
- Use Cluster Profiles from Story 002
- Compare tag overlaps and theme abstractions for hierarchy
- Use vector similarity for neighbor detection
- Apply graph algorithms to ensure consistency (no orphans, reasonable depth)

### Dependencies
- Story 002 (Structured Metadata Synthesis) - provides profiles
- Alexandria's The Ananke (PostgreSQL for graph storage)
- Weaviate for vector similarity calculations

## Affected Components
- **Argus**: Relationship analysis logic
- **Alexandria**: Graph storage (The Ananke)
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
