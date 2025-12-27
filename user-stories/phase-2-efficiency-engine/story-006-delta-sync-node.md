# Story 006: Delta Sync Node

**As a** writer
**I want** a background node that only re-processes Weaviate clusters that have new vectors
**So that** my "Digital Brain" stays updated without redundant heavy lifting

## Acceptance Criteria
- [ ] Background LangGraph node that runs on a schedule (e.g., every 30 minutes)
- [ ] Tracks last sync timestamp per cluster
- [ ] Identifies clusters with new/modified vectors since last sync
- [ ] Only re-runs Cluster Profile generation (Story 002) for changed clusters
- [ ] Updates cluster relationships (Story 003) if cluster profiles changed
- [ ] Invalidates query cache (Story 005) for affected clusters
- [ ] Logs delta sync statistics (clusters processed, time taken)
- [ ] Graceful handling of sync failures (retry logic)

## Technical Notes

### Delta Detection Strategy
```python
# Option 1: Timestamp-based (requires Weaviate metadata)
changed_clusters = get_clusters_modified_since(last_sync_timestamp)

# Option 2: Vector count comparison
for cluster in all_clusters:
    current_count = weaviate.count_vectors(cluster_id)
    if current_count != cluster.cached_vector_count:
        changed_clusters.append(cluster)
```

### Sync State Tracking
```python
class ClusterSyncState(BaseModel):
    cluster_id: str
    last_sync_timestamp: datetime
    vector_count_at_sync: int
    profile_version: int
    next_sync_scheduled: datetime
```

Store in The Ananke (PostgreSQL)

### LangGraph Background Node
```python
from langgraph.graph import StateGraph
from apscheduler.schedulers.background import BackgroundScheduler

def delta_sync_node(state: SyncState) -> SyncState:
    # 1. Identify changed clusters
    # 2. Re-run Cluster Profile generation
    # 3. Update relationships if needed
    # 4. Invalidate cache
    # 5. Update sync state
    return updated_state

scheduler = BackgroundScheduler()
scheduler.add_job(delta_sync_node, 'interval', minutes=30)
```

### Integration Points
- **The Graphos watcher** (Aletheia): Triggers immediate sync when vault changes detected
- **Story 002**: Re-use Cluster Profile generation logic
- **Story 003**: Re-calculate relationships for affected clusters
- **Story 005**: Invalidate cached queries mentioning affected clusters

### Performance Targets
- Process 10 changed clusters in <5 minutes on Pi 5
- Minimize Weaviate query load (batch operations)
- Avoid blocking user queries

### Dependencies
- The Graphos file watcher (Aletheia) - signals vault changes
- Stories 002, 003, 005 - re-uses their logic
- APScheduler or similar for background jobs
- Alexandria's Weaviate and The Ananke

## Affected Components
- **Aletheia**: The Graphos watcher triggers sync
- **Argus**: Delta sync node implementation
- **Alexandria**: Weaviate queries, sync state in The Ananke

## Priority
**Medium** - Important for keeping vault current, but initial sync is manual

## Estimate
8 story points (5-8 days)

## Linear Labels
`phase-2`, `langgraph`, `background-job`, `performance`, `aletheia`, `argus`

## Related Stories
- Story 002: Structured Metadata Synthesis (re-generates profiles)
- Story 003: Automated Graph Taxonomy (updates relationships)
- Story 005: Semantic Routing (cache invalidation)
