# Story 006: Semantic Chunking with LLM

**As a** developer
**I want** LLM-based semantic boundary detection for chunking
**So that** chunks preserve topic boundaries and improve retrieval quality

## Acceptance Criteria
- [ ] Can switch chunking strategies via config (`CHUNKING_STRATEGY` env var)
- [ ] Semantic chunking preserves topic boundaries (measured via Story 004 metrics)
- [ ] Retrieval quality improves vs baseline (higher recall@k, NDCG)
- [ ] Performance acceptable (~30 min for 100 files with hybrid strategy)
- [ ] A/B test results comparing all strategies (recursive, semantic, hybrid)
- [ ] Hybrid strategy (recommended) uses heading structure + LLM detection
- [ ] Fallback to recursive chunking if LLM fails/timeouts
- [ ] Caching of LLM decisions in ingestion state DB

## Technical Notes

### Implementation Approach

**New Modules:**
1. `/src/mnemosyne/aletheia/semantic_chunker.py` (350 lines)
   - `SemanticChunker` class
   - LLM-based topic boundary detection
   - Variable chunk sizes (100-1000 chars)

2. `/src/mnemosyne/aletheia/hybrid_chunker.py` (250 lines) **RECOMMENDED**
   - Uses heading structure (Story 005) as primary splits
   - LLM semantic detection within sections
   - Fallback to fixed-size if LLM fails
   - Best balance of quality and performance

3. `/src/mnemosyne/aletheia/chunking_strategy_factory.py` (100 lines)
   - Strategy pattern factory
   - Creates chunker based on config
   - Supported strategies: recursive, semantic, hybrid

4. `/scripts/compare_chunking_strategies.py` (200 lines)
   - A/B testing framework
   - Compares all strategies using Story 004 metrics
   - Generates comparison report

**Modified Modules:**
1. `/src/mnemosyne/aletheia/obsidian_ingestor.py` (+50 lines)
   - Configurable chunking strategy
   - Default: recursive (backward compat)
   - Config: `CHUNKING_STRATEGY=recursive|semantic|hybrid`

### Chunking Strategies

**Strategy A: Semantic Chunking**
```python
class SemanticChunker:
    def chunk_text(self, text: str) -> List[TextChunk]:
        # Use LLM to identify topic boundaries
        prompt = f"""
        Identify where topics change in this text.
        Return line numbers where topics shift.

        Text:
        {text}

        Output format (JSON):
        {{"boundaries": [10, 25, 42]}}
        """

        response = ollama.generate(
            model="qwen3:0.6b",
            prompt=prompt,
            format="json",
            options={"temperature": 0.2}
        )

        boundaries = json.loads(response['response'])['boundaries']
        chunks = self._split_at_boundaries(text, boundaries)
        return chunks
```

**Strategy B: Hybrid Chunking (RECOMMENDED)**
```python
class HybridChunker:
    def __init__(self, semantic_chunker, structure_extractor):
        self.semantic_chunker = semantic_chunker
        self.structure_extractor = structure_extractor

    def chunk_text(self, text: str, structure: DocumentStructure) -> List[TextChunk]:
        chunks = []

        # 1. Split at heading boundaries (from Story 005)
        for section in structure.sections:
            section_text = text[section.start_pos:section.end_pos]

            # 2. Use semantic chunker within each section
            if len(section_text) > 1000:  # Large sections
                sub_chunks = self.semantic_chunker.chunk_text(section_text)
            else:  # Small sections
                sub_chunks = [TextChunk(text=section_text, index=0)]

            # 3. Attach heading metadata
            for chunk in sub_chunks:
                chunk.heading_path = section.heading_path
                chunk.heading_level = section.level
                chunks.append(chunk)

        return chunks
```

### Configuration

```bash
# .env
CHUNKING_STRATEGY=hybrid  # recursive|semantic|hybrid

# For semantic/hybrid
SEMANTIC_MIN_CHUNK_SIZE=100
SEMANTIC_MAX_CHUNK_SIZE=1000
SEMANTIC_LLM_TEMP=0.2
```

### Performance Optimization

- Cache LLM decisions in ingestion state DB
- Batch LLM calls (process 5 sections at once)
- Skip LLM for short documents (<500 chars)
- Fallback to recursive if LLM fails/timeouts
- Progressive timeout strategy (5s per section, max 30s total)

### A/B Testing Framework

```bash
# Compare all strategies
python scripts/compare_chunking_strategies.py --vault test_vault --output comparison.html

# Output:
# Strategy       | Recall@10 | NDCG@10 | Avg Chunk | Ingestion Time
# ---------------|-----------|---------|-----------|---------------
# recursive      | 0.68      | 0.72    | 387       | 2 min
# semantic       | 0.74      | 0.78    | 456       | 28 min
# hybrid         | 0.76      | 0.81    | 423       | 18 min  ← Winner
```

### Expected Quality Improvements

**Baseline (Recursive):**
- Recall@10: 0.68
- NDCG@10: 0.72
- Semantic coherence: 0.65

**Target (Hybrid):**
- Recall@10: 0.76 (+12% improvement)
- NDCG@10: 0.81 (+13% improvement)
- Semantic coherence: 0.78 (+20% improvement)

### Dependencies
- Ollama (qwen3:0.6b model)
- Story 004 (Quality Assurance Framework for validation)
- Story 005 (Hierarchical Structure for hybrid approach)
- Existing chunking infrastructure (Story 000)

### Data Flow

```
Markdown File → [Structure Extractor] (Story 005)
                        ↓
                Document Structure
                        ↓
            [Chunking Strategy Factory]
                        ↓
        (recursive | semantic | hybrid)
                        ↓
                   Text Chunks
```

## Affected Components
- **Aletheia**: Primary implementation location (input processing)
- **Iris**: Quality metrics for A/B testing
- **CLI**: New chunking strategy configuration

## Priority
**High** - State-of-the-art chunking quality

## Estimate
13 story points (8-10 days)

## Linear Labels
`phase-1`, `semantic-chunking`, `llm-integration`, `aletheia`, `advanced-feature`

## Related Stories
- Story 000: Obsidian Vault Ingestion (extends this pipeline)
- Story 004: Quality Assurance Framework (validates improvements)
- Story 005: Hierarchical Structure Preservation (hybrid strategy dependency)
- Story 001-003: Clustering (benefits from better chunk quality)

## Risks and Mitigations

**Risk 1: LLM-based chunking too slow**
- Mitigation: Implement caching, batch processing, skip for small docs
- Fallback: Use recursive chunking if timeout/failure
- Threshold: If >45 min for 100 files, optimize or abandon strategy

**Risk 2: Semantic chunking doesn't improve quality**
- Mitigation: A/B test reveals this early (Story 004 metrics)
- Fallback: Keep recursive as default, make semantic opt-in
- Learning: Document why it didn't work for future reference

**Risk 3: LLM boundary detection unreliable**
- Mitigation: Hybrid approach uses structural hints (headings) first
- Fallback: Section-level recursive chunking
- Validation: Story 004 boundary quality metric

## Future Enhancements (Not in Scope)

- Late chunking (embed full doc, chunk afterward)
- Agentic chunking (LLM decides boundaries with reasoning)
- Custom LLM model support (beyond Qwen3)
- Chunk size optimization based on content density
- Cross-document chunking patterns
