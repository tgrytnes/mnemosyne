# HF-001: Email Source Directory Hotfix for Story 031

**As a** Platform Operator  
**I want** the raw email ingestion pipeline to have an explicit `SOURCE_DIR` defined in every environment and in Docker Compose  
**So that** the new `.eml`/`.mbox` ingestion can run without manual overrides and the watcher can reliably observe the correct directory.

## Excellent Acceptance Criteria

- [ ] **Scenario: Environment consistency**
  - **Given** the dev, staging, and prod `.env.*` files
  - **When** they are sourced by their respective containers
  - **Then** each file defines `SOURCE_DIR` pointing to the environment’s email directory (`/srv/mnemosyne/<env>/emails`)

- [ ] **Scenario: Compose defaults**
  - **Given** the `mnemosyne_ingestor` service in `docker-compose.yml`
  - **When** the container starts without an explicit `SOURCE_DIR` env override
  - **Then** the service falls back to `/data/emails` and the deprecated `EMAIL_TSV` variable is removed

- [ ] **Scenario: Hotfix traceability**
  - **Given** the change history for Story 031
  - **When** we review configuration docs
  - **Then** this hotfix document references the environment wiring that makes the story functional.

## Testing Plan

- Manually `docker compose` up dev/staging/prod variants and confirm `env | grep SOURCE_DIR` outputs the expected path.
- Run `python -m mnemosyne.aletheia.email_ingest` inside each environment to ensure it reads `/data/emails` by default.
- Verify `docker-compose.yml` no longer sets `EMAIL_TSV`.
