# Story 032: Automate Graph Taxonomy Updates and Monitor Agent Proposal Generation

**As a** Platform Administrator  
**I want** the scheduler to automatically run the graph taxonomy and monitor agent tasks on every iteration  
**So that** the knowledge graph stays up to date and new project proposals are materialized in Postgres without manual steps

## Acceptance Criteria
- [ ] Scheduler executes graph taxonomy and monitor agent tasks on every iteration (no gating on profile changes).
- [ ] Scheduler logs include graph metrics (nodes created, edges created) and proposal metrics (pending proposals).
- [ ] Graph taxonomy writes successfully to Neo4j via the existing pipeline.
- [ ] Monitor agent writes proposals to Postgres (proposal_queue).
- [ ] Monitor agent state is persisted in Postgres (monitor_state) and used for cooldown/re-ask logic.
- [ ] Confidence threshold and scan limit are configurable via environment variables.
- [ ] Services remain healthy under docker compose up; monitor agent does not crash on empty discovery sets.
- [ ] Unit tests cover scheduler wiring and env configuration.
- [ ] Integration tests use real Postgres, Weaviate, and Neo4j (no mocks).
- [ ] E2E test covers discovery -> proposal -> rejection -> escalation using real services.

## Technical Notes
- Scheduler runs continuously; graph taxonomy and monitor agent run every iteration.
- Use Postgres for proposal queue, monitor state, and outbox data; do not introduce SQLite.
- Configuration:
  - `MONITOR_CONFIDENCE_THRESHOLD` (float)
  - `MONITOR_SCAN_LIMIT` (int)
- Python code changes preferred; docker compose may be updated to pass env vars if needed.

## Affected Components
- Argus scheduler (`mnemosyne.cli.scheduler`)
- Graph taxonomy pipeline (`mnemosyne.argus.graph_taxonomy_pipeline`)
- Monitor agent (`mnemosyne.argus.scout.monitor_agent`)
- Alexandria storage (Postgres, Neo4j, Weaviate)

## Priority
High

## Estimate
8 pts
