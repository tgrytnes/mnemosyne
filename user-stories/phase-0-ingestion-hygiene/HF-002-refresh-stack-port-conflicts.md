# HF-002: Refresh Stack Port Conflict Resolution

**As a** Platform Operator  
**I want** `refresh-stack.sh` to detect and resolve port conflicts between Mnemosyne stacks  
**So that** dev/staging/prod refreshes do not fail with "port already allocated".

## Excellent Acceptance Criteria

- [ ] **Scenario: Conflict detection before startup**
  - **Given** a target environment with host ports configured
  - **When** the refresh script runs
  - **Then** it checks for port conflicts before `docker compose up -d`.

- [ ] **Scenario: Mnemosyne conflicts auto-resolved**
  - **Given** a conflicting container whose name includes "mnemosyne"
  - **When** a host port is already allocated
  - **Then** the script stops/removes that container and logs its name and ports.

- [ ] **Scenario: Non-Mnemosyne conflicts require confirmation**
  - **Given** a conflicting container not owned by Mnemosyne
  - **When** a host port is already allocated
  - **Then** the script prompts for confirmation before stopping it, and aborts on "no".

- [ ] **Scenario: Watcher processes restart**
  - **Given** scheduler and ingest watcher processes are running
  - **When** the refresh script executes
  - **Then** it stops the watchers first and restarts them after the stack is up, logging what was stopped and started.

- [ ] **Scenario: Image tag overrides are preserved**
  - **Given** `IMAGE_TAG_OVERRIDE` is set
  - **When** the refresh script runs
  - **Then** the override is used unchanged.

- [ ] **Scenario: Default image tag behavior**
  - **Given** no runtime `IMAGE_TAG` or `IMAGE_TAG_OVERRIDE` is provided
  - **When** the refresh script runs
  - **Then** it uses `latest`, ignoring any `IMAGE_TAG` value in `.env.*`.

- [ ] **Scenario: Watchers running after refresh**
  - **Given** the stack refresh completes
  - **When** the script finishes
  - **Then** the scheduler and ingestor containers are running and the script reports their status.

- [ ] **Scenario: Watchers verified inside containers**
  - **Given** the refreshed stack is up
  - **When** the script performs post-refresh validation
  - **Then** it confirms watcher processes are running inside the scheduler and ingestor containers, retries once if missing, and fails clearly if still absent.

## Testing Plan

- Unit: validate conflict detection/prompt strings in `scripts/refresh-stack.sh`.
- Unit: validate default image tag selection and runtime override precedence.
- Integration: run the script with a conflicting Mnemosyne container; verify auto-stop and a successful refresh.
- E2E: run `IMAGE_TAG_OVERRIDE=latest ./scripts/refresh-stack.sh staging` and confirm services are healthy and watchers restarted.
- Verification: run `docker compose ps` and `docker logs` to confirm scheduler/ingestor containers are running after refresh.
- Unit: validate watcher process checks via `docker exec` and the retry path.
