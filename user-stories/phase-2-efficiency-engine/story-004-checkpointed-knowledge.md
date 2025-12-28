# Story 004: Checkpointed Knowledge (Long-term Memory)

**As a** Pi 5 user
**I want** LangGraph to use its built-in persistence (checkpointer) to save the state of my research
**So that** I can resume a complex query even after a reboot

## Acceptance Criteria
- [ ] LangGraph checkpointer configured (SQLite or PostgreSQL backend)
- [ ] Agent state persisted at key nodes (after semantic extraction, after search, after synthesis)
- [ ] Resume functionality: load previous state by query ID
- [ ] State includes: conversation history, intermediate results, current node
- [ ] Checkpoint cleanup policy (auto-delete after 30 days or manual trigger)
- [ ] API endpoints defined to list/resume/delete checkpoints (explicit routes or CLI commands)
- [ ] Performance: State save/load completes in <500ms on Pi 5
- [ ] Cleanup job removes checkpoints older than 30 days (validated by a test)
- [ ] Tests: unit tests for serialization/validation + integration test for persistence + e2e test for resume flow

## Technical Notes

### LangGraph Persistence Setup
```python
from langgraph.checkpoint.sqlite import SqliteSaver

# For Pi 5: Use SQLite for simplicity
checkpointer = SqliteSaver("/data/langgraph-checkpoints.db")

graph = StateGraph(...)
graph = graph.compile(checkpointer=checkpointer)
```

### State Schema
```python
class ResearchState(BaseModel):
    query_id: str
    original_query: str
    current_node: str
    cluster_profiles: List[ClusterProfile]
    search_results: List[Document]
    synthesis_draft: Optional[str]
    timestamp: datetime
    metadata: Dict[str, Any]
```

### Checkpoint Lifecycle
1. **Create**: On first query
2. **Update**: After each LangGraph node completes
3. **Resume**: Load by query_id, continue from current_node
4. **Cleanup**: Cron job deletes checkpoints older than 30 days

### Storage Considerations
- Pi 5 SD card space: Monitor checkpoint DB size
- Compression: Serialize large embeddings efficiently
- Indexing: Fast lookup by query_id and timestamp

### Dependencies
- LangGraph framework with persistence module
- SQLite (or The Ananke PostgreSQL if shared)
- Stories 001-003 (defines what state to checkpoint)

## Affected Components
- **Argus**: Primary user of checkpointing
- **Alexandria**: Potential storage in The Ananke (if using PostgreSQL)
- **Hermes**: Could notify user when resumable queries exist

## Priority
**High** - Critical for Pi 5 usability

## Estimate
5 story points (3-5 days)

## Linear Labels
`phase-2`, `langgraph`, `persistence`, `pi5-optimization`, `argus`

## Related Stories
- Story 005: Semantic Routing (checkpoint before expensive operations)
- Story 007: Multi-Turn Reasoning Loop (uses checkpoints for iterations)
