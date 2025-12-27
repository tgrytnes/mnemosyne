# Story 010: Autonomous Pattern Detection (Scout)

**As a** knowledge worker
**I want** the system to automatically detect emerging patterns in my vault without me asking
**So that** I discover connections and themes I wouldn't have thought to search for

## 🎯 Architectural Role

**This story implements Scout, the core agent of Argus (Subconscious layer).**

Scout operates autonomously, scanning The Muses nightly to discover latent patterns without user prompting. It bridges the gap between curated knowledge (The Muses) and committed projects (The Ananke) via The Gates approval system.

## Acceptance Criteria
- [ ] Background job runs on schedule (daily at 2 AM or configurable)
- [ ] Systematic analysis across all clusters using shared insight engines
- [ ] Detects multiple pattern types: emerging themes, orphaned clusters, contradictions, project candidates
- [ ] Results stored in Discovery Vector DB with metadata (timestamp, pattern type, confidence)
- [ ] Deduplication logic prevents re-notifying about same patterns
- [ ] Performance: Complete analysis of 416 clusters in <30 minutes on Pi 5
- [ ] Configurable thresholds for each pattern type
- [ ] Dry-run mode for testing pattern detection

## Technical Notes

### Pattern Types to Detect

#### 1. Emerging Themes
```python
class EmergingThemeDetector:
    def detect(self, time_window_days: int = 30) -> List[Theme]:
        # Find clusters with sudden growth
        # Threshold: 3+ new notes in time_window
        recent_notes = get_notes_since(days_ago=time_window_days)
        cluster_velocity = group_by_cluster(recent_notes)

        emerging = [
            cluster for cluster, count in cluster_velocity.items()
            if count >= 3 and cluster.previous_velocity < 1
        ]
        return emerging
```

#### 2. Orphaned Clusters
```python
class OrphanedClusterDetector:
    def detect(self) -> List[Cluster]:
        # Find clusters with no relationships to others
        # Uses graph from Story 003
        all_clusters = get_all_clusters()
        orphans = [
            cluster for cluster in all_clusters
            if len(cluster.neighbors) == 0 and len(cluster.parents) == 0
        ]
        return orphans
```

#### 3. Contradiction Detection
```python
class ContradictionDetector:
    def detect(self) -> List[Contradiction]:
        # Find clusters with semantically opposing content
        # Use embedding similarity + sentiment analysis
        clusters = get_all_clusters()
        contradictions = []

        for c1, c2 in combinations(clusters, 2):
            if are_contradictory(c1.profile, c2.profile):
                contradictions.append({
                    'cluster1': c1,
                    'cluster2': c2,
                    'contradiction_type': classify_contradiction(c1, c2),
                    'confidence': calculate_confidence(c1, c2)
                })
        return contradictions
```

#### 4. Project Candidates
```python
class ProjectnessDetector:
    def detect(self) -> List[ProjectCandidate]:
        # Heuristics for "projectness"
        # - Multiple related notes (5+)
        # - Temporal clustering (notes created in bursts)
        # - Action-oriented language
        # - Cross-cluster references

        candidates = []
        for cluster in get_all_clusters():
            score = self.calculate_projectness_score(cluster)
            if score > 0.7:
                candidates.append({
                    'cluster': cluster,
                    'score': score,
                    'signals': self.get_projectness_signals(cluster)
                })
        return candidates

    def calculate_projectness_score(self, cluster: Cluster) -> float:
        signals = {
            'note_count': min(cluster.note_count / 10, 1.0) * 0.3,
            'temporal_density': self.temporal_clustering(cluster) * 0.2,
            'action_verbs': self.count_action_verbs(cluster) * 0.2,
            'cross_references': self.count_cross_refs(cluster) * 0.3
        }
        return sum(signals.values())
```

### Discovery Vector DB Schema

```python
class DiscoveryRecord(BaseModel):
    id: str
    pattern_type: Literal['emerging_theme', 'orphan', 'contradiction', 'project_candidate']
    cluster_ids: List[str]
    title: str
    description: str
    confidence_score: float
    detected_at: datetime
    notified_at: Optional[datetime]
    dismissed_at: Optional[datetime]
    metadata: Dict[str, Any]

    # Embeddings for semantic search of discoveries
    discovery_embedding: List[float]
```

Storage: Weaviate collection "Discoveries" or separate PostgreSQL table in The Ananke

### Background Job Implementation

```python
from apscheduler.schedulers.background import BackgroundScheduler
from langgraph.graph import StateGraph

class LatentScoutState(BaseModel):
    run_id: str
    start_time: datetime
    patterns_detected: Dict[str, List[DiscoveryRecord]]
    clusters_analyzed: int
    errors: List[str]

def build_scout_graph() -> StateGraph:
    graph = StateGraph(LatentScoutState)

    graph.add_node("initialize", initialize_run)
    graph.add_node("detect_emerging_themes", emerging_theme_node)
    graph.add_node("detect_orphans", orphan_detection_node)
    graph.add_node("detect_contradictions", contradiction_node)
    graph.add_node("detect_projects", projectness_node)
    graph.add_node("store_discoveries", store_to_db_node)
    graph.add_node("notify", notify_via_hermes_node)

    graph.set_entry_point("initialize")
    graph.add_edge("initialize", "detect_emerging_themes")
    graph.add_edge("detect_emerging_themes", "detect_orphans")
    graph.add_edge("detect_orphans", "detect_contradictions")
    graph.add_edge("detect_contradictions", "detect_projects")
    graph.add_edge("detect_projects", "store_discoveries")
    graph.add_edge("store_discoveries", "notify")

    return graph.compile()

# Schedule the job
scheduler = BackgroundScheduler()
scout_graph = build_scout_graph()

def run_latent_scout():
    initial_state = LatentScoutState(
        run_id=str(uuid4()),
        start_time=datetime.now(),
        patterns_detected={},
        clusters_analyzed=0,
        errors=[]
    )
    result = scout_graph.invoke(initial_state)
    log_scout_run(result)

scheduler.add_job(run_latent_scout, 'cron', hour=2, minute=0)  # 2 AM daily
scheduler.start()
```

### Deduplication Strategy

```python
def is_duplicate_discovery(new_discovery: DiscoveryRecord) -> bool:
    # Check if we've seen this pattern in last 7 days
    recent_discoveries = get_discoveries_since(days_ago=7)

    for existing in recent_discoveries:
        # Same pattern type and overlapping clusters
        if (existing.pattern_type == new_discovery.pattern_type and
            set(existing.cluster_ids) & set(new_discovery.cluster_ids)):

            # Check if substantially different
            similarity = cosine_similarity(
                existing.discovery_embedding,
                new_discovery.discovery_embedding
            )
            if similarity > 0.9:
                return True  # Too similar, skip

    return False
```

### Dependencies
- Story 001: Cluster Centroid Node (cluster analysis)
- Story 002: Structured Metadata Synthesis (cluster profiles)
- Story 003: Automated Graph Taxonomy (relationship graph)
- Alexandria: Weaviate (Discovery DB), The Ananke (storage)
- APScheduler or similar for background jobs

## Affected Components
- **Argus**: Latent Scout implementation (new `scout/` subdirectory)
- **Alexandria**: Discovery Vector DB storage
- **Hermes**: Will receive notifications (Story 012)

## Priority
**Medium** - Enhances system but not critical for MVP

## Estimate
13 story points (8-10 days)

## Linear Labels
`phase-4`, `latent-scout`, `background-job`, `pattern-detection`, `argus`

## Related Stories
- Story 002: Structured Metadata Synthesis (uses cluster profiles)
- Story 003: Automated Graph Taxonomy (uses graph data)
- Story 011: Radar Vector Exploration (uses same discovery DB)
- Story 012: Proactive Insight Notifications (sends discoveries)
- Story 013: Discovery Feed Management (UI for reviewing discoveries)

## Future Enhancements
- Machine learning models for pattern detection (train on user feedback)
- User-defined custom patterns (DSL or config-based)
- Confidence calibration based on user accept/dismiss rates
- Cross-vault pattern detection (if multiple vaults)
