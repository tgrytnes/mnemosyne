# Story 022: Quality Testing Matrix (Non-Functional)

**As a** system architect
**I want** comprehensive quality testing across different LLM models, chunking strategies, and clustering configurations
**So that** I can make data-driven decisions about optimal system configurations for different use cases

## Acceptance Criteria
- [ ] Test matrix covers 3+ LLM models (embedding + generation)
- [ ] Test matrix covers 3 chunking strategies (recursive, semantic, hybrid)
- [ ] Test matrix covers 2+ clustering algorithms (k-means, HDBSCAN)
- [ ] Automated benchmark suite runs on real data (100+ files)
- [ ] Quality metrics captured for each configuration combination
- [ ] Performance metrics captured (ingestion time, memory usage, query latency)
- [ ] Report generator produces comparison matrix (HTML/Markdown)
- [ ] CI integration for regression testing on key configurations
- [ ] Ground truth dataset created for retrieval evaluation (30+ query-document pairs)

## Technical Notes

### Testing Dimensions

**Dimension 1: LLM Models**
- **Embedding Models** (Ollama):
  - `qwen3-embedding:0.6b` (baseline, 1024-dim)
  - `nomic-embed-text:latest` (768-dim, optimized for retrieval)
  - `mxbai-embed-large:latest` (1024-dim, SOTA performance)

- **Text Generation Models** (for semantic chunking):
  - `gemma3:1b` (current default, good topic detection)
  - `qwen3:0.6b` (lightweight, baseline comparison)
  - `mistral:7b` (higher quality, slower)

**Dimension 2: Chunking Strategies**
- `recursive` - Fixed-size with overlap (baseline)
- `semantic` - LLM-based topic boundaries only
- `hybrid` - Structure-aware + LLM boundaries (recommended)

**Dimension 3: Clustering Algorithms**
- `k-means` - Current implementation, fixed cluster count
- `HDBSCAN` - Density-based, auto-determines cluster count
- `Agglomerative` - Hierarchical clustering for taxonomy

**Dimension 4: Chunk Size Configurations**
- Small: 200 chars, 50 overlap
- Medium: 400 chars, 100 overlap (current default)
- Large: 800 chars, 200 overlap

### Test Matrix Structure

```python
# Total configurations: 3 embedding × 3 generation × 3 chunking × 3 clustering × 3 sizes = 243 combos
# Realistic subset: 18 key configurations for systematic comparison

TEST_MATRIX = [
    # Baseline configurations
    {
        "name": "baseline_current",
        "embedding_model": "qwen3-embedding:0.6b",
        "generation_model": "gemma3:1b",
        "chunking_strategy": "recursive",
        "chunk_size": 400,
        "chunk_overlap": 100,
        "clustering_algorithm": "k-means",
        "n_clusters": 416,
    },

    # Recommended configuration (Story 021)
    {
        "name": "recommended_hybrid",
        "embedding_model": "qwen3-embedding:0.6b",
        "generation_model": "gemma3:1b",
        "chunking_strategy": "hybrid",
        "chunk_size": 400,
        "chunk_overlap": 100,
        "clustering_algorithm": "k-means",
        "n_clusters": 416,
    },

    # High-quality configuration (slower)
    {
        "name": "high_quality",
        "embedding_model": "mxbai-embed-large:latest",
        "generation_model": "mistral:7b",
        "chunking_strategy": "hybrid",
        "chunk_size": 600,
        "chunk_overlap": 150,
        "clustering_algorithm": "HDBSCAN",
    },

    # Performance-optimized (faster)
    {
        "name": "performance_optimized",
        "embedding_model": "nomic-embed-text:latest",
        "generation_model": "qwen3:0.6b",
        "chunking_strategy": "recursive",
        "chunk_size": 300,
        "chunk_overlap": 75,
        "clustering_algorithm": "k-means",
        "n_clusters": 200,
    },

    # ... (14 more systematic variations)
]
```

### Quality Metrics Collected

**Chunking Quality:**
- Avg chunk size (chars)
- Chunk size std deviation
- Topic boundary alignment score (for semantic/hybrid)
- Structure preservation score (Story 020 metric)
- Chunks per document (distribution)

**Embedding Quality:**
- Avg intra-cluster cosine similarity
- Avg inter-cluster cosine similarity
- Silhouette score (clustering quality)
- Vector space coverage (% dimensions used)
- Embedding collapse detection

**Retrieval Quality:**
- Recall@5, Recall@10, Recall@20
- NDCG@5, NDCG@10, NDCG@20
- Mean Reciprocal Rank (MRR)
- Precision@k

**Performance Metrics:**
- Ingestion time (total, per file)
- Embedding generation time
- LLM call time (for semantic chunking)
- Clustering time
- Memory usage (peak, avg)
- Query latency (p50, p95, p99)
- Index size (Weaviate storage)

### Implementation Approach

**New Modules:**

1. `/src/mnemosyne/iris/quality_testing/test_matrix.py`
   - `TestConfiguration` dataclass
   - `TestMatrixRunner` class
   - Configuration loader from YAML/JSON
   - Parallel test execution

2. `/src/mnemosyne/iris/quality_testing/metrics_collector.py`
   - `MetricsCollector` class
   - Real-time metric capture during ingestion
   - Performance profiling integration
   - Memory tracking

3. `/src/mnemosyne/iris/quality_testing/ground_truth.py`
   - `GroundTruthDataset` class
   - Query-document pair loader
   - Relevance scoring (binary or graded)
   - Dataset validation

4. `/src/mnemosyne/iris/quality_testing/report_generator.py`
   - `ComparisonReport` class
   - HTML/Markdown output
   - Interactive charts (plotly/matplotlib)
   - Winner/loser highlighting

5. `/scripts/run_quality_matrix.py`
   - CLI entry point
   - Progress tracking
   - Result caching (avoid re-runs)
   - Report generation

**Modified Modules:**

1. `/src/mnemosyne/aletheia/obsidian_ingestor.py` (+30 lines)
   - Add metrics callback hooks
   - Expose performance counters
   - Optional profiling mode

### Ground Truth Dataset Format

```yaml
# /data/ground_truth/retrieval_queries.yaml
queries:
  - id: Q001
    query: "How do I implement semantic chunking in Python?"
    relevant_documents:
      - path: "notes/development/semantic-chunking-guide.md"
        relevance: 2  # 0=not relevant, 1=somewhat, 2=highly relevant
      - path: "notes/projects/mnemosyne-design.md"
        relevance: 1
    irrelevant_documents:
      - path: "notes/cooking/pasta-recipes.md"

  - id: Q002
    query: "What are the trade-offs between k-means and HDBSCAN clustering?"
    relevant_documents:
      - path: "notes/ml/clustering-comparison.md"
        relevance: 2
      - path: "notes/research/hdbscan-paper-summary.md"
        relevance: 2

  # ... (28 more queries)
```

### CLI Usage

```bash
# Run full test matrix (takes several hours)
python scripts/run_quality_matrix.py \
  --vault /path/to/test_vault \
  --matrix configs/test_matrix.yaml \
  --output reports/quality_matrix_$(date +%Y%m%d).html

# Run specific configuration
python scripts/run_quality_matrix.py \
  --vault /path/to/test_vault \
  --config baseline_current \
  --output reports/baseline.html

# Compare two configurations
python scripts/run_quality_matrix.py \
  --vault /path/to/test_vault \
  --compare baseline_current recommended_hybrid \
  --output reports/comparison.html

# Regression test (run on CI)
python scripts/run_quality_matrix.py \
  --vault /path/to/test_vault \
  --regression \
  --baseline-report reports/baseline.json
```

### Report Example (Markdown)

```markdown
# Quality Testing Matrix Report
Generated: 2025-12-29 18:00:00
Test Vault: /data/test_vault_100_files (100 files, 387KB)

## Summary

| Configuration | Recall@10 | NDCG@10 | Ingestion Time | Avg Chunk Size | Winner |
|---------------|-----------|---------|----------------|----------------|--------|
| baseline_current | 0.68 | 0.72 | 2m 15s | 387 chars | - |
| recommended_hybrid | **0.76** | **0.81** | 18m 42s | 423 chars | 🏆 Quality |
| high_quality | **0.82** | **0.85** | 45m 12s | 612 chars | 🏆 Best Quality |
| performance_optimized | 0.65 | 0.69 | **1m 48s** | 312 chars | 🏆 Speed |

## Detailed Analysis

### Chunking Quality
- **hybrid** strategies show 20% better topic boundary alignment
- **semantic** creates more variable chunk sizes (CV=0.42 vs 0.15 for recursive)
- **recursive** has most consistent performance across vault sizes

### Embedding Quality
- **mxbai-embed-large** shows best cluster separation (silhouette=0.68)
- **qwen3-embedding** adequate for most use cases (silhouette=0.58)
- **nomic-embed-text** fastest but lower separation (silhouette=0.52)

### Retrieval Performance
- **hybrid + mxbai-embed-large** achieves best recall@10 (0.82)
- **LLM-based chunking** improves retrieval by avg 12% vs recursive
- **Larger chunk sizes** (600-800 chars) perform better for complex queries

### Performance Trade-offs
- **Semantic chunking** adds 8-10x ingestion time vs recursive
- **Hybrid approach** good balance (8x slower but +12% quality)
- **LLM model size** has linear impact on chunking time

## Recommendations

1. **For development/testing**: Use `performance_optimized`
   - Fast iteration cycles
   - Adequate quality for most queries

2. **For production**: Use `recommended_hybrid`
   - Best quality/performance balance
   - Runs acceptably on Raspberry Pi 5
   - +12% retrieval improvement

3. **For research/archival**: Use `high_quality`
   - Maximum retrieval quality
   - Acceptable for one-time ingestion
   - Best for large, complex vaults

## Regression Results

| Metric | Baseline | Current | Delta | Status |
|--------|----------|---------|-------|--------|
| Recall@10 | 0.68 | 0.76 | +11.8% | ✅ PASS |
| NDCG@10 | 0.72 | 0.81 | +12.5% | ✅ PASS |
| Ingestion Time | 2m 15s | 18m 42s | +729% | ⚠️ WARN |
| Memory Usage | 245MB | 312MB | +27% | ✅ PASS |

**Verdict**: Quality improvements justify performance cost.
```

### CI Integration

```yaml
# .github/workflows/quality-regression.yml
name: Quality Regression Testing

on:
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 2 * * 0'  # Weekly on Sunday at 2 AM

jobs:
  quality-regression:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Download test vault
        run: |
          # Download standardized test vault (stored in releases or S3)
          wget https://github.com/user/repo/releases/download/v1.0/test_vault_100.tar.gz
          tar -xzf test_vault_100.tar.gz

      - name: Download ground truth dataset
        run: |
          wget https://github.com/user/repo/releases/download/v1.0/ground_truth.yaml

      - name: Start Ollama with required models
        run: |
          docker run -d --name ollama -p 11434:11434 ollama/ollama:latest
          docker exec ollama ollama pull qwen3-embedding:0.6b
          docker exec ollama ollama pull gemma3:1b

      - name: Run regression test
        run: |
          python scripts/run_quality_matrix.py \
            --vault test_vault_100 \
            --config baseline_current recommended_hybrid \
            --regression \
            --baseline-report quality_baselines/v1.0.json \
            --output regression_report.html

      - name: Upload report
        uses: actions/upload-artifact@v4
        with:
          name: quality-regression-report
          path: regression_report.html

      - name: Check regression thresholds
        run: |
          # Fail if quality metrics regressed by >5%
          python scripts/check_regression_thresholds.py \
            --report regression_report.json \
            --max-recall-drop 0.05 \
            --max-ndcg-drop 0.05
```

### Test Data Requirements

**Test Vault Structure:**
- 100 diverse markdown files
- Mix of note types (technical, personal, project, research)
- Varying lengths (100 - 5000 words)
- Different heading structures (flat, nested, complex)
- Real-world content (anonymized user vault or curated dataset)

**Ground Truth Dataset:**
- 30-50 query-document pairs
- Mix of query types (factual, conceptual, multi-hop)
- Graded relevance (0=not relevant, 1=somewhat, 2=highly relevant)
- Coverage across vault topics
- Hand-verified by domain expert

### Dependencies

- Story 019: Quality Assurance Framework (provides metrics infrastructure)
- Story 020: Hierarchical Structure Preservation (structure metrics)
- Story 021: Semantic Chunking with LLM (chunking strategies)
- Story 001: Cluster Centroid Node (clustering algorithms)

**External Dependencies:**
- Ollama with multiple models installed
- Weaviate for vector storage
- NumPy/SciPy for metric calculations
- Plotly or Matplotlib for visualization
- YAML/JSON config parsing
- Memory profiler (memory_profiler or tracemalloc)

## Affected Components

- **Iris**: Primary implementation location (quality testing infrastructure)
- **Aletheia**: Metrics collection hooks during ingestion
- **Alexandria**: Test data storage and retrieval
- **CLI**: Test matrix runner and report generation

## Priority

**Medium-High** - Non-functional but critical for data-driven optimization

## Estimate

13 story points (8-10 days)
- Test matrix infrastructure: 3 days
- Ground truth dataset creation: 2 days
- Metrics collection hooks: 1 day
- Report generation: 2 days
- CI integration: 1 day
- Documentation and validation: 1-2 days

## Linear Labels

`phase-1`, `non-functional`, `quality-testing`, `iris`, `benchmarking`, `performance`

## Related Stories

- Story 019: Quality Assurance Framework (provides base metrics)
- Story 020: Hierarchical Structure Preservation (structure quality)
- Story 021: Semantic Chunking with LLM (chunking strategies to test)
- Story 001: Cluster Centroid Node (clustering algorithms to test)

## Risks and Mitigations

**Risk 1: Test matrix too large (243 configurations)**
- Mitigation: Focus on 15-20 key configurations covering main trade-offs
- Fallback: Parallel execution on multiple machines/containers
- Learning: Document which dimensions have biggest impact

**Risk 2: Test vault not representative of real usage**
- Mitigation: Use real anonymized user vault + synthetic supplements
- Fallback: Crowdsource test vaults from community
- Validation: Validate results against production metrics

**Risk 3: Ground truth dataset subjective/biased**
- Mitigation: Multi-rater agreement for query-document pairs
- Fallback: Use standard IR datasets (MS MARCO, BEIR) adapted to notes
- Validation: Measure inter-rater reliability (Cohen's kappa)

**Risk 4: CI runtime too long for full matrix**
- Mitigation: Run only critical configurations on PR, full matrix weekly
- Fallback: Cache results, only re-run changed configurations
- Threshold: If regression test >20 min, reduce scope

## Future Enhancements (Not in Scope)

- A/B testing framework for production deployment
- Automatic hyperparameter tuning (grid search, Bayesian optimization)
- Multi-language support (test with non-English vaults)
- Real-time quality monitoring dashboard
- User-specific configuration recommendations
- Cost analysis (compute time × energy cost)
- Carbon footprint tracking for LLM calls

## Success Metrics

- [ ] Test matrix runs successfully on 100-file vault
- [ ] All 18 key configurations complete within 8 hours
- [ ] Quality report clearly identifies winner configurations
- [ ] Regression test catches >5% quality drops
- [ ] Ground truth dataset has inter-rater agreement >0.7 (Cohen's kappa)
- [ ] Report is actionable (clear recommendations)
- [ ] CI integration runs weekly without manual intervention
