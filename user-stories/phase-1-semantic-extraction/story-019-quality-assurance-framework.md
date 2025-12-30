# Story 004: Quality Assurance Framework

**As a** developer
**I want** measurement infrastructure to validate chunking and embedding quality
**So that** I can objectively evaluate improvements and compare chunking strategies

## Acceptance Criteria
- [ ] Can measure embedding quality (5-10 metrics)
- [ ] Can evaluate retrieval performance (recall@k, NDCG)
- [ ] Can compare different chunking strategies objectively
- [ ] Generates actionable quality reports (HTML/Markdown)
- [ ] Baseline metrics established from current recursive chunking approach
- [ ] CLI tool for running quality reports
- [ ] Ground truth dataset for retrieval evaluation (20-30 query-document pairs)

## Technical Notes

### Implementation Approach

**New Modules:**
1. `/src/mnemosyne/iris/quality_metrics.py`
   - `EmbeddingQualityAnalyzer` class
   - `RetrievalEvaluator` class
   - `ChunkingQualityAnalyzer` class
   - `QualityReportGenerator` class

2. `/src/mnemosyne/iris/embedding_quality.py`
   - Cosine similarity distribution analysis
   - Vector space density metrics (cluster tightness)
   - Dimensionality usage analysis
   - Nearest neighbor consistency checks

3. `/src/mnemosyne/iris/retrieval_evaluation.py`
   - Recall@k calculation (k=5, 10, 20)
   - NDCG@k (Normalized Discounted Cumulative Gain)
   - Ground truth dataset loader
   - Regression test runner

4. `/src/mnemosyne/cli/quality.py`
   - CLI commands: `report`, `compare`, `benchmark`
   - Example: `python -m mnemosyne.cli.quality report --output metrics.html`

### Key Metrics

**Embedding Quality:**
- Avg cosine similarity within clusters (should be high)
- Avg cosine similarity between clusters (should be low)
- Vector space coverage (% of dimensions used)
- Embedding collapse detection (all vectors too similar)

**Retrieval Quality:**
- Recall@5, Recall@10, Recall@20
- NDCG@5, NDCG@10, NDCG@20
- Mean Reciprocal Rank (MRR)

**Chunking Quality:**
- Avg chunk size distribution
- Semantic coherence score (intra-chunk similarity)
- Boundary quality (are splits at natural boundaries?)
- Overlap effectiveness (context preserved?)

### Integration with Weaviate

```python
# Use existing vectors for analysis (no re-embedding)
collection = weaviate_client.collections.get("ObsidianNote")
vectors = collection.query.fetch_objects(limit=1000, return_vectors=True)

# Calculate metrics
analyzer = EmbeddingQualityAnalyzer(vectors)
report = analyzer.generate_report()
```

### Quality Report Format (Markdown)

```markdown
# Mnemosyne Quality Report
Generated: 2025-12-28 15:30

## Embedding Quality
- Avg intra-cluster similarity: 0.72 (good)
- Avg inter-cluster similarity: 0.31 (good separation)
- Vector space coverage: 87% (healthy)
- Embedding collapse: No

## Retrieval Performance
- Recall@5: 0.68
- Recall@10: 0.82
- NDCG@10: 0.74

## Chunking Quality
- Avg chunk size: 387 chars (target: 400)
- Semantic coherence: 0.65 (moderate)
- Boundary quality: 78% at sentence boundaries
```

### Dependencies
- Weaviate client library
- NumPy/SciPy for similarity calculations
- Optional: FAISS for efficient nearest neighbor search
- Ground truth dataset (hand-crafted query-document pairs)

## Affected Components
- **Iris**: Primary implementation location (intelligence services)
- **Alexandria**: Data source (Weaviate - The Muses)
- **CLI**: New quality command module

## Priority
**High** - Foundation for validating Stories 005 and 006

## Estimate
8 story points (5-6 days)

## Linear Labels
`phase-1`, `quality-assurance`, `metrics`, `iris`, `core-feature`

## Related Stories
- Story 005: Hierarchical Structure Preservation (uses metrics to validate)
- Story 006: Semantic Chunking with LLM (A/B tested using this framework)
- Story 001: Cluster Centroid Node (quality metrics help evaluate clustering)
