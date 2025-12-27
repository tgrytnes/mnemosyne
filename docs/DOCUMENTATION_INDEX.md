# Mnemosyne Documentation Index

Complete guide to all project documentation.

## 📚 Documentation Structure

```
Mnemosyne/
├── README.md                      # Project overview & quick start
├── IMPLEMENTATION_PLAN.md         # Week-by-week execution roadmap
│
├── docs/                          # All guides here
│   ├── GETTING_STARTED.md         # New developer onboarding
│   ├── TESTING.md                 # Testing guide & best practices
│   ├── DEPLOYMENT.md              # Production deployment guide
│   └── LINEAR_INTEGRATION.md      # Linear project management sync
│
├── user-stories/                  # Detailed specifications
│   ├── SYSTEM_ARCHITECTURE.md     # Complete system design
│   ├── STORY_INDEX.md             # All 18 stories indexed
│   └── phase-X/                   # Stories by phase
│       └── story-XXX-*.md         # Individual story specs
│
└── scripts/
    └── README.md                  # Script usage guide
```

## 🎯 Start Here

**New to the project?**
1. Read: [README.md](../README.md) - Project overview
2. Follow: [docs/GETTING_STARTED.md](GETTING_STARTED.md) - Setup guide
3. Reference: [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md) - Execution roadmap

## 📖 Core Documentation

### [Getting Started](GETTING_STARTED.md)
**Purpose**: Onboard new developers in 5 minutes

**Contains**:
- Quick setup (environment, services, test data)
- Your first development cycle (TDD workflow)
- Project structure overview
- Common commands reference

**When to read**: Before writing any code

---

### [Implementation Plan](../IMPLEMENTATION_PLAN.md)
**Purpose**: Week-by-week execution roadmap

**Contains**:
- 18 user stories organized by phase
- Critical path dependencies
- Testing strategy for each story
- Week-by-week timeline (10 weeks)
- Quality gates and coverage goals

**When to read**:
- Daily (check current story)
- Before starting new story
- When planning sprint/cycle

---

### [Testing Guide](TESTING.md)
**Purpose**: How to write and run tests

**Contains**:
- Test infrastructure setup
- Unit/Integration/E2E testing levels
- TDD workflow (Red → Green → Refactor)
- Test fixtures and examples
- Coverage goals by phase

**When to read**:
- Before writing first test
- When adding integration tests
- When coverage drops

---

### [Deployment Guide](DEPLOYMENT.md)
**Purpose**: Production deployment on Raspberry Pi

**Contains**:
- Multi-environment setup (dev/test/prod)
- Docker Compose configuration
- Environment variables guide
- Deployment workflow
- Production best practices

**When to read**:
- When setting up environments
- Before deploying to production
- When configuring Docker

---

### [Linear Integration](LINEAR_INTEGRATION.md)
**Purpose**: Sync project status with Linear

**Contains**:
- Linear setup (one-time import)
- Daily sync workflow
- Status mapping (Linear ↔ local files)
- Recommended Linear organization
- Troubleshooting

**When to read**:
- After initial setup (import stories)
- Daily (sync workflow)
- When Linear status changes

---

## 📋 User Stories & Architecture

### [System Architecture](../user-stories/SYSTEM_ARCHITECTURE.md)
**Purpose**: Complete 6-layer system design

**Contains**:
- Layer-by-layer architecture
- Data flow diagrams
- Database schema
- Technology choices
- Design rationale

**When to read**:
- When understanding system design
- Before implementing new layer
- When making architectural decisions

---

### [Story Index](../user-stories/STORY_INDEX.md)
**Purpose**: All 18 stories organized and indexed

**Contains**:
- Stories grouped by phase
- Story dependencies
- Quick reference table
- Links to individual stories

**When to read**:
- When planning work
- When looking for specific story
- When understanding dependencies

---

### Individual Story Files
**Location**: `user-stories/phase-X/story-XXX-*.md`

**Contains**:
- User story (As a... I want... So that...)
- Acceptance criteria (detailed checklist)
- Technical notes and architecture
- Code examples
- Related stories

**When to read**:
- Before implementing each story
- When writing tests
- When unclear about requirements

---

## 🛠️ Scripts Documentation

### [Scripts README](../scripts/README.md)
**Purpose**: Guide to utility scripts

**Contains**:
- Linear import script usage
- Linear sync script usage
- Test data setup script
- Quick reference

**When to read**:
- When using Linear integration
- When regenerating test data

---

## 🗂️ By Use Case

### "I'm starting development"
1. [README.md](../README.md) - Overview
2. [GETTING_STARTED.md](GETTING_STARTED.md) - Setup
3. [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md) - Find Story 000
4. `user-stories/phase-0-ingestion-hygiene/story-000-*.md` - Read requirements

### "I need to write tests"
1. [TESTING.md](TESTING.md) - Testing guide
2. [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md) - Story testing plan
3. `tests/conftest.py` - Available fixtures

### "I'm deploying to production"
1. [DEPLOYMENT.md](DEPLOYMENT.md) - Deployment guide
2. `.env.production` - Production config
3. `docker-compose.yml` - Service orchestration

### "I need to understand the architecture"
1. [SYSTEM_ARCHITECTURE.md](../user-stories/SYSTEM_ARCHITECTURE.md) - Full design
2. [README.md](../README.md) - High-level overview
3. Individual story files - Component details

### "I'm tracking progress"
1. [LINEAR_INTEGRATION.md](LINEAR_INTEGRATION.md) - Sync guide
2. Linear workspace: https://linear.app/project-mnemosyne
3. [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md) - Local status

---

## 📊 Documentation Changelog

### 2025-12-27: Documentation Cleanup
**Removed** (redundant):
- ❌ TEST_DATA_READY.md → Info in TESTING.md
- ❌ TESTING_ADDED.md → Install summary only
- ❌ LINEAR_INTEGRATION_COMPLETE.md → Consolidated
- ❌ LINEAR_IMPORT_SUCCESS.md → Consolidated
- ❌ LINEAR_SYNC_READY.md → Consolidated
- ❌ ENVIRONMENTS_READY.md → Info in DEPLOYMENT.md
- ❌ scripts/LINEAR_IMPORT.md → Consolidated
- ❌ scripts/LINEAR_SYNC.md → Consolidated

**Moved** (better organization):
- ✅ TESTING.md → docs/TESTING.md
- ✅ DEPLOYMENT_STRATEGY.md → docs/DEPLOYMENT.md

**Created** (new guides):
- ✅ docs/GETTING_STARTED.md - Quick start
- ✅ docs/LINEAR_INTEGRATION.md - Consolidated Linear docs
- ✅ docs/DOCUMENTATION_INDEX.md - This file
- ✅ scripts/README.md - Script usage

**Updated**:
- ✅ README.md - Rewritten as proper entry point

---

## 🔍 Quick Reference

| Need | Document | Location |
|------|----------|----------|
| **Setup project** | Getting Started | [docs/GETTING_STARTED.md](GETTING_STARTED.md) |
| **Find current task** | Implementation Plan | [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md) |
| **Read story details** | Individual story | `user-stories/phase-X/story-XXX-*.md` |
| **Write tests** | Testing Guide | [docs/TESTING.md](TESTING.md) |
| **Deploy to Pi** | Deployment Guide | [docs/DEPLOYMENT.md](DEPLOYMENT.md) |
| **Sync with Linear** | Linear Integration | [docs/LINEAR_INTEGRATION.md](LINEAR_INTEGRATION.md) |
| **Understand system** | System Architecture | [user-stories/SYSTEM_ARCHITECTURE.md](../user-stories/SYSTEM_ARCHITECTURE.md) |

---

## ✅ Documentation Best Practices

**When adding new docs**:
- Put in `docs/` directory (not root)
- Add to this index
- Link from README.md if core guide
- Use consistent formatting

**When updating docs**:
- Keep IMPLEMENTATION_PLAN.md synced with Linear
- Update DOCUMENTATION_INDEX.md when adding/removing
- Version control all changes

**File naming**:
- `UPPERCASE.md` for core docs
- `lowercase.md` for supplementary
- Descriptive names (not doc1.md)

---

**Last updated**: 2025-12-27

**Total docs**: 11 files (8 in docs/, 1 in scripts/, 2 at root)

**Status**: Clean, organized, ready for development ✅
