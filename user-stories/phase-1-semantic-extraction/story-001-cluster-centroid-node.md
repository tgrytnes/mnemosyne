# Story 001: Cluster Centroid Node

**As a** developer
**I want** a LangGraph node that automatically pulls the 5 most representative notes from a Weaviate cluster
**So that** the Agent starts its reasoning with the highest-quality data

## Acceptance Criteria
- [ ] LangGraph node implementation that queries Weaviate
- [ ] Algorithm to identify the 5 most representative vectors in a cluster (e.g., closest to centroid)
- [ ] Node returns structured data (note IDs, metadata, content snippets)
- [ ] Performance: Query completes in <2 seconds on Pi 5
- [ ] Unit tests for centroid calculation
- [ ] Integration test with sample Weaviate cluster

## Technical Notes

### Implementation Approach
- Use Weaviate's vector search with `nearVector` query
- Calculate cluster centroid by averaging all vectors in the cluster
- Query for top 5 vectors nearest to centroid
- Cache centroid calculations for clusters that haven't changed

### Dependencies
- Weaviate client library
- LangGraph framework
- Alexandria's Weaviate instance (The Lethe or The Muses)

### Data Flow
```
Cluster ID → [Centroid Node] → {
  centroid_vector: [...],
  representative_notes: [
    {id, title, content_snippet, distance_from_centroid},
    ...
  ]
}
```

## Affected Components
- **Argus**: Primary implementation location (background agents)
- **Alexandria**: Data source (Weaviate - The Muses)

## Priority
**High** - Foundation for Phase 1

## Estimate
5 story points (3-5 days)

## Linear Labels
`phase-1`, `langgraph`, `weaviate`, `argus`, `core-feature`

## Related Stories
- Story 002: Structured Metadata Synthesis (depends on this)
- Story 004: Checkpointed Knowledge (uses output from this)
