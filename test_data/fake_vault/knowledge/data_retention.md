---
title: Data Retention
tags: [retention, cleanup]
created: 2024-02-11
---

# Data Retention

## Policy
- Remove stale chunks when a file is re-ingested.
- Keep checkpoints for 30 days unless explicitly deleted.

## Rationale
Retention avoids stale search results and keeps the index consistent.

## Links
- [[pipeline_test_plan]]
- [[project_alpha]]
