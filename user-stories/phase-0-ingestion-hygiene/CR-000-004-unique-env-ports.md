# CR-000-004: Unique Host Ports per Environment (Change Request)

**As a** Platform Administrator  
**I want** dev, staging, and prod to bind to distinct host ports  
**So that** I can run environments side-by-side without port collisions

## Context / Clarifications
- Current host: Raspberry Pi with 8GB RAM.
- Staging is already running on fixed host ports; dev and prod must not overlap.
- Container ports remain standard (Weaviate 8080/50051, Postgres 5432, Neo4j 7474/7687).
- Only host port bindings change, not internal service wiring.

## Acceptance Criteria
- [ ] Host port bindings for dev, staging, and prod are unique for Weaviate HTTP, Weaviate gRPC, Postgres, Neo4j HTTP, and Neo4j Bolt.
- [ ] `docker-compose.yml` uses environment variables for host ports (no hard-coded host port numbers).
- [ ] `.env.dev`, `.env.staging`, `.env.prod` define host port values for each environment.
- [ ] `make env-dev-up`, `make env-staging-up`, `make env-prod-up` can run without host port conflicts.
- [ ] Existing container-to-container communication remains unchanged (service names + internal ports).
- [ ] Documentation clarifies the per-environment host port map.

## Proposed Port Map
- **Staging (current, keep):**
  - Weaviate HTTP: 8081
  - Weaviate gRPC: 50061
  - Postgres: 55432
  - Neo4j HTTP: 17474
  - Neo4j Bolt: 17687
- **Dev:**
  - Weaviate HTTP: 8082
  - Weaviate gRPC: 50062
  - Postgres: 55433
  - Neo4j HTTP: 17475
  - Neo4j Bolt: 17688
- **Prod:**
  - Weaviate HTTP: 8083
  - Weaviate gRPC: 50063
  - Postgres: 55434
  - Neo4j HTTP: 17476
  - Neo4j Bolt: 17689

## Configuration
Required env vars (per environment):
- `WEAVIATE_HOST_PORT`
- `WEAVIATE_GRPC_HOST_PORT`
- `POSTGRES_HOST_PORT`
- `NEO4J_HTTP_HOST_PORT`
- `NEO4J_BOLT_HOST_PORT`

## Test Plan (TDD)
**Unit**
- [ ] `docker compose config` succeeds for dev/staging/prod with the new host port env vars.

**Integration**
- [ ] `make env-*-up` starts the stack without port conflicts.
- [ ] `curl http://localhost:$WEAVIATE_HOST_PORT/v1/.well-known/ready` returns OK for each env.
- [ ] `pg_isready -h localhost -p $POSTGRES_HOST_PORT` reports ready for each env.
- [ ] `curl http://localhost:$NEO4J_HTTP_HOST_PORT/` returns a HTTP response.

**E2E**
- [ ] Run Story 015 E2E against dev while staging remains up.

## Affected Components
- `docker-compose.yml`
- `.env.dev`, `.env.staging`, `.env.prod`
- `docs/` (port map reference)

## Priority
High

## Estimate
3-5 pts
