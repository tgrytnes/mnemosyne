# Machine Learning Experiments

## Current Experiments

### Experiment 1: Local LLM Fine-tuning

**Goal**: Fine-tune qwen3:0.6b on personal writing style for better note summarization.

**Dataset**:
- 200+ markdown notes
- Remove private information
- Format as instruction-following pairs

**Approach**:
```bash
# Using Ollama's fine-tuning (when available)
ollama create personal-summarizer \
  --modelfile Modelfile \
  --dataset notes_dataset.jsonl
```

**Status**: Blocked - Ollama doesn't support fine-tuning yet. Might need to use Hugging Face Transformers directly.

### Experiment 2: Semantic Chunking Quality

**Goal**: Measure if LLM-based semantic chunking improves retrieval vs fixed-size chunks.

**Metrics**:
- Recall@5, Recall@10
- NDCG (Normalized Discounted Cumulative Gain)
- Semantic coherence (intra-chunk similarity)

**Baseline**: RecursiveCharacterTextSplitter (400 chars, 100 overlap)

**Hypothesis**: Semantic chunking should improve recall by 10-15% because chunks respect topic boundaries.

### Experiment 3: Cluster Quality Analysis

**Goal**: Understand if k-means clustering on embeddings produces meaningful topic groups.

**Approach**:
1. Embed all notes with qwen3-embedding
2. Run MiniBatchKMeans (k=30 clusters)
3. Manually inspect 5 notes from each cluster
4. Calculate silhouette score (cluster tightness)

**Expected**: Silhouette score >0.3 = decent clustering

## Resources

- [Chunking Strategies Paper](https://arxiv.org/fake-url)
- [LangChain Text Splitters Docs](https://langchain.com/docs)
- scikit-learn clustering: `sklearn.cluster.MiniBatchKMeans`

#machine-learning #experiments #nlp
