# Story 002: Structured Metadata Synthesis

**As a** researcher
**I want** the Agent to use Qwen3's JSON mode to generate a "Cluster Profile"
**So that** my knowledge vault has a machine-readable directory of themes and key entities

## Acceptance Criteria
- [ ] LangGraph node that takes cluster data and generates structured metadata
- [ ] Qwen3 integration with JSON mode enabled
- [ ] Cluster Profile schema defined (using Pydantic)
- [ ] Profile includes: theme summary, key entities, tags, confidence scores
- [ ] Profiles stored in The Ananke (PostgreSQL registry) with a defined table name and unique constraint on `cluster_id`
- [ ] Validation uses Pydantic models from The Gates (specify exact module path)
- [ ] Error handling for malformed JSON responses (retry once, then log and mark profile as failed)
- [ ] Success threshold: >= 95% of clusters produce valid profiles in a full run
- [ ] Performance target: process 50 clusters in <= 5 minutes on RPi 5
- [ ] Tests: unit tests for schema validation + integration test with mocked LLM JSON output

## Technical Notes

### Cluster Profile Schema (Pydantic)
```python
class ClusterProfile(BaseModel):
    cluster_id: str
    theme_summary: str
    key_entities: List[str]
    dominant_topics: List[str]
    tags: List[str]
    confidence_score: float
    representative_note_ids: List[str]
    created_at: datetime
    metadata: Dict[str, Any]
```

### LLM Prompt Strategy
- Use few-shot examples for consistent JSON output
- Include representative notes from Story 001 as context
- Request structured extraction of themes, entities, topics
- Use temperature=0.3 for more deterministic outputs

### Dependencies
- Story 001 (Cluster Centroid Node) - provides input data
- Qwen3 model access
- LangGraph framework
- Alexandria's The Ananke (PostgreSQL)
- Alexandria's The Gates (Pydantic validators)

## Affected Components
- **Argus**: LangGraph node implementation
- **Alexandria**: Storage (The Ananke), validation (The Gates)
- **Prometheus**: May use profiles for proposal generation

## Priority
**High** - Core Phase 1 deliverable

## Estimate
8 story points (5-8 days)

## Linear Labels
`phase-1`, `langgraph`, `llm`, `qwen3`, `argus`, `alexandria`, `core-feature`

## Related Stories
- Story 001: Cluster Centroid Node (prerequisite)
- Story 003: Automated Graph Taxonomy (uses profiles)
- Story 006: Delta Sync Node (triggers profile regeneration)
