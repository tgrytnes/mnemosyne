# Story 011: Radar Vector Exploration

**As a** researcher
**I want** the system to explore "adjacent possible" knowledge spaces autonomously
**So that** I discover connections between seemingly unrelated clusters I wouldn't have explored manually

## Acceptance Criteria
- [ ] Configurable strategies: breadth-first sweep and curiosity-driven (selectable per run)
- [ ] Budgeted run: `budget_seconds` hard-caps runtime; optional `max_pairs_per_cluster` and neighbor skip to avoid obvious edges
- [ ] Identity: every candidate has `discovery_job_key`, deterministic `candidate_key` (ordered cluster ids + type), persisted `discovery_id`; duplicates skipped idempotently
- [ ] State checkpoint of explored cluster pairs so incremental runs resume without reprocessing
- [ ] Weak links stored in Discoveries with embedding, confidence, type, and short explanation; at least one weak link produced on seeded vault in tests
- [ ] Exploration summary persisted (pairs explored, new discoveries, elapsed, strategy) per run
- [ ] Coverage: curiosity strategy prioritizes surprising pairs; breadth-first enumerates systematically

## Technical Notes

### The "Radar Vector" Concept

**Metaphor**: Like radar sweeping across the horizon, systematically exploring each direction.

**Implementation**: Vector space exploration using cluster centroids

```
Your vault = 416-dimensional cluster space
Radar = Systematic pairwise analysis with smart pruning
```

### Exploration Strategies

#### 1. Breadth-First Exploration (Systematic)
```python
class BreadthFirstExplorer:
    def explore(self, budget_minutes: int = 15) -> List[WeakLink]:
        start_time = datetime.now()
        clusters = get_all_clusters()
        unexplored_pairs = self.get_unexplored_pairs(clusters)

        discoveries = []
        for c1, c2 in unexplored_pairs:
            if elapsed_time(start_time) > budget_minutes:
                break

            connection = self.analyze_connection(c1, c2)
            if connection.score > 0.5:  # Threshold for "interesting"
                discoveries.append(connection)

            self.mark_as_explored(c1.id, c2.id)

        return discoveries
```

#### 2. Curiosity-Driven Exploration (Smart)
```python
class CuriosityDrivenExplorer:
    def explore(self, budget_minutes: int = 15) -> List[WeakLink]:
        # Prioritize cluster pairs that are:
        # 1. Semantically distant (surprising connections)
        # 2. Recently updated (fresh content)
        # 3. High "information value" (diverse themes)

        clusters = get_all_clusters()
        prioritized_pairs = self.rank_by_curiosity(clusters)

        discoveries = []
        for c1, c2, curiosity_score in prioritized_pairs:
            if no_time_remaining():
                break

            connection = self.deep_analyze_connection(c1, c2)
            if connection.is_surprising:
                discoveries.append(connection)

        return discoveries

    def rank_by_curiosity(self, clusters: List[Cluster]) -> List[Tuple]:
        pairs = []
        for c1, c2 in combinations(clusters, 2):
            curiosity = self.calculate_curiosity_score(c1, c2)
            pairs.append((c1, c2, curiosity))

        return sorted(pairs, key=lambda x: x[2], reverse=True)

    def calculate_curiosity_score(self, c1: Cluster, c2: Cluster) -> float:
        # Higher score = more interesting to explore
        return (
            self.semantic_distance(c1, c2) * 0.4 +      # Surprising = distant
            self.recency_bonus(c1, c2) * 0.3 +           # Fresh content
            self.information_gain(c1, c2) * 0.3          # Novel combination
        )
```

#### 3. Temporal Pattern Exploration
```python
class TemporalExplorer:
    def explore(self) -> List[TemporalPattern]:
        # Find clusters that co-occur in time
        # Example: "Every time I write about Docker, I write about DevOps within 3 days"

        clusters = get_all_clusters()
        temporal_patterns = []

        for c1 in clusters:
            for c2 in clusters:
                if c1.id == c2.id:
                    continue

                # Get note creation timestamps for each cluster
                c1_timestamps = get_note_timestamps(c1)
                c2_timestamps = get_note_timestamps(c2)

                # Check for temporal correlation
                correlation = self.calculate_temporal_correlation(
                    c1_timestamps,
                    c2_timestamps,
                    window_days=7
                )

                if correlation > 0.7:
                    temporal_patterns.append({
                        'cluster1': c1,
                        'cluster2': c2,
                        'correlation': correlation,
                        'pattern_type': 'co-occurrence',
                        'lag_days': self.calculate_lag(c1_timestamps, c2_timestamps)
                    })

        return temporal_patterns
```

### Weak Link Data Model

```python
class WeakLink(BaseModel):
    """
    A connection between clusters not captured by direct relationships
    """
    id: str
    cluster1_id: str
    cluster2_id: str
    connection_type: Literal['semantic', 'temporal', 'thematic', 'contradictory']
    confidence_score: float
    explanation: str  # LLM-generated explanation of the connection
    evidence: List[str]  # Note IDs that support this connection
    discovered_at: datetime
    explored_by: Literal['breadth_first', 'curiosity_driven', 'temporal']
    user_feedback: Optional[Literal['helpful', 'not_helpful', 'dismissed']]

    # For semantic search
    link_embedding: List[float]
```

### Connection Analysis (Core Logic)

```python
def analyze_connection(c1: Cluster, c2: Cluster) -> Optional[WeakLink]:
    """
    Deep analysis to find non-obvious connections
    """

    # 1. Semantic similarity (but not direct neighbors from Story 003)
    vector_similarity = cosine_similarity(c1.centroid, c2.centroid)

    # Skip if already neighbors or too dissimilar
    if c2.id in c1.neighbor_ids or vector_similarity < 0.3:
        return None

    # 2. Thematic overlap (from cluster profiles)
    theme_overlap = len(set(c1.profile.tags) & set(c2.profile.tags))

    # 3. Entity co-occurrence
    entity_overlap = len(set(c1.profile.key_entities) & set(c2.profile.key_entities))

    # 4. LLM-based explanation (only if promising)
    if vector_similarity > 0.4 or theme_overlap > 2:
        explanation = generate_connection_explanation(c1, c2)

        if explanation.confidence > 0.6:
            return WeakLink(
                cluster1_id=c1.id,
                cluster2_id=c2.id,
                connection_type='semantic',
                confidence_score=explanation.confidence,
                explanation=explanation.text,
                evidence=explanation.supporting_note_ids,
                discovered_at=datetime.now(),
                explored_by='curiosity_driven'
            )

    return None

def generate_connection_explanation(c1: Cluster, c2: Cluster) -> Explanation:
    """
    Use Qwen3 to explain potential connection
    """
    prompt = f"""
    Analyze the connection between these two knowledge clusters:

    Cluster 1: {c1.profile.theme_summary}
    Key entities: {c1.profile.key_entities}
    Tags: {c1.profile.tags}

    Cluster 2: {c2.profile.theme_summary}
    Key entities: {c2.profile.key_entities}
    Tags: {c2.profile.tags}

    Is there a non-obvious connection? If yes, explain it concisely.
    Provide confidence (0-1) and cite specific entities or themes.
    """

    response = qwen3.generate(prompt, json_mode=True)
    return Explanation.parse(response)
```

### Exploration State Tracking

```sql
-- PostgreSQL table in The Ananke
CREATE TABLE exploration_state (
    cluster1_id TEXT NOT NULL,
    cluster2_id TEXT NOT NULL,
    explored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    exploration_strategy TEXT,
    result_type TEXT, -- 'weak_link_found', 'no_connection', 'skipped'
    PRIMARY KEY (cluster1_id, cluster2_id)
);

CREATE INDEX idx_unexplored ON exploration_state(explored_at);
```

### LangGraph Integration

```python
class RadarVectorState(BaseModel):
    exploration_budget_minutes: int
    strategy: Literal['breadth_first', 'curiosity_driven', 'temporal']
    clusters_to_explore: List[Tuple[str, str]]
    weak_links_found: List[WeakLink]
    clusters_processed: int

def build_radar_graph() -> StateGraph:
    graph = StateGraph(RadarVectorState)

    graph.add_node("initialize", init_exploration)
    graph.add_node("select_pairs", select_cluster_pairs_node)
    graph.add_node("analyze", analyze_connections_node)
    graph.add_node("explain", llm_explanation_node)
    graph.add_node("store", store_weak_links_node)

    # Loop until budget exhausted
    graph.add_conditional_edges(
        "analyze",
        lambda state: "explain" if state.time_remaining() else END
    )

    return graph.compile()
```

### Dependencies
- Story 001: Cluster Centroid Node (cluster vectors)
- Story 002: Structured Metadata Synthesis (cluster profiles for comparison)
- Story 003: Automated Graph Taxonomy (to avoid re-discovering direct neighbors)
- Story 010: Autonomous Pattern Detection (shares Discovery DB)
- Alexandria: Weaviate, The Ananke

## Affected Components
- **Argus**: Radar Vector explorer (latent scout)
- **Alexandria**: Discovery DB, exploration state storage
- **Prometheus**: May use weak links for proposal generation

## Priority
**Low** - Advanced feature, build after core scout works

## Estimate
13 story points (8-10 days)

## Linear Labels
`phase-4`, `latent-scout`, `exploration`, `advanced`, `argus`

## Related Stories
- Story 002: Structured Metadata Synthesis (uses profiles)
- Story 003: Automated Graph Taxonomy (complements with weak links)
- Story 010: Autonomous Pattern Detection (runs alongside)
- Story 012: Proactive Insight Notifications (sends weak link discoveries)
- Story 013: Discovery Feed Management (displays weak links)

## Future Enhancements
- Reinforcement learning: Learn which exploration strategies find best connections
- User-guided exploration: "Explore more like this" based on feedback
- Cross-vault radar: Explore connections across multiple vaults
- Visualization: 3D cluster space with radar sweep animation
