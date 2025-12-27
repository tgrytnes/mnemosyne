# Story 003: Automated Graph Taxonomy

**As a** user
**I want** the Agent to assign "parent" and "neighbor" relationships to clusters
**So that** I can navigate my vault non-linearly

## Acceptance Criteria
- [ ] LangGraph node that analyzes cluster relationships
- [ ] Algorithm to determine parent/child hierarchy (e.g., theme abstraction levels)
- [ ] Algorithm to identify neighbor clusters (e.g., semantic similarity)
- [ ] Relationships stored as a graph structure in The Ananke
- [ ] API to query relationships (get children, get neighbors, get parents)
- [ ] Visualization-ready output format (e.g., graph JSON)
- [ ] Handle cycles and ambiguous relationships gracefully

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
