# Story 029: Discovery Identity Standardization (Change Request)

**As a** system maintainer
**I want** stable, deterministic discovery identifiers across Scout, Monitor, Gatekeeper, and Console
**So that** discoveries, proposals, and projects stay linked and deduplicated over time

## 🎯 Architectural Role

**This story standardizes discovery identity across the latent-scout pipeline.**

It retrofits identity rules for existing discovery records and ensures new data uses a
single canonical identifier (`discovery_id`) that is stable across runs, storage layers,
and downstream agents.

## Acceptance Criteria
- [ ] Canonical fields exist on every discovery record: `discovery_job_key`, `candidate_key`, `discovery_id`
- [ ] Canonical rule is enforced: `discovery_id = {discovery_job_key}:{candidate_key}`
- [ ] `discovery_job_key` is required and set from the scout job config (e.g., `private_projects`)
- [ ] `candidate_key` is a deterministic slug derived from the discovery label (e.g., `house_painting`)
- [ ] Scout writes the canonical fields for all new discoveries in Weaviate
- [ ] Deduplication uses `discovery_id` as the primary uniqueness key
- [ ] Migration/backfill updates existing discoveries missing the canonical fields
- [ ] Conflicts (same `discovery_id` with different content) are logged and skipped (no overwrite)
- [ ] SQLite proposal queue stores `discovery_id` and rejects records without it
- [ ] SQL Project Gatekeeper writes `discovery_id` into The Ananke projects table
- [ ] CLI validation command reports missing or duplicate discovery identities
- [ ] Integration test covers backfill on a real Weaviate collection
- [ ] E2E test runs Scout twice on the same dataset and verifies stable `discovery_id` with no duplicates

## Technical Notes

### Canonical Identity Rules
- `discovery_job_key`: stable identifier for the scout job/concept
- `candidate_key`: deterministic slug for the discovery label
- `discovery_id`: `{discovery_job_key}:{candidate_key}` (primary identity)

### Backfill Strategy
1) Fetch discoveries missing any canonical field.
2) Derive `discovery_job_key` from stored job metadata or a default job mapping.
3) Derive `candidate_key` from the discovery title/label using the slug rules.
4) Write back the fields without mutating other properties.
5) Log conflicts and leave them untouched for manual review.

### CLI Validation
- `mnemosyne discovery validate-identities`
  - reports missing fields
  - reports collisions
  - outputs a JSON report for audit

## Dependencies
- Story 010: Autonomous Pattern Detection (Scout writes discoveries)
- Story 015: Monitor Agent (proposal queue)
- Story 014: SQL Project Gatekeeper (writes projects)
- Story 028: Scout Management Console (displays discovery identity)

## Affected Components
- **Argus**: Scout discovery emission, identity derivation
- **Alexandria**: Weaviate Discoveries, SQLite queue, The Ananke projects
- **Hermes**: Console displays identity metadata

## Priority
**Medium** - Required for long-term data integrity

## Estimate
5 story points (3-4 days)

## Linear Labels
`phase-4`, `latent-scout`, `data-integrity`, `migration`

## Related Stories
- Story 010: Autonomous Pattern Detection
- Story 015: Monitor Agent (Proposal Queue)
- Story 028: Scout Management Console
- Story 014: SQL Project Gatekeeper
