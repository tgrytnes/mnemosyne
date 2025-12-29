---
title: Semantic Chunking Overview
tags: [chunking, retrieval]
---

# Semantic Chunking Overview

Semantic chunking splits text on topic boundaries.

## Topic A: Embeddings
Embeddings convert text into vectors. The model should be stable across runs.

### Notes
Vector length should match the schema.

## Topic B: Retrieval
Retrieval uses similarity search in Weaviate.

### Notes
Recall@k and NDCG are computed on a fixed query set.

## Topic C: Evaluation
Evaluation compares chunking strategies on the same corpus.
