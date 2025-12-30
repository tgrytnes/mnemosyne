# End-to-End Pipeline Test Suite

## Overview

These E2E tests validate the **complete data flow** across multiple stories, ensuring all components work together correctly.

## Test Files

### 1. `test_complete_pipeline_e2e.py` ✅ READY TO RUN

**Stories Covered:**
- Story 000: Obsidian Vault Ingestion
- Story 001: Cluster Centroid Node
- Story 019: Quality Assurance Framework
- Story 020: Hierarchical Structure Preservation
- Story 021: Semantic Chunking with LLM

**Pipeline Flow Tested:**
```
Raw Vault → Clean → Chunk → Embed → Store → Cluster → Query Representatives
```

**Test Classes:**

#### `TestCompleteEndToEndPipeline`
Complete integration tests across all merged stories.

**Tests:**
1. **`test_pipeline_00_vault_to_cluster_representatives`** 🏆 **GOLDEN PATH TEST**
   - **What it does:** Validates the entire pipeline from raw vault to cluster representatives
   - **Creates:** 4 diverse markdown files (ML, PM, Cooking, Mixed content)
   - **Validates:**
     - All files ingested correctly
     - Chunks stored in Weaviate with proper metadata
     - Clustering creates correct number of clusters
     - Centroids stored properly
     - LangGraph node returns valid representatives
     - Representatives ordered by distance from centroid
   - **Real services:** Weaviate + Ollama
   - **Expected runtime:** ~2-3 minutes

2. **`test_pipeline_01_chunking_strategy_comparison`**
   - **What it does:** A/B test between recursive and hybrid chunking strategies
   - **Creates:** Highly structured document with nested headings
   - **Validates:**
     - Both strategies ingest same content
     - Hybrid preserves structure better (Story 020)
     - Quality metrics differ between strategies
   - **Real services:** Weaviate + Ollama
   - **Expected runtime:** ~3-5 minutes (runs ingestion twice)

3. **`test_pipeline_02_incremental_update_propagation`**
   - **What it does:** Tests incremental ingestion and cluster updates
   - **Flow:**
     1. Initial ingestion
     2. Cluster chunks
     3. Modify file content
     4. Re-ingest (only changed file)
     5. Verify old chunks removed, new chunks added
     6. Re-cluster
   - **Validates:**
     - State tracking works correctly
     - Chunks updated in Weaviate
     - Cluster assignments updated
   - **Real services:** Weaviate + Ollama
   - **Expected runtime:** ~2 minutes

4. **`test_pipeline_03_quality_metrics_end_to_end`**
   - **What it does:** Validates quality metrics collection (Story 019)
   - **Creates:** Diverse content (technical + creative)
   - **Validates:**
     - Chunking quality metrics
     - Embedding quality metrics
     - Structure preservation scores
     - No embedding collapse detected
   - **Real services:** Weaviate + Ollama
   - **Expected runtime:** ~2 minutes

5. **`test_pipeline_04_heading_based_retrieval`**
   - **What it does:** Tests heading-based queries end-to-end (Story 020)
   - **Creates:** Multi-section knowledge base document
   - **Validates:**
     - Heading paths stored correctly
     - Can query chunks by heading
     - Nested headings work
     - Heading levels preserved
   - **Real services:** Weaviate + Ollama
   - **Expected runtime:** ~1-2 minutes

6. **`test_pipeline_05_cluster_semantic_coherence`**
   - **What it does:** Validates clusters are semantically meaningful
   - **Creates:** 5 files with 3 distinct topics (ML, Cooking, History)
   - **Validates:**
     - Clustering groups related content
     - Representatives reflect cluster topics
     - At least 2 distinct topics identified
   - **Real services:** Weaviate + Ollama
   - **Expected runtime:** ~2-3 minutes

#### `TestPipelineEdgeCases`
Edge case and error handling tests.

**Tests:**
1. **`test_empty_vault_handling`** - Graceful handling of empty vault
2. **`test_single_file_single_chunk`** - Minimal content edge case
3. **`test_very_long_document`** - Large document with 50+ sections

---

### 2. `test_pipeline_with_metadata_synthesis_e2e.py` ⚠️ REQUIRES STORY 002

**Stories Covered:**
- All from `test_complete_pipeline_e2e.py` +
- Story 002: Structured Metadata Synthesis (LLM-generated cluster profiles)

**Pipeline Flow Tested:**
```
Raw Vault → Clean → Chunk → Embed → Store → Cluster → Representatives → LLM Synthesis → PostgreSQL
```

**Prerequisites:**
- Story 002 must be merged
- PostgreSQL connection required
- Tests automatically skip if Story 002 not available

**Test Classes:**

#### `TestCompletePipelineWithMetadataSynthesis`

**Tests:**
1. **`test_pipeline_full_vault_to_cluster_profiles`** 🏆 **ULTIMATE E2E TEST**
   - **What it does:** Complete pipeline from vault to stored cluster profiles
   - **Creates:** 6 realistic files across 3 domains (ML, PM, Cooking)
   - **Flow:**
     1. Ingest with hybrid chunking
     2. Cluster into 3 semantic groups
     3. Get representatives for each cluster
     4. Synthesize cluster metadata with REAL LLM
     5. Store profiles in PostgreSQL
     6. Validate profile quality and semantic coherence
   - **Validates:**
     - Full data flow works end-to-end
     - LLM generates meaningful themes
     - Key entities identified
     - Confidence scores reasonable
     - Profiles stored and retrievable from PostgreSQL
     - Semantic topics correctly identified
   - **Real services:** Weaviate + Ollama + PostgreSQL
   - **Expected runtime:** ~5-8 minutes (LLM synthesis is slower)

2. **`test_pipeline_metadata_synthesis_quality_validation`**
   - **What it does:** Validates synthesized metadata quality with ground truth
   - **Creates:** 6 coherent single-topic documents (3 Python, 3 Mediterranean food)
   - **Validates:**
     - LLM correctly identifies topics
     - Themes match expected content
     - Key entities are relevant
     - Confidence scores correlate with cluster quality
   - **Real services:** Weaviate + Ollama + PostgreSQL
   - **Expected runtime:** ~3-4 minutes

3. **`test_pipeline_handles_mixed_quality_clusters`**
   - **What it does:** Tests robustness with both good and bad clusters
   - **Creates:** Mix of coherent and scattered content
   - **Validates:**
     - System handles low-quality clusters gracefully
     - Doesn't crash on poor data
     - Successfully synthesizes at least some profiles
   - **Real services:** Weaviate + Ollama + PostgreSQL
   - **Expected runtime:** ~3-4 minutes

---

## Running the Tests

### Prerequisites

1. **Start required services:**
   ```bash
   docker-compose up weaviate postgres ollama -d

   # Pull required models
   docker exec ollama ollama pull qwen3-embedding:0.6b
   docker exec ollama ollama pull gemma3:1b  # For semantic chunking
   ```

2. **Install dependencies:**
   ```bash
   poetry install --with dev
   ```

### Run Current Implementation Tests

These tests work with the currently merged stories (000, 001, 019, 020, 021):

```bash
# Run all current E2E tests
pytest tests/e2e/test_complete_pipeline_e2e.py -v

# Run specific test
pytest tests/e2e/test_complete_pipeline_e2e.py::TestCompleteEndToEndPipeline::test_pipeline_00_vault_to_cluster_representatives -v

# Run with coverage
pytest tests/e2e/test_complete_pipeline_e2e.py --cov=src/mnemosyne --cov-report=html
```

### Run After Story 002 Merge

Once Story 002 is merged:

```bash
# Run advanced tests with metadata synthesis
pytest tests/e2e/test_pipeline_with_metadata_synthesis_e2e.py -v

# Run ALL E2E tests (both files)
pytest tests/e2e/ -v -m e2e
```

---

## What These Tests Validate

### ✅ Data Flow Integrity
- Data correctly transformed at each stage
- No data loss or corruption at boundaries
- Metadata preserved throughout pipeline

### ✅ Component Integration
- ObsidianIngestor → Weaviate storage
- Weaviate → ClusterManager
- ClusterManager → GetClusterRepresentatives (LangGraph)
- Representatives → ClusterMetadataSynthesizer (Story 002)
- Profiles → PostgreSQL (Story 002)

### ✅ Quality Metrics
- Chunking quality meets thresholds
- Embedding quality verified
- Structure preservation >95%
- No embedding collapse

### ✅ Semantic Coherence
- Clusters group related content
- Representatives are actually representative
- Synthesized themes match content

### ✅ State Management
- Incremental updates work correctly
- State persists across runs
- Changed files detected

### ✅ Edge Cases
- Empty vaults handled gracefully
- Single-chunk files work
- Very long documents processed correctly

---

## Test Design Philosophy

### 1. **Use REAL Data**
- No synthetic "perfect" test data
- Realistic markdown with actual structure
- Diverse content types (technical, creative, mixed)

### 2. **Use REAL Services**
- Actual Weaviate vector database
- Actual Ollama LLM for embeddings and synthesis
- Actual PostgreSQL for profile storage
- NO MOCKS in E2E tests

### 3. **Test COMPLETE Flows**
- End-to-end pipelines, not isolated components
- Validate data transformations at boundaries
- Test integration points between stories

### 4. **Validate QUALITY, Not Just Success**
- Check output is meaningful, not just non-empty
- Verify semantic coherence
- Validate metrics meet thresholds

### 5. **Test Edge Cases**
- Empty vaults
- Minimal content
- Very large documents
- Mixed-quality clusters
- Scattered random content

---

## Expected Test Results

### Current Implementation (Stories 000, 001, 019, 020, 021)

**All 9 tests should PASS:**
- ✅ `test_pipeline_00_vault_to_cluster_representatives` (GOLDEN PATH)
- ✅ `test_pipeline_01_chunking_strategy_comparison`
- ✅ `test_pipeline_02_incremental_update_propagation`
- ✅ `test_pipeline_03_quality_metrics_end_to_end`
- ✅ `test_pipeline_04_heading_based_retrieval`
- ✅ `test_pipeline_05_cluster_semantic_coherence`
- ✅ `test_empty_vault_handling`
- ✅ `test_single_file_single_chunk`
- ✅ `test_very_long_document`

**Estimated total runtime:** ~15-20 minutes

### After Story 002 Merge

**Additional 3 tests should PASS:**
- ✅ `test_pipeline_full_vault_to_cluster_profiles` (ULTIMATE TEST)
- ✅ `test_pipeline_metadata_synthesis_quality_validation`
- ✅ `test_pipeline_handles_mixed_quality_clusters`

**Estimated total runtime:** ~25-30 minutes (all tests)

---

## Debugging Failed Tests

### Common Issues

**1. Weaviate Connection Failed**
```bash
# Check Weaviate is running
curl http://localhost:8080/v1/.well-known/ready

# View logs
docker-compose logs weaviate

# Restart
docker-compose restart weaviate
```

**2. Ollama Model Not Found**
```bash
# Pull required models
docker exec ollama ollama pull qwen3-embedding:0.6b
docker exec ollama ollama pull gemma3:1b

# Check models available
docker exec ollama ollama list
```

**3. PostgreSQL Connection Failed (Story 002 tests)**
```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Test connection
psql -h localhost -U postgres -d ananke_test

# Restart
docker-compose restart postgres
```

**4. Test Timeouts**
- Increase Ollama timeout in `conftest.py`
- Check system resources (CPU, memory)
- Ensure no other processes using Ollama

**5. Clustering Fails with Empty Collection**
- Verify chunks actually stored in Weaviate
- Check ingestion stats: `stats['total_chunks'] > 0`
- Ensure test vault files created correctly

---

## Adding New E2E Tests

When implementing new stories, add E2E tests that:

1. **Test the new story in isolation** (e.g., `test_story_XXX_e2e.py`)
2. **Test integration with existing pipeline** (add to `test_complete_pipeline_e2e.py`)
3. **Update this README** with new test descriptions

### Template for New E2E Test

```python
@pytest.mark.e2e
@pytest.mark.weaviate  # Add required service markers
def test_pipeline_new_feature(
    weaviate_client,
    clean_weaviate_collection,
    test_config
):
    """
    PIPELINE TEST: <Description>

    Tests Stories: <Story numbers>

    Flow:
    1. <Step 1>
    2. <Step 2>
    ...

    Validates:
    - <What you're validating>
    """
    # Setup
    ollama_client = ollama.Client(...)

    # Create realistic test data
    with tempfile.TemporaryDirectory() as tmp_dir:
        ...

    # Run pipeline stages
    # STAGE 1: ...
    # STAGE 2: ...

    # Validate at each stage
    assert ...
```

---

## CI Integration

These tests run in GitHub Actions CI:

```yaml
# .github/workflows/test.yml

e2e-tests:
  runs-on: ubuntu-latest
  services:
    weaviate: ...
    postgres: ...
    ollama: ...
  steps:
    - name: Run E2E tests
      run: |
        pytest tests/e2e/test_complete_pipeline_e2e.py -v --tb=short
```

**Current tests:** Run on every PR to `main`
**Story 002 tests:** Will run after merge

---

## Success Criteria

✅ **All current E2E tests pass** (9 tests)
✅ **Tests run in <20 minutes** on CI
✅ **No flaky tests** (consistent pass rate >99%)
✅ **Code coverage** >90% for pipeline code
✅ **Real services used** (no mocks in E2E)

---

## Related Documentation

- [Main Test README](../README.md)
- [Story Index](../../user-stories/STORY_INDEX.md)
- [Story 000: Vault Ingestion](../../user-stories/phase-0-ingestion-hygiene/story-000-obsidian-vault-ingestion.md)
- [Story 001: Cluster Centroids](../../user-stories/phase-1-semantic-extraction/story-001-cluster-centroid-node.md)
- [Story 002: Metadata Synthesis](../../user-stories/phase-1-semantic-extraction/story-002-structured-metadata-synthesis.md)
- [Story 019: Quality Framework](../../user-stories/phase-1-semantic-extraction/story-019-quality-assurance-framework.md)
- [Story 020: Structure Preservation](../../user-stories/phase-1-semantic-extraction/story-020-hierarchical-structure-preservation.md)
- [Story 021: Semantic Chunking](../../user-stories/phase-1-semantic-extraction/story-021-semantic-chunking-llm.md)
