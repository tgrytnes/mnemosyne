# Mnemosyne

**Personal Knowledge Management System with AI-powered Pattern Discovery**

A 6-layer AI system that ingests your digital vault (Obsidian notes, emails, documents), discovers hidden patterns, and surfaces actionable insights through a Telegram interface.

## Overview

Mnemosyne transforms your scattered knowledge into structured, actionable intelligence through autonomous pattern detection and intelligent project management.

### Core Capabilities

- **Automatic Ingestion**: Monitors Obsidian vault, email archives, and documents
- **Semantic Clustering**: Groups similar content using embeddings
- **Pattern Detection**: Autonomous "Scout" discovers project opportunities
- **Intelligent Gatekeepers**: Human-in-the-loop approval for vault modifications
- **Telegram Interface**: Conversational access to your knowledge
- **Project Management**: Tracks active projects with pressure scores and deadlines

## Quick Start

```bash
# Setup
make env-dev
make services-up

# Start development
cat docs/GETTING_STARTED.md
```

**First Task**: Implement Story 000 (Obsidian Vault Ingestion)
- Read: `user-stories/phase-0-ingestion-hygiene/story-000-*.md`
- Follow: `IMPLEMENTATION_PLAN.md` lines 633-668

## Architecture

### 6-Layer Design

```
Layer 6: Prometheus       (Execution - Future Phase)
         └─ Autonomous task execution

Layer 5: Hermes          (Interaction)
         ├─ Telegram Bot
         └─ Project Manager Agent

Layer 4: Iris            (Intelligence Services)
         └─ Semantic Query Routing

Layer 3: Argus           (Subconscious)
         ├─ Scout (Pattern Detection)
         └─ Curator (Vault Maintenance)

Layer 2: Alexandria      (Storage & Governance)
         ├─ The Gates (Gatekeepers)
         └─ The Ananke (PostgreSQL)

Layer 1: Aletheia        (Input Processing)
         ├─ Obsidian Ingestor
         ├─ Email Ingestor
         └─ PDF/OCR Ingestor
```

### Data Stores

- **The Muses** (Weaviate): Curated Obsidian vault (~1,500 chunks)
- **The Lethe** (Weaviate): Email & PDF archive (~30k-100k chunks)
- **Discovery DB** (Weaviate): Scout findings and insights
- **The Ananke** (PostgreSQL): Committed projects and metadata

## Project Status

**Current Phase**: Phase 0 - Ingestion & Hygiene (Week 1-2)

- [ ] Story 000: Obsidian Vault Ingestion
- [ ] Story 024: Email Archive Ingestion
- [ ] Story 025: Shadow Copy & Hygiene
- [ ] Story 026: PDF/OCR Ingestion

**Progress**: 0/18 stories completed (0%)

Track progress: https://linear.app/project-mnemosyne

## Development

### Setup

```bash
# 1. Install dependencies
poetry install --with dev

# 2. Set up pre-commit hooks (enforces Black, Ruff, mypy)
poetry run pre-commit install

# 3. Configure environment
make env-dev
```

**Pre-commit hooks** automatically check code quality before commits. See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for details.

### Environment

```bash
# Development (test data, debug logging)
make env-dev

# Production (full data, optimized)
make env-prod
```

### Testing

```bash
# Fast unit tests
make test

# Integration tests (requires Docker)
make test-integration

# All tests with coverage
make test-all
```

> **Tip:** the local dev `docker-compose` maps Weaviate to `localhost:8082` and gRPC to `50062`. When you run `make test-integration` (or `pytest tests/integration/test_story_001_integration.py::test_clustering_and_representation_pipeline`) against that stack, export the same overrides that the CI workflow uses:

```bash
export TEST_WEAVIATE_PORT=8082
export TEST_WEAVIATE_GRPC_PORT=50062
export OLLAMA_BASE_URL=http://localhost:11434
make test-integration
```

### Services

**Required**:
- Ollama (port 11434) - Embeddings & LLM
- Weaviate (port 8081) - Vector database
- PostgreSQL (port 5432) - Structured data

```bash
# Start all services
make services-up

# Stop services
make services-down
```

## Documentation

### Core Guides
- **[Getting Started](docs/GETTING_STARTED.md)** - Quick start guide
- **[Development Guide](docs/DEVELOPMENT.md)** - Pre-commit hooks, code quality, CI/CD
- **[Implementation Plan](IMPLEMENTATION_PLAN.md)** - Week-by-week execution roadmap
- **[Testing Guide](docs/TESTING.md)** - How to write and run tests
- **[Deployment Guide](docs/DEPLOYMENT.md)** - Production deployment on Raspberry Pi

### Additional
- **[Linear Integration](docs/LINEAR_INTEGRATION.md)** - Project management sync
- **[System Architecture](user-stories/SYSTEM_ARCHITECTURE.md)** - Detailed architecture
- **[User Stories](user-stories/STORY_INDEX.md)** - All 18 stories indexed
- **[TabbyAPI Setup](docs/TABBYAPI_SETUP.md)** - Configure TabbyAPI for strict JSON

## Technology Stack

**AI & ML**:
- Ollama (qwen3-embedding:0.6b, qwen3:0.6b)
- LangChain / LangGraph
- MiniBatch K-Means clustering

**Databases**:
- Weaviate (vector database)
- PostgreSQL 15 (structured data)
- SQLite (state tracking & caching)

**Python**:
- Python 3.11+
- Poetry (dependency management)
- pytest (testing)

**Infrastructure**:
- Docker & Docker Compose
- Raspberry Pi 5 (production deployment)

## Implementation Timeline

**Phase 0** (Week 1-2): Ingestion & Hygiene
- Obsidian, Email, PDF ingestion
- Shadow copy & gatekeeper

**Phase 1** (Week 3-4): Semantic Extraction
- Clustering & metadata synthesis
- Automated graph taxonomy

**Phase 2** (Week 5-6): Efficiency Engine
- Checkpointed knowledge
- Semantic routing

**Phase 3** (Week 7): Showcase
- Multi-turn reasoning
- Traceable showcase

**Phase 4** (Week 8-10): Latent Scout
- Pattern detection
- Proactive notifications
- Project management

**Phase 5** (Future): Vault Curation
- Automated vault maintenance
- Content editing & organization

## Design Philosophy

### Test-Driven Development
Write tests first, implement to pass tests, refactor.

### Human-in-the-Loop
Critical decisions (project creation, vault edits) require human approval via "Gatekeepers."

### Separation of Concerns
- **The Muses**: Small, high-quality (analysis)
- **The Lethe**: Large archive (retrieval only)
- Clear separation prevents expensive operations on mixed-quality data

### Performance-First
Designed for Raspberry Pi 5 (8GB):
- Lightweight models (0.6B parameters)
- Efficient clustering
- Incremental processing

## Contributing

This is a personal project, but the architecture and patterns may be useful for similar knowledge management systems.

## License

Private project - All rights reserved

---

**Status**: Development started 2025-12-27

**Next**: Begin Story 000 - Obsidian Vault Ingestion

See [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md) for detailed setup.
