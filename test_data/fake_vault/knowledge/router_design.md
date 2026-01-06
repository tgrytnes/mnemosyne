---
title: Router Design Notes
tags: [routing, design]
created: 2024-02-07
---

# Router Design Notes

## Intent
Route queries to the best source (cache, weaviate, or web) based on similarity.

## Heuristics
- If the cache similarity is above the threshold, return cached results.
- If no cache hit, prefer Weaviate for vault content.
- Web retrieval is the fallback when the query looks external.

## Open Questions
- Should we store routing decisions for audit and debugging?
- Do we allow mixed routes for a single query?

## Links
- [[embedding_models]]
- [[semantic_chunking]]
