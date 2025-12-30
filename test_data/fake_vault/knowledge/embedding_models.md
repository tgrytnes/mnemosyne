---
title: Embedding Models
aliases: [Embeddings]
tags: [embedding, models]
created: 2024-02-05
---

# Embedding Models

## Summary
We use lightweight embedding models in CI and local runs to keep tests fast.

## Candidates
- qwen3-embedding:0.6b is used for embeddings in the pipeline.
- gemma3:1b is used for text generation when semantic chunking needs LLM support.

## Notes
- Vector length should match the Weaviate schema (expected: 1024).
- When upgrading models, update the test data seed and verify metrics.

## Links
- [[weaviate_schema]]
- [[semantic_chunking]]
- [[retrieval_metrics]]
