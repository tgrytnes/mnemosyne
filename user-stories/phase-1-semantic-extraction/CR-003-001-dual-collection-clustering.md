# CR-003-001: Dual-Collection Clustering and Lethe-Only Graph Taxonomy (Change Request)

**As a** Platform Administrator  
**I want** clustering to run separately for TheMuses and TheLethe, with graph taxonomy built only from TheLethe  
**So that** curated vault content drives Scout proposals while archived emails/PDFs drive taxonomy in Neo4j without mixing sources

## Context / Clarifications
- Pipeline A (Vault): Obsidian → embeddings → clusters (TheMuses) → Scout → project proposals.
- Pipeline B (Archive): Emails/PDFs → embeddings → clusters (TheLethe) → graph taxonomy → Neo4j.
- Graph taxonomy should **not** use TheMuses for now.
- Email chunks are stored in **TheLethe** with `documentType=email` (no separate chunk collection).
- Cluster profiles are stored in Postgres with a `source` column (`muses` or `lethe`).

## Acceptance Criteria
- [ ] Clustering runs **separately** for TheMuses and TheLethe.
- [ ] Each collection uses its own cluster count (`N_CLUSTERS_MUSES`, `N_CLUSTERS_LETHE`) with fallback to `N_CLUSTERS`.
- [ ] Cluster IDs are updated only on objects in their respective collections (no cross-updates).
- [ ] Centroids are stored in **separate** collections (e.g., `ClusterCentroidMuses`, `ClusterCentroidLethe`).
- [ ] Scout uses **TheMuses** clusters only and continues to write discoveries/proposals from TheMuses data.
- [ ] Graph taxonomy uses **TheLethe** centroids and TheLethe-derived cluster profiles only.
- [ ] Cluster profiles are persisted in Postgres `cluster_profiles` with a required `source` column (`muses` or `lethe`).
- [ ] Graph taxonomy filters profiles by `source='lethe'` and does not read `source='muses'`.
- [ ] Graph taxonomy writes nodes/edges to Neo4j from Lethe profiles without mixing Muses data.
- [ ] Services remain healthy when either collection is empty (no crashes; log and skip).
- [ ] Logging clearly reports per-collection clustering counts and taxonomy source.

## Configuration
- `N_CLUSTERS_MUSES` (int)
- `N_CLUSTERS_LETHE` (int)
- `N_CLUSTERS` (int, fallback)
- Optional: `GRAPH_TAXONOMY_SOURCE=lethe` (default to lethe for now)

## Test Plan (TDD)
**Unit**
- [ ] Clustering config resolves per-collection cluster counts with fallback.
- [ ] Cluster managers write to the correct centroid collection for each source.
- [ ] Graph taxonomy pipeline selects Lethe centroids/profiles only.
- [ ] Cluster profile repository requires and persists the `source` column.

**Integration (real services)**
- [ ] Weaviate: verify TheMuses and TheLethe each receive cluster IDs and their own centroid collections.
- [ ] Postgres: verify cluster_profiles are stored with correct `source` metadata.
- [ ] Neo4j: verify taxonomy nodes/edges are created from Lethe profiles only.

**E2E**
- [ ] Run full scheduler iteration with sample vault + email/PDF data.
- [ ] Confirm Scout proposals are generated from TheMuses only.
- [ ] Confirm Neo4j taxonomy is populated from TheLethe only.

## Affected Components
- `mnemosyne.cli.cluster`
- `mnemosyne.argus.graph_taxonomy_pipeline`
- `mnemosyne.argus.delta_sync` (if profile synthesis depends on centroids)
- `mnemosyne.alexandria.cluster_profile_repository`
- `mnemosyne.alexandria.weaviate_schema`
- `mnemosyne.cli.scheduler`

## Priority
High

## Estimate
8–13 pts
