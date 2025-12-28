# Mnemosyne User Stories Index

Quick reference for all user stories with status tracking.

## Phase 0: Ingestion & Hygiene (Foundation)

| ID | Title | Priority | Estimate | Status | Assignee |
|----|-------|----------|----------|--------|----------|
| 000 | Obsidian Vault Ingestion | Critical | 8 pts | ✅ Done | - |
| 001 | Email Archive Ingestion | Medium | 13 pts | 📝 Draft | - |
| 002 | Shadow Copy & Hygiene Layer | High | 13 pts | 📝 Draft | - |
| 003 | PDF & OCR Document Ingestion | Medium | 8 pts | 📝 Draft | - |

**Phase Total**: 42 story points (8 completed, 34 remaining)

## Phase 1: Semantic Extraction (The Graph Schema)

| ID | Title | Priority | Estimate | Status | Assignee |
|----|-------|----------|----------|--------|----------|
| 001 | Cluster Centroid Node | High | 5 pts | 📝 Draft | - |
| 002 | Structured Metadata Synthesis | High | 8 pts | 📝 Draft | - |
| 003 | Automated Graph Taxonomy | Medium | 8 pts | 📝 Draft | - |
| 019 | Quality Assurance Framework | High | 8 pts | 📝 Draft | - |
| 020 | Hierarchical Structure Preservation | High | 5 pts | 📝 Draft | - |
| 021 | Semantic Chunking with LLM | High | 13 pts | 📝 Draft | - |

**Phase Total**: 47 story points

## Phase 2: The Efficiency Engine (Memory & Persistence)

| ID | Title | Priority | Estimate | Status | Assignee |
|----|-------|----------|----------|--------|----------|
| 004 | Checkpointed Knowledge | High | 5 pts | 📝 Draft | - |
| 005 | Semantic Routing | High | 8 pts | 📝 Draft | - |
| 006 | Delta Sync Node | Medium | 8 pts | 📝 Draft | - |

**Phase Total**: 21 story points

## Phase 3: The Showcase (Visual Interaction)

| ID | Title | Priority | Estimate | Status | Assignee |
|----|-------|----------|----------|--------|----------|
| 007 | Multi-Turn Reasoning Loop | Medium | 8 pts | 📝 Draft | - |
| 008 | The "Traceable" Showcase | Low | 5 pts | 📝 Draft | - |
| 009 | Actionable Synthesis | High | 5 pts | 📝 Draft | - |

**Phase Total**: 18 story points

## Phase 4: The Latent Scout (Autonomous Discovery)

| ID | Title | Priority | Estimate | Status | Assignee |
|----|-------|----------|----------|--------|----------|
| 010 | Autonomous Pattern Detection | Medium | 13 pts | 📝 Draft | - |
| 011 | Radar Vector Exploration | Low | 13 pts | 📝 Draft | - |
| 012 | Proactive Insight Notifications | High | 8 pts | 📝 Draft | - |
| 013 | Discovery Feed Management | Medium | 8 pts | 📝 Draft | - |
| 014 | SQL Project Gatekeeper | Critical | 8 pts | 📝 Draft | - |

**Phase Total**: 50 story points

---

## Summary

- **Total Stories**: 21
- **Stories Completed**: 1 (5%)
- **Total Story Points**: 178 points
- **Story Points Completed**: 8 points (4%)
- **Estimated Duration**: 34-43 weeks remaining (assuming 4-5 points/week velocity)

## Status Legend
- 📝 Draft - Story written, not yet started
- 🔄 In Progress - Currently being developed
- 👀 Review - Implementation complete, under review
- ✅ Done - Accepted and merged
- 🚫 Blocked - Waiting on dependencies

## Priority Distribution
- Critical: 2 stories (11%)
- High: 7 stories (39%)
- Medium: 7 stories (39%)
- Low: 2 stories (11%)

## Component Impact

### By Component (stories that touch each)
- **Aletheia**: 7 stories (41% - ingestion, cleaning, The Graphos)
- **Argus**: 13 stories (76% - core implementation hub for both reactive & latent scout)
- **Alexandria**: 14 stories (82% - storage and governance)
- **Hermes**: 6 stories (35% - user interface and notifications)
- **Iris**: 2 stories (12% - search integration)
- **Prometheus**: 2 stories (12% - proposal generation)

### Dependency Chain

```
Phase 0 Foundation (MUST complete first):
000 (Vault Ingestion) ─┬→ Phase 1+
002 (Shadow Copy)      ─┤
001 (Email Ingestion)  ─┤  Optional, parallel
003 (PDF/OCR)          ─┘  Optional, parallel

Phase 1 Foundation (Required for all semantic features):
[Phase 0] → 001 (Cluster Centroids) → 002 (Metadata Synthesis) → 003 (Graph Taxonomy)

Phase 2 Reactive Agent (Builds on Phase 1):
[001,002,003] → 004 (Checkpoints) → 005 (Routing) → 006 (Delta Sync)

Phase 3 User Experience (Requires Phase 1 & 2):
[001-006] → 007 (Multi-Turn Loop) → 008 (Visualization) → 009 (Synthesis Output)

Phase 4 Latent Scout (Runs parallel to Phases 2-3):
[001,002,003] → 010 (Pattern Detection) ─┬→ 012 (Notifications) → 013 (Feed)
                                           │
              [001,002,003] → 011 (Radar) ─┘
```

### Argus Architecture Split

**Reactive Mode** (Stories 001-009):
- User-triggered query answering
- LangGraph-based reasoning loops
- Real-time response requirements
- High priority for MVP

**Proactive Mode** (Stories 010-013):
- Background autonomous discovery
- Scheduled pattern detection
- No user prompt required
- Lower priority, builds on reactive foundation

**Shared Infrastructure**:
- Cluster analysis utilities (from Story 001)
- Insight engines (projectness, contradiction detection, etc.)
- LangGraph framework
- Vector operations

## Phase Readiness

### Phase 0 → Phase 1
**Blockers**: None, can start immediately
**Prerequisites**:
- Docker + Docker Compose
- Ollama with qwen3-embedding:0.6b and qwen3:0.6b
- Weaviate instance
- Obsidian vault accessible

**Critical Path**: Story 000 (Vault Ingestion) MUST complete
**Optional**: Stories 001 (Email), 003 (PDF) can run in parallel

### Phase 1 → Phase 2
**Blockers**: Phase 0 Story 000 must complete (vault data required)
**Prerequisites**: Phase 0 complete, Weaviate populated with vault chunks

### Phase 2 → Phase 3
**Blockers**: Phase 1 must complete (Stories 001-003)
**Prerequisites**: LangGraph persistence configured

### Phase 3 → Production
**Blockers**: Phase 1 & 2 must complete
**Prerequisites**: LangGraph Studio for visualization

### Phase 4 → Standalone
**Blockers**: Only needs Phase 1 (Stories 001-003)
**Can run parallel to**: Phases 2 & 3
**Note**: Phase 4 can be developed independently after Phase 1

## Recommended Implementation Order

### Sprint 1-3 (Phase 0): Ingestion Foundation
1. **Story 000: Obsidian Vault Ingestion** (CRITICAL - blocks everything)
2. **Story 002: Shadow Copy & Hygiene** (safety layer)
3. Story 001: Email Archive Ingestion (optional, parallel)
4. Story 003: PDF/OCR Ingestion (optional, parallel)

### Sprint 4-6 (Phase 1): Semantic Foundation
1. Story 001: Cluster Centroid Node (renumbered from old 001)
2. Story 002: Structured Metadata Synthesis (renumbered from old 002)
3. Story 003: Automated Graph Taxonomy (renumbered from old 003)

### Sprint 7-9 (Phase 2): Reactive Agent
4. Story 004: Checkpointed Knowledge
5. Story 005: Semantic Routing
6. Story 006: Delta Sync Node

### Sprint 10-12 (Phase 3): User Experience
7. Story 009: Actionable Synthesis (highest user value)
8. Story 007: Multi-Turn Reasoning Loop
9. Story 008: The "Traceable" Showcase (optional demo)

### Sprint 13-17 (Phase 4): Latent Scout
10. **Story 014: SQL Project Gatekeeper** (CRITICAL - safety layer)
11. Story 010: Autonomous Pattern Detection
12. Story 012: Proactive Insight Notifications
13. Story 013: Discovery Feed Management
14. Story 011: Radar Vector Exploration (advanced, optional)

## Success Metrics by Phase

### Phase 0 Success
- [ ] Obsidian vault (300+ files) fully ingested
- [ ] Shadow copy hygiene operational with approval workflow
- [ ] Email archive (if applicable) clustered and classified
- [ ] PDF documents (if applicable) OCR'd and searchable
- [ ] Ingestion rate: 3-4 files/minute on Pi 5
- [ ] No data loss or corruption in canonical vault

### Phase 1 Success
- [ ] 416 clusters successfully profiled
- [ ] Graph taxonomy has <5% orphaned clusters
- [ ] Profile generation takes <30 seconds per cluster

### Phase 2 Success
- [ ] Query cache hit rate >40%
- [ ] 90% of queries complete in <5 seconds on Pi 5
- [ ] Delta sync processes changes in <5 minutes

### Phase 3 Success
- [ ] Users create 10+ synthesis notes per week
- [ ] Multi-turn loops average <3 iterations to answer
- [ ] LangGraph Studio successfully visualizes flows

### Phase 4 Success
- [ ] Scout finds 5+ useful discoveries per week
- [ ] <30% discovery dismissal rate (70%+ useful)
- [ ] SQL Gatekeeper: 0 unauthorized writes to The Ananke
- [ ] Project approval rate >60% (high signal-to-noise)
- [ ] Notification acceptance rate >50%
- [ ] Weekly active engagement with discovery feed

## Next Steps

1. ✅ Review Phase 4 stories
2. 🔲 Update Argus README to clarify reactive vs. proactive modes
3. 🔲 Create technical architecture diagram
4. 🔲 Set up Linear project and import stories
5. 🔲 Prioritize infrastructure stories (Weaviate, PostgreSQL, Docker)
6. 🔲 Begin Phase 1 Sprint 1
