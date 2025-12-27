# Mnemosyne User Stories

This directory contains all user stories for the Mnemosyne project, organized by phase and component.

## Structure

- `phase-1-semantic-extraction/` - Graph schema and semantic mapping
- `phase-2-efficiency-engine/` - Memory, persistence, and optimization
- `phase-3-showcase/` - Visual interaction and demonstration features
- `phase-4-latent-scout/` - Autonomous discovery and proactive insights
- `backlog/` - Future stories not yet assigned to a phase

## Story Format

Each story file follows this structure:
```markdown
# [Story ID]: [Title]

**As a** [role]
**I want** [feature]
**So that** [benefit]

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2

## Technical Notes
[Implementation details, dependencies, etc.]

## Affected Components
- Component 1
- Component 2

## Priority
[High/Medium/Low]

## Estimate
[Story points or time estimate]
```

## Linear Integration

Stories in this directory can be synced to Linear using:
- Manual creation (copy/paste)
- Linear CLI
- Custom sync script (TBD)

## Phases Overview

### Phase 1: Semantic Extraction (The Graph Schema)
**Goal**: Map the "Nodes" of your knowledge and initialize the Agent's state.
- Affected: Argus, Alexandria (Weaviate)
- LangGraph introduction

### Phase 2: The Efficiency Engine (Memory & Persistence)
**Goal**: Leverage LangGraph's persistence to make the Pi 5 snappy and responsive.
- Affected: Argus, Alexandria (SQLite cache)
- Performance optimization focus

### Phase 3: The Showcase (Visual Interaction)
**Goal**: Demonstrate the "Librarian Agent" in action using visual agentic flows.

**Stories**: 007-009 (18 points)
- Multi-turn reasoning loops
- LangGraph Studio visualization
- Actionable synthesis output to Obsidian

**Affected**: Hermes, Iris, Argus, Aletheia

**Why**: User-facing features and polished UX

---

### Phase 4: The Latent Scout (Autonomous Discovery)
**Goal**: Proactively discover patterns and insights without user prompts.

**Stories**: 010-013 (42 points)
- Autonomous pattern detection (emerging themes, contradictions, projects)
- Radar vector exploration (weak link discovery)
- Proactive notifications via Telegram
- Discovery feed management

**Affected**: Argus (latent scout mode), Hermes, Alexandria

**Why**: The "thinking partner" differentiator - system watches your vault autonomously

---

## Argus: Reactive vs. Proactive Modes

The Argus component has two distinct operational modes that share infrastructure:

### Reactive Mode (Stories 001-009)
**Trigger**: User query via Telegram or API
**Purpose**: Answer questions, synthesize information
**Latency**: Real-time (<5 seconds target)
**Examples**:
- "What are my notes about Docker networking?"
- "Find contradictions in my philosophy notes"
- "Summarize my homelab project notes"

### Proactive Mode (Stories 010-013)
**Trigger**: Scheduled background jobs (daily, weekly)
**Purpose**: Autonomous discovery without prompts
**Latency**: Batch processing (can take 30+ minutes)
**Examples**:
- Detecting emerging themes from recent notes
- Finding unexpected connections between clusters
- Identifying project candidates
- Surfacing contradictions

### Shared Infrastructure
Both modes use:
- Cluster centroids and profiles (Phase 1)
- LangGraph framework
- Insight engines (projectness detector, contradiction finder, etc.)
- Alexandria's storage (Weaviate, PostgreSQL)

**Key Principle**: Insight logic is reusable. The scout runs it proactively; the reactive agent runs it on-demand.

---

## Implementation Recommendations

### Critical Path (MVP)
1. **Phase 1** (required for everything)
2. **Phase 2 Stories 004-005** (checkpoints + routing for usable reactive agent)
3. **Phase 3 Story 009** (Obsidian output - immediate user value)

### Nice-to-Have (Post-MVP)
- Phase 2 Story 006 (Delta sync - can manually trigger initially)
- Phase 3 Stories 007-008 (Showcase features)
- Phase 4 (Entire latent scout - differentiator but not blocking)

### Parallel Development Opportunity
After Phase 1 completes, **Phase 2-3** (reactive) and **Phase 4** (proactive) can be developed in parallel by different developers/teams.

---

## Success Metrics

### Phase 1
- 416 clusters successfully profiled
- <5% orphaned clusters in graph
- Profile generation <30s per cluster

### Phase 2
- Cache hit rate >40%
- 90% queries complete <5s on Pi 5
- Delta sync <5 min per run

### Phase 3
- Users create 10+ synthesis notes/week
- Multi-turn loops average <3 iterations
- LangGraph Studio visualizations working

### Phase 4
- Scout finds 5+ useful discoveries/week
- <30% dismissal rate (70%+ useful)
- 50%+ notification acceptance rate

---

## Technical Stack Summary

| Component | Technologies |
|-----------|-------------|
| **LangGraph** | State management, agentic flows, persistence |
| **Weaviate** | Vector storage (The Lethe, The Muses, Discovery DB) |
| **PostgreSQL** | Structured data (The Ananke, exploration state) |
| **SQLite** | Query cache, checkpoints |
| **Qwen3** | LLM for profile generation, explanations (JSON mode) |
| **Sentence-Transformers** | Local embeddings |
| **Python/Pydantic** | Data validation (The Gates) |
| **Telegram Bot** | User interface (Hermes) |
| **Docker** | Containerization (Alexandria stack) |
| **Obsidian** | Note storage (The Graphos vault mount) |

---

## Getting Started

1. Review [STORY_INDEX.md](STORY_INDEX.md) for quick overview
2. Read Phase 1 stories to understand foundation
3. Set up development environment (see infrastructure prerequisites)
4. Import stories to Linear or start with Story 001

---

## Questions?

- Architecture questions: See Argus reactive vs. proactive modes above
- Implementation order: See Critical Path section
- Dependencies: Check STORY_INDEX.md dependency chain
- Technical details: Each story has comprehensive Technical Notes section
