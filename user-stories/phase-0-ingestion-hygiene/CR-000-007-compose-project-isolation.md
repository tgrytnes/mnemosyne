# CR-000-007: Compose Project + Data Isolation for Dev/Staging/Prod

**As a** platform operator  
**I want** dev, staging, and prod to run as fully isolated systems with separate compose project names and data roots  
**So that** all three can run concurrently without port or data conflicts.

## Excellent Acceptance Criteria

- [ ] **Scenario: Distinct compose projects**
  - **Given** `.env.dev`, `.env.staging`, and `.env.prod`
  - **When** each stack is started
  - **Then** each uses a unique `COMPOSE_PROJECT_NAME` (`mnemosyne-dev`, `mnemosyne-staging`, `mnemosyne-prod`), creating separate networks and container names.

- [ ] **Scenario: No container_name collisions**
  - **Given** the compose files
  - **When** stacks are started concurrently
  - **Then** there are no fixed `container_name` values that would collide across environments.

- [ ] **Scenario: Isolated data roots**
  - **Given** `DATA_ROOT` is set per environment
  - **When** the stack starts
  - **Then** all host-mounted data paths resolve under:
    - `/home/tgrytnes/projects/Mnemosyne/data/dev`
    - `/home/tgrytnes/projects/Mnemosyne/data/staging`
    - `/home/tgrytnes/projects/Mnemosyne/data/prod`

- [ ] **Scenario: Data migration for dev and staging**
  - **Given** existing shared data directories
  - **When** this CR is applied
  - **Then** dev and staging data are migrated into their new `DATA_ROOT` locations
  - **And** prod remains empty by default.

- [ ] **Scenario: Ports remain unique**
  - **Given** the current port mappings
  - **When** dev, staging, and prod run simultaneously
  - **Then** no host port conflicts occur.

- [ ] **Scenario: Refresh-stack honors environment isolation**
  - **Given** `scripts/refresh-stack.sh` is run for any environment
  - **When** the stack is refreshed
  - **Then** it uses that environment's `COMPOSE_PROJECT_NAME` and `DATA_ROOT` values.

## Testing Plan

- Unit: refresh-stack env resolution uses `COMPOSE_PROJECT_NAME` and `DATA_ROOT`.
- Integration: start dev + staging simultaneously; confirm distinct container names, networks, and volumes.
- E2E: run refresh-stack for dev, staging, prod sequentially; confirm each stack healthy and data paths isolated.
