# Change Request CR-000-009: Graph Taxonomy Profile Bootstrap

**As a** platform operator
**I want** graph taxonomy to auto-bootstrap cluster profile storage and metadata synthesis on first run
**So that** new environments can populate Neo4j without manual database setup steps

## Background
Graph taxonomy relies on `cluster_profiles` in Postgres. Fresh environments can fail if the
`cluster_profiles` table is missing or empty. This CR adds a one-time bootstrap step that:
1) ensures the table exists, and
2) synthesizes initial profiles when the table is empty for the active source.

## Acceptance Criteria
- [ ] Graph taxonomy ensures the `cluster_profiles` table exists before querying it.
- [ ] If no profiles exist for the active source (`lethe` or `muses`), the system runs a one-time
      metadata synthesis pass to populate `cluster_profiles`.
- [ ] Bootstrap uses the correct Weaviate collections and properties:
      - `lethe`: `TheLethe` + `ClusterCentroidLethe`, text=`body`, source=`sourcePath`, heading=`subject`.
      - `muses`: `TheMuses` + `ClusterCentroidCollection`, text=`text`, source=`sourceFile`, heading=`headingPath`.
- [ ] Bootstrap is skipped once profiles exist for the source.
- [ ] Graph taxonomy continues with the newly created profiles and logs the bootstrap outcome.

## Test Plan
- **Unit**:
  - `ClusterProfileRepository.has_profiles` returns expected values.
  - Graph taxonomy pipeline ensures the table exists and calls bootstrap when profiles are empty.
- **Integration**:
  - Bootstrap helper uses real Postgres to detect empty profiles and invokes synthesis.
- **E2E**:
  - Seed minimal Weaviate data, run bootstrap for an empty profile table, and verify profiles are
    created in Postgres before graph taxonomy runs.

## Notes
- One-time bootstrap should happen on the first graph taxonomy run per environment/source.
- Uses existing Ollama config (`OLLAMA_BASE_URL`) for synthesis.
