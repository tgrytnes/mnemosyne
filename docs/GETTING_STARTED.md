# Getting Started with Mnemosyne

Quick start guide to begin developing Mnemosyne.

## Prerequisites

- **Python 3.11+**
- **Docker** (for services)
- **Git**
- **Ollama** (running on port 11434)

## Quick Setup (5 minutes)

### 1. Clone and Setup

```bash
cd /home/tgrytnes/projects/Mnemosyne

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install requests python-dotenv

# Or with Poetry (if available)
poetry install --with dev
```

### 2. Configure Environment

```bash
# Use development environment
make env-dev

# Verify configuration
cat .env | grep ENVIRONMENT
# Should show: ENVIRONMENT=development
```

### 3. Start Services

```bash
# Start Weaviate, PostgreSQL, Redis
docker-compose -f docker-compose.dev.yml up -d

# Verify services
curl http://localhost:11434/api/tags  # Ollama
curl http://localhost:8081/v1/.well-known/ready  # Weaviate
```

### 4. Setup Test Data

Test data is already created (50 vault files, 1,000 emails).

Verify:
```bash
ls test_data/test_vault/ | wc -l
# Should show: 50
```

### 5. Setup Linear (Optional)

```bash
# Get API key from https://linear.app/settings/api
echo "LINEAR_API_KEY=lin_api_xxxxx" >> .env

# Import stories (one-time)
.venv/bin/python scripts/import_to_linear.py
```

## Your First Development Cycle

### 1. Pick a Story

Start with **Story 000: Obsidian Vault Ingestion**

```bash
# Read the story
cat user-stories/phase-0-ingestion-hygiene/story-000-obsidian-vault-ingestion.md

# Check implementation plan
cat IMPLEMENTATION_PLAN.md | grep -A 20 "Story 000"
```

### 2. Create Package Structure

```bash
# Create Aletheia package (The Ingestor)
mkdir -p Aletheia
touch Aletheia/__init__.py
```

### 3. Write Tests First (TDD)

```bash
# Create test file
vim tests/unit/test_ingestor.py
```

Example test:
```python
import pytest

@pytest.mark.unit
class TestMarkdownCleaning:
    def test_remove_yaml_frontmatter(self):
        """Test YAML frontmatter removal"""
        from Aletheia.ingestor import ObsidianIngestor

        content = """---
title: Test
tags: [test]
---
# Heading
Content here"""

        ingestor = ObsidianIngestor(vault_path="test_data/test_vault")
        cleaned = ingestor.clean_markdown(content)

        assert "---" not in cleaned
        assert "# Heading" in cleaned
```

### 4. Run Tests (Red)

```bash
# Should fail - code doesn't exist yet
pytest tests/unit/test_ingestor.py -v
```

### 5. Implement Code (Green)

```bash
# Create implementation
vim Aletheia/ingestor.py
```

Example:
```python
class ObsidianIngestor:
    def __init__(self, vault_path: str):
        self.vault_path = vault_path

    def clean_markdown(self, content: str) -> str:
        """Remove YAML frontmatter from markdown"""
        # Remove YAML frontmatter
        import re
        content = re.sub(r'^---\n.*?\n---\n', '', content, flags=re.DOTALL)
        return content
```

### 6. Run Tests (Green)

```bash
# Should pass now
pytest tests/unit/test_ingestor.py -v
```

### 7. Iterate

Repeat: Write test → Fail → Implement → Pass → Refactor

## Project Structure

```
Mnemosyne/
├── Aletheia/              # Layer 1: Input Processing
├── Alexandria/            # Layer 2: Storage & Governance
├── Argus/                 # Layer 3: Subconscious (Scout, Curator)
├── Iris/                  # Layer 4: Intelligence Services
├── Hermes/                # Layer 5: Interaction (Telegram, Manager)
├── Prometheus/            # Layer 6: Execution (Future)
│
├── tests/
│   ├── unit/              # Fast, isolated tests
│   ├── integration/       # With real services
│   └── e2e/               # Complete workflows
│
├── test_data/             # Sample data (50 files)
│   ├── test_vault/
│   └── cleaned_emails_sample.tsv
│
├── user-stories/          # Detailed specifications
│   ├── phase-0-ingestion-hygiene/
│   ├── phase-1-semantic-extraction/
│   └── ...
│
├── docs/                  # All documentation
│   ├── GETTING_STARTED.md     # This file
│   ├── TESTING.md             # Testing guide
│   ├── DEPLOYMENT.md          # Deployment guide
│   └── LINEAR_INTEGRATION.md  # Linear sync
│
├── scripts/               # Utility scripts
├── IMPLEMENTATION_PLAN.md # Execution roadmap
└── README.md              # Project overview
```

## Development Workflow

### Daily Routine

```bash
# 1. Sync from Linear
.venv/bin/python scripts/sync_from_linear.py --show-status

# 2. Pick next story
cat IMPLEMENTATION_PLAN.md

# 3. Read story details
cat user-stories/phase-X/story-XXX-*.md

# 4. Write tests
vim tests/unit/test_*.py

# 5. Run tests (TDD)
make test

# 6. Implement
vim Aletheia/*.py

# 7. Run all tests
make test-all

# 8. Update Linear
# Move story to "Done" in Linear

# 9. Sync and commit
.venv/bin/python scripts/sync_from_linear.py
git add .
git commit -m "Implement Story 000: Obsidian Vault Ingestion"
git push
```

### Testing Levels

**Unit Tests** (write first, run always):
```bash
make test
# Fast, no Docker, mocked dependencies
```

**Integration Tests** (after unit tests pass):
```bash
make test-integration
# With real services, slower
```

**E2E Tests** (after feature complete):
```bash
pytest tests/e2e -v
# Complete workflows, slowest
```

## Environment Management

```bash
# Development (default)
make env-dev
# Uses test data (50 files), fast iteration

# Production (Raspberry Pi)
make env-prod
# Uses full data (512 files), optimized settings
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for deployment guide.

## Common Commands

```bash
# Testing
make test                # Unit tests
make test-integration    # Integration tests
make test-all           # All tests + coverage
make coverage           # HTML coverage report

# Services
make services-up        # Start Docker services
make services-down      # Stop services

# Code Quality
make format             # Format with Black
make lint              # Run linters
make check             # All quality checks

# Environment
make env-dev           # Development mode
make env-prod          # Production mode
```

## Useful Links

**Documentation**:
- Implementation Plan: [../IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md)
- Testing Guide: [TESTING.md](TESTING.md)
- Deployment Guide: [DEPLOYMENT.md](DEPLOYMENT.md)
- Linear Integration: [LINEAR_INTEGRATION.md](LINEAR_INTEGRATION.md)

**User Stories**:
- System Architecture: [../user-stories/SYSTEM_ARCHITECTURE.md](../user-stories/SYSTEM_ARCHITECTURE.md)
- Story Index: [../user-stories/STORY_INDEX.md](../user-stories/STORY_INDEX.md)

**External**:
- Linear Workspace: https://linear.app/project-mnemosyne
- Ollama API: http://localhost:11434
- Weaviate: http://localhost:8081

## Next Steps

1. ✅ **Read Story 000**: `cat user-stories/phase-0-ingestion-hygiene/story-000-*.md`
2. ✅ **Follow Implementation Plan**: See IMPLEMENTATION_PLAN.md lines 633-668
3. ✅ **Write First Test**: `vim tests/unit/test_ingestor.py`
4. ✅ **Implement**: Follow TDD cycle (Red → Green → Refactor)
5. ✅ **Track in Linear**: Move PRO-5 to "In Progress" → "Done"

## Troubleshooting

### Services not connecting?

```bash
# Check Docker
docker ps

# Restart services
make services-down
make services-up

# Check logs
docker-compose -f docker-compose.dev.yml logs
```

### Tests failing?

```bash
# Clear cache
make clean

# Reinstall dependencies
pip install -r requirements.txt

# Check environment
cat .env | grep ENVIRONMENT
```

### Wrong environment?

```bash
# Switch back to dev
make env-dev

# Verify
cat .env | head -5
```

## Getting Help

- **Implementation Plan**: Detailed week-by-week guide
- **Testing Guide**: How to write and run tests
- **User Stories**: Full requirements and acceptance criteria
- **Linear**: Track progress and ask questions

---

**Ready to start?** Begin with Story 000: Obsidian Vault Ingestion!

See [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md) lines 633-668 for detailed steps.
