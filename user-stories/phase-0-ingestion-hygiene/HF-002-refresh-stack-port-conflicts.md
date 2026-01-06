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

## Testing Plan

- Unit: validate conflict detection/prompt strings in `scripts/refresh-stack.sh`.
- Integration: run the script with a conflicting Mnemosyne container; verify auto-stop and a successful refresh.
- E2E: run `IMAGE_TAG_OVERRIDE=latest ./scripts/refresh-stack.sh staging` and confirm services are healthy and watchers restarted.
