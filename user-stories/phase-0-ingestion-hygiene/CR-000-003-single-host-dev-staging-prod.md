# CR-000-003: Single-Host Dev/Staging/Prod Compose Environments (Change Request)

**As a** Platform Administrator  
**I want** dev, staging, and prod deployments isolated on a single Raspberry Pi using Docker Compose  
**So that** I can test and promote builds reliably now, and later move staging or prod to another host with minimal changes

## Context / Clarifications
- Current host: Raspberry Pi with 8GB RAM.
- We will run **one environment at a time** (sequential) to avoid resource contention.
- Isolation uses separate compose projects, env files, and volumes per environment.
- Images are built in CI and pulled by tag on the host (no local build on the Pi).

## Acceptance Criteria
- [ ] Base compose file remains `docker-compose.yml`; environment overrides use `docker-compose.dev.yml`, `docker-compose.staging.yml`, `docker-compose.prod.yml`.
- [ ] Each environment has its own env file: `.env.dev`, `.env.staging`, `.env.prod`.
- [ ] Compose projects are isolated via `-p mnemosyne-<env>` and do not share volumes or networks.
- [ ] A single command per environment brings it up, using the same base compose file and the env override.
- [ ] `IMAGE_TAG` (or equivalent) pins the exact image version; staging and prod can be promoted by reusing the same tag.
- [ ] Secrets are sourced from env files or Docker secrets; no hard-coded credentials.
- [ ] Documented procedure covers: dev -> staging -> prod promotion, rollback by tag, and how to move staging to another host later.
- [ ] Add Make targets (or scripts) for `env-dev-up`, `env-staging-up`, `env-prod-up`, `env-down`, `env-status`.
- [ ] Running environment is explicitly documented as **one at a time** on the Pi.

## Configuration
Required env vars (per environment):
- `IMAGE_TAG`
- `WEAVIATE_HTTP_HOST`, `WEAVIATE_HTTP_PORT`, `WEAVIATE_GRPC_PORT`
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
- `OLLAMA_BASE_URL`

## Test Plan (TDD)
**Unit**
- [ ] N/A (infrastructure-only change).

**Integration**
- [ ] `docker compose config` succeeds for dev/staging/prod (no invalid references).
- [ ] `make env-*-up` starts the stack and all services report healthy.

**E2E**
- [ ] Run the existing E2E suite against staging using the pinned `IMAGE_TAG`.
- [ ] Promote the same `IMAGE_TAG` to prod and confirm health checks pass.

## Affected Components
- `docker-compose.yml` + new `docker-compose.<env>.yml` files
- `.env.dev`, `.env.staging`, `.env.prod`
- `Makefile` (or scripts under `scripts/`)
- `docs/DEPLOYMENT.md` (or new `docs/ENVIRONMENTS.md`)

## Priority
High

## Estimate
8–13 pts
