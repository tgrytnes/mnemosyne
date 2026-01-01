# Story 028: Scout Management Console

**As a** knowledge worker
**I want** a lightweight GUI to define Scout concepts and run the latent scanner
**So that** I can control what the Scout looks for and validate discoveries before they persist

## 🎯 Architectural Role

**This story introduces a local management console for Scout configuration and runs.**

It provides a minimal web UI to create and tune radar vectors (positive/negative prototypes),
launch dry-run or persistent Scout scans, and review run results without relying on Telegram.

## Acceptance Criteria
- [ ] Local web UI is available (FastAPI + HTML is acceptable; no SPA required)
- [ ] Users can create, edit, enable/disable, and delete Scout concept sets
- [ ] Concept set fields include: key, description, positives, negatives, threshold
- [ ] Concept key is a stable `discovery_job_key` (slug; used to build discovery IDs)
- [ ] Validations: at least 2 positives and 1 negative, threshold in [0, 1]
- [ ] Users can select a subset of concepts to run
- [ ] Users can run Scout in dry-run or persist mode
- [ ] Run history is listed with run_id, time, counts, errors, and duration
- [ ] Users can view discoveries by run_id and pattern_type
- [ ] Discoveries shown in the console include `discovery_id` ({job}:{candidate})
- [ ] UI exposes a "preview score" action for a concept against a sample cluster text
- [ ] No Telegram integration in this story (local-only console)
- [ ] Configuration and run metadata are persisted in SQLite
- [ ] E2E test covers: create concept -> run dry-run -> view results in console API

## Technical Notes

### SQLite Schema (Concept Store)

```sql
CREATE TABLE IF NOT EXISTS scout_concepts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  key TEXT UNIQUE NOT NULL, -- discovery_job_key
  description TEXT,
  positives_json TEXT NOT NULL,
  negatives_json TEXT NOT NULL,
  threshold REAL NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);
```

### SQLite Schema (Run History)

```sql
CREATE TABLE IF NOT EXISTS scout_runs (
  run_id TEXT PRIMARY KEY,
  started_at TIMESTAMP,
  duration_seconds REAL,
  dry_run INTEGER NOT NULL,
  clusters_analyzed INTEGER,
  detections_json TEXT,
  errors_json TEXT
);
```

### Discovery Identity
- `discovery_job_key` is the concept key defined in the console (slug).
- `candidate_key` is a slug derived from the discovery label.
- `discovery_id = {discovery_job_key}:{candidate_key}` and should be displayed in the UI.

### Minimal API Surface

```python
# GET /scout/concepts
# POST /scout/concepts
# PUT /scout/concepts/{key}
# DELETE /scout/concepts/{key}

# POST /scout/run {dry_run: bool, concepts: [keys]}
# GET /scout/runs
# GET /scout/runs/{run_id}
# GET /scout/discoveries?run_id=...&pattern_type=...

# POST /scout/preview {concept_key: ..., text: ...}
```

### Console UX (Minimal)

- Concepts list with enable/disable toggle
- Detail/edit form for prototypes and threshold
- Run panel with dry-run toggle and concept multi-select
- Run history table with status badge
- Discoveries list filtered by run_id

### Dependencies

- Story 010 (Autonomous Pattern Detection)
- Story 027 (Message Outbox Relay) optional for later; not required here
