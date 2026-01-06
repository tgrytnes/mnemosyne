---
title: Pipeline Test Plan
tags: [test, e2e]
created: 2024-02-09
---

# Pipeline Test Plan

## Acceptance Criteria
- Ingestion completes without errors.
- Weaviate stores expected vector lengths.
- Checkpoint resume returns the latest state.

## Scenarios
1. Ingest a small vault and validate chunk counts.
2. Resume a saved query from a checkpoint database.
3. Query Weaviate using a mixed-topic prompt.

## Notes
Keep the dataset realistic but small enough for CI.
