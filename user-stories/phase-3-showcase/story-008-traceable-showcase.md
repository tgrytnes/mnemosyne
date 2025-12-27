# Story 008: The "Traceable" Showcase

**As a** presenter
**I want** to use LangGraph Studio to show the path a query took through my 416 clusters
**So that** viewers can see exactly which notes contributed to the final answer

## Acceptance Criteria
- [ ] LangGraph graph instrumented with cluster traversal tracking
- [ ] LangGraph Studio visualization configured and accessible
- [ ] Each node annotates which clusters were accessed
- [ ] Visual representation: cluster graph with highlighted paths
- [ ] Export functionality: save visualization as image/video
- [ ] Demo mode: Pre-loaded example queries with interesting paths
- [ ] Performance: Visualization renders in <5 seconds for 416 clusters

## Technical Notes

### Instrumentation Strategy
```python
class TraceableState(BaseModel):
    query: str
    cluster_path: List[str]  # Ordered list of cluster IDs accessed
    cluster_metadata: Dict[str, ClusterProfile]  # Details for each cluster
    search_decisions: List[Dict]  # Why each cluster was selected
    final_answer: str
    provenance: List[str]  # Note IDs that contributed to answer

def instrumented_search_node(state: TraceableState) -> TraceableState:
    # Log cluster access
    state.cluster_path.append(current_cluster_id)
    state.search_decisions.append({
        "cluster": current_cluster_id,
        "reason": "High similarity to query (0.89)",
        "timestamp": datetime.now()
    })
    # ... perform search
    return state
```

### LangGraph Studio Setup
1. **Graph Export**: Serialize graph definition for Studio
2. **State Snapshots**: Capture state at each node for replay
3. **Visualization Config**: Custom rendering for cluster nodes
4. **Annotations**: Add cluster theme names and similarity scores to edges

### Visualization Enhancements
- **Cluster nodes**: Color-coded by theme (science, code, philosophy, etc.)
- **Edges**: Thickness indicates relevance score
- **Highlights**: Path taken by the query glows
- **Tooltips**: Hover over cluster to see representative notes

### Demo Queries
Prepare 3-5 showcase queries:
1. "How do Docker networks interact with Kubernetes?"
   - Expected path: Docker → Networking → Kubernetes → Container Orchestration
2. "What's the relationship between stoicism and modern productivity?"
   - Expected path: Philosophy → Stoicism → Psychology → Productivity
3. "Explain transformers in the context of LLMs"
   - Expected path: ML → Neural Networks → Transformers → LLMs

### Export Formats
- **PNG/SVG**: Static image of graph with highlighted path
- **GIF**: Animated traversal showing step-by-step
- **JSON**: Raw data for custom visualizations
- **Markdown Report**: Text-based trace with cluster names and excerpts

### Dependencies
- LangGraph Studio (installation and setup)
- Story 003: Automated Graph Taxonomy (cluster relationships)
- Story 007: Multi-Turn Reasoning Loop (generates interesting paths)
- Story 002: Structured Metadata Synthesis (cluster metadata)

## Affected Components
- **Argus**: Instrumentation logic
- **Alexandria**: Cluster data (The Ananke)
- **Hermes**: Could share visualizations via Telegram

## Priority
**Low** - Pure showcase, no functional impact

## Estimate
5 story points (3-5 days)

## Linear Labels
`phase-3`, `langgraph`, `visualization`, `showcase`, `demo`, `argus`

## Related Stories
- Story 003: Automated Graph Taxonomy (provides cluster graph)
- Story 007: Multi-Turn Reasoning Loop (generates traces)
- Story 009: Actionable Synthesis (uses same provenance data)
