---
title: Retrieval Metrics
tags: [metrics, evaluation]
created: 2024-02-06
---

# Retrieval Metrics

## Definitions
- Recall@k: proportion of relevant chunks returned in the top-k results.
- NDCG@k: ranking quality that discounts lower positions.
- Latency: end-to-end retrieval time per query.

## Baseline Targets
| Metric | Target | Notes |
| --- | --- | --- |
| Recall@5 | 0.70 | Synthetic queries |
| NDCG@5 | 0.60 | Human-labeled set |
| Latency (ms) | 800 | Local CI budget |

## Observations
- Chunk overlap can improve recall but increases storage cost.
- Retrieval should be tested with mixed-topic queries.

## Links
- [[semantic_chunking]]
- [[project_alpha]]
