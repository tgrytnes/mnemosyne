# HF-003: Graph Taxonomy Bootstrap Runtime Dependencies

**As a** Platform Operator  
**I want** the graph taxonomy bootstrap to run in dev without missing runtime deps  
**So that** cluster profiles are synthesized and stored before taxonomy runs.

## Context
- The dev scheduler/container crash-looped due to missing `apscheduler`.
- `cluster_profiles` exists but remains empty, blocking taxonomy bootstrap.
- This hotfix ensures runtime dependencies and bootstrap flow execute in dev.

## Excellent Acceptance Criteria

- [ ] **Scenario: Scheduler starts without missing deps**
  - **Given** the dev stack is running
  - **When** the scheduler starts
  - **Then** it does not fail with `ModuleNotFoundError: apscheduler`.

- [ ] **Scenario: Cluster profiles table exists before use**
  - **Given** the graph taxonomy bootstrap runs
  - **When** the bootstrap begins
  - **Then** `cluster_profiles` exists before any profile lookup occurs.

- [ ] **Scenario: Empty profiles trigger one-time synthesis**
  - **Given** no profiles exist for the active source
  - **When** bootstrap checks the table
  - **Then** it runs one-time metadata synthesis and inserts profiles.

- [ ] **Scenario: Correct Weaviate sources are used**
  - **Given** `GRAPH_TAXONOMY_SOURCE=lethe`
  - **When** bootstrap runs
  - **Then** it uses `TheLethe` + `ClusterCentroidLethe`, with text=`body`,
    source=`sourcePath`, heading=`subject`.
  - **Given** `GRAPH_TAXONOMY_SOURCE=muses`
  - **When** bootstrap runs
  - **Then** it uses `TheMuses` + `ClusterCentroidCollection`, with text=`text`,
    source=`sourceFile`, heading=`headingPath`.

- [ ] **Scenario: Bootstrap is skipped once profiles exist**
  - **Given** profiles already exist for the active source
  - **When** bootstrap runs again
  - **Then** it skips synthesis and logs the skip reason.

- [ ] **Scenario: Taxonomy continues after bootstrap**
  - **Given** bootstrap inserts profiles
  - **When** graph taxonomy runs
  - **Then** it completes using the newly created profiles and logs the outcome.

## Testing Plan
- Unit: verify dependency import path used in scheduler startup (no missing deps).
- Unit: repo `has_profiles` and bootstrap trigger logic for empty sources.
- Integration: run bootstrap against real Postgres; verify profiles inserted once.
- E2E (dev): seed minimal Lethe data, run bootstrap + taxonomy, confirm profiles exist.
