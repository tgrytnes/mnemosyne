# CR-000-006: Scheduler/Ingestor Operational Controls

**As a** Platform Operator  
**I want** better control and observability of the scheduler/ingestor processes  
**So that** I can verify they are running, pause them safely, and stop/start them reliably during updates.

## Excellent Acceptance Criteria

- [ ] **Scenario: Runtime tooling available**
  - **Given** the scheduler/ingestor containers
  - **When** we need to verify running processes
  - **Then** the image includes `ps`/`pgrep` tooling (procps).

- [ ] **Scenario: Health checks report watcher status**
  - **Given** the scheduler/ingestor services are running
  - **When** Docker healthchecks execute
  - **Then** services are marked healthy only when their watcher loops are running, and unhealthy otherwise.

- [ ] **Scenario: Enable/disable flags**
  - **Given** `SCHEDULER_ENABLED=false`
  - **When** the scheduler container starts
  - **Then** it logs that it is disabled and stays idle.
  - **Given** `INGESTOR_WATCH_ENABLED=false`
  - **When** the ingestor container starts
  - **Then** it completes the one-time ingestion steps and does not start the watcher loop.

- [ ] **Scenario: Graceful shutdown**
  - **Given** the scheduler or ingestor is running
  - **When** the container receives SIGTERM
  - **Then** it logs a clean shutdown and exits without stack traces.

## Testing Plan

- Unit: verify env-flag logic for scheduler and ingestor.
- Unit: verify docker-compose healthcheck commands for scheduler/ingestor.
- Unit: verify Dockerfiles include procps.
- Integration: run compose with flags disabled and confirm containers remain stable.
- Integration: run compose without flags and confirm healthchecks report healthy.
