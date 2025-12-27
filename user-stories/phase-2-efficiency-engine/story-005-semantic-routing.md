# Story 005: Semantic Routing (Iris - Intelligence Services)

**As a** developer
**I want** a "Router Node" that decides if a question can be answered by the local SQLite cache or if it needs to trigger a full Weaviate search
**So that** I save the Pi's CPU cycles

## 🎯 Architectural Role

**This story implements the routing logic for Iris (Intelligence Services layer).**

Iris is the user-facing intelligence layer that provides semantic search and query answering. The router determines which database (The Muses, The Lethe, The Ananke) to query, or whether to use cached results or web search.

## Acceptance Criteria
- [ ] LangGraph Router Node implementation
- [ ] SQLite cache for common queries/patterns
- [ ] Decision logic: cache hit vs. Weaviate search vs. web search
- [ ] Cache stores: query embeddings, results, timestamp
- [ ] Cache invalidation strategy (time-based or vault-update-based)
- [ ] Metrics: cache hit rate logged
- [ ] Performance: Routing decision completes in <100ms
- [ ] Fallback: Always route to Weaviate if cache is stale or uncertain

## Technical Notes

### Router Decision Tree
```
Query → [Embed Query] → [Router Node]
                            ├─ Cache hit (>0.95 similarity) → Return cached result
                            ├─ Cluster-specific → Weaviate search (The Muses)
                            ├─ Fact-based → SQLite lookup (The Ananke)
                            └─ Web-dependent → Web search (Iris)
```

### Cache Schema (SQLite)
```sql
CREATE TABLE query_cache (
    id INTEGER PRIMARY KEY,
    query_text TEXT NOT NULL,
    query_embedding BLOB NOT NULL,
    result_json TEXT NOT NULL,
    source TEXT NOT NULL, -- 'cache', 'weaviate', 'web'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP,
    access_count INTEGER DEFAULT 0
);

CREATE INDEX idx_query_embedding ON query_cache(query_embedding);
```

### Routing Logic
1. **Embed incoming query** (lightweight model: sentence-transformers)
2. **Check cache**: cosine similarity > 0.95 threshold
3. **If cache miss**: Classify query type
   - Fact retrieval → The Ananke
   - Semantic search → Weaviate (The Muses)
   - External info → Web search (Iris)
4. **Execute appropriate search**
5. **Update cache** with new result

### Performance Optimizations
- In-memory LRU cache (top 100 queries) + SQLite for cold storage
- Parallel routing: Check cache while embedding
- Batch similar queries

### Dependencies
- LangGraph for router node
- Sentence-transformers or similar for query embeddings
- SQLite for cache storage
- Alexandria's Weaviate and The Ananke

## Affected Components
- **Argus**: Router node implementation
- **Alexandria**: Cache storage (SQLite or The Ananke)
- **Iris**: Fallback to web search

## Priority
**High** - Critical for Pi 5 performance

## Estimate
8 story points (5-8 days)

## Linear Labels
`phase-2`, `langgraph`, `performance`, `caching`, `pi5-optimization`, `argus`

## Related Stories
- Story 004: Checkpointed Knowledge (router checkpoint before expensive ops)
- Story 006: Delta Sync Node (cache invalidation on vault updates)
- Story 007: Multi-Turn Reasoning Loop (uses router for each iteration)
