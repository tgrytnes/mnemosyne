# CR-000-005: E2E Ingestion Progress Logging & Reduced Test Load

**As a** developer  
**I want** progress logs during long-running ingestion tests and a smaller default load  
**So that** I can see real-time progress on the Pi and avoid multi-hour runs without feedback

## Context
- E2E performance tests (hybrid semantic chunking) can run 30+ minutes on a Raspberry Pi.
- Current logs are sparse, making it hard to see that work is progressing.

## Acceptance Criteria
- [ ] Obsidian ingestion logs progress every N files when enabled (default off).
- [ ] Progress log includes: processed count, total, elapsed time, and ETA.
- [ ] Logging frequency is configurable via env var `INGEST_PROGRESS_EVERY` (0 disables).
- [ ] E2E hybrid ingestion performance test default file count is reduced to 50.
- [ ] File count and time limit are configurable via env vars.

## Test Plan (TDD)
**Unit**
- [ ] `ObsidianIngestor.ingest_vault` emits progress logs when `INGEST_PROGRESS_EVERY` is set.

**E2E**
- [ ] Hybrid ingestion performance test uses the reduced default count and still completes.

## Affected Components
- `mnemosyne.aletheia.obsidian_ingestor`
- `tests/e2e/test_chunking_performance_e2e.py`

## Priority
High

## Estimate
1–2 pts
