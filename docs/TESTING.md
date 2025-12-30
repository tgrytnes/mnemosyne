# Testing Guide for Mnemosyne

Quick reference for adding tests to the Mnemosyne project.

## Quick Start

```bash
# Install dependencies
poetry install --with dev

# Check code quality BEFORE committing (RECOMMENDED)
./scripts/check_quality.sh

# Run all unit tests (fast, no Docker needed)
poetry run pytest -m unit

# Run all tests with coverage
poetry run pytest --cov=.

# Start services for integration tests
docker-compose up weaviate postgres -d

# Run integration tests
poetry run pytest -m integration
```

## Code Quality Checks

**IMPORTANT**: Always run quality checks before pushing to avoid CI failures.

### Quick Check (Recommended)

```bash
# Run both Ruff and Black checks
./scripts/check_quality.sh
```

### Manual Checks

```bash
# Check Ruff linting
.venv/bin/ruff check .

# Check Black formatting
.venv/bin/black --check .
```

### Auto-Fix Issues

```bash
# Fix Ruff issues automatically
.venv/bin/ruff check --fix .

# Fix Black formatting automatically
.venv/bin/black .
```

### Pre-Push Hook (Optional)

Automatically run quality checks before every `git push`:

```bash
# Enable pre-push hook (already configured)
git config core.hooksPath .githooks
```

The hook will prevent pushes if quality checks fail, saving CI time.

## Adding New Tests

### 1. Choose Test Type

- **Unit Test**: Testing a single function/class in isolation → `tests/unit/`
- **Integration Test**: Testing component interactions with real services → `tests/integration/`
- **E2E Test**: Testing complete workflows → `tests/e2e/`

### 2. Create Test File

File naming convention: `test_<component>.py`

```python
# tests/unit/test_my_component.py
"""
Unit tests for MyComponent
Tests Story XXX: Component Name
"""
import pytest
from unittest.mock import Mock

@pytest.mark.unit
class TestMyComponent:
    """Test suite for MyComponent"""

    def test_basic_functionality(self):
        """Test description"""
        # Arrange
        component = MyComponent()

        # Act
        result = component.do_something()

        # Assert
        assert result == expected_value
```

### 3. Use Fixtures

Available fixtures from `conftest.py`:

```python
# Temporary file system
def test_with_vault(temp_vault):
    """temp_vault: Temporary Obsidian vault with sample notes"""
    pass

def test_with_shadow(temp_shadow_vault):
    """temp_shadow_vault: Temporary shadow vault"""
    pass

# Mock services
def test_with_ollama(mock_ollama_client):
    """mock_ollama_client: Mocked Ollama for embeddings"""
    pass

def test_with_telegram(mock_telegram_bot):
    """mock_telegram_bot: Mocked Telegram bot"""
    pass

# Real services (integration tests)
def test_with_weaviate(weaviate_client, clean_weaviate_collection):
    """weaviate_client: Real Weaviate connection"""
    pass

def test_with_postgres(ananke_test_db):
    """ananke_test_db: PostgreSQL test database"""
    pass

# Test data
def test_with_data(sample_chunks, sample_email):
    """Pre-configured test data"""
    pass
```

### 4. Add Test Markers

```python
@pytest.mark.unit          # Fast, isolated test
@pytest.mark.integration   # Requires Docker services
@pytest.mark.weaviate      # Needs Weaviate
@pytest.mark.postgres      # Needs PostgreSQL
@pytest.mark.slow          # Takes >5 seconds
@pytest.mark.e2e           # End-to-end test
```

### 5. Test User Stories

Each user story should have corresponding tests:

| Story | Test File | Focus |
|-------|-----------|-------|
| Story 000: Obsidian Vault Ingestion | `test_ingestor.py` | Markdown cleaning, chunking, embeddings |
| Story 025: Obsidian Gatekeeper | `test_gatekeeper.py` | Shadow copy workflow |
| Story 005: Semantic Routing | `test_router.py` | Cache hits, routing decisions |
| Story 010: Scout Pattern Detection | `test_scout.py` | Pattern detection, confidence scoring |
| Story 014: SQL Project Gatekeeper | `test_gatekeeper.py` | Approval workflow, SQL writes |
| Story 016: Project Manager | `test_project_manager.py` | Pressure scores, deadline tracking |

## Testing Patterns

### Pattern 1: Testing with Mocks

```python
@pytest.mark.unit
def test_with_mock_database():
    """Test without real database"""
    from unittest.mock import Mock

    db = Mock()
    db.cursor().fetchall.return_value = [
        (1, "Test Project", 0.85)
    ]

    # Use mock in your test
    component = MyComponent(db)
    result = component.query()

    # Verify mock was called
    db.cursor.assert_called_once()
```

### Pattern 2: Testing Time-Dependent Code

```python
@pytest.mark.unit
def test_with_frozen_time(freeze_time):
    """Test deadline detection"""
    with freeze_time("2024-01-15 08:00:00"):
        # Time is frozen at 2024-01-15 08:00:00
        deadline = datetime(2024, 1, 17)  # 2 days away

        is_approaching = check_deadline(deadline)
        assert is_approaching is True
```

### Pattern 3: Testing File Operations

```python
@pytest.mark.unit
def test_file_cleaning(temp_vault):
    """Test markdown file cleaning"""
    # Create test file
    test_file = temp_vault / "test.md"
    test_file.write_text("""---
tags: [test]
---
# Title
Content here
""")

    # Test your function
    cleaned = clean_markdown(test_file)

    assert "---" not in cleaned
    assert "# Title" in cleaned
```

### Pattern 4: Testing Async Code

```python
@pytest.mark.asyncio
async def test_async_function():
    """Test async operations"""
    result = await async_operation()
    assert result is not None
```

### Pattern 5: Testing Exceptions

```python
@pytest.mark.unit
def test_raises_error():
    """Test error handling"""
    with pytest.raises(ValueError) as exc_info:
        invalid_operation()

    assert "expected error message" in str(exc_info.value)
```

## Running Specific Tests

```bash
# By file
pytest tests/unit/test_ingestor.py

# By class
pytest tests/unit/test_scout.py::TestPatternDetection

# By function
pytest tests/unit/test_scout.py::TestPatternDetection::test_detect_project_candidate

# By marker
pytest -m unit
pytest -m "integration and weaviate"
pytest -m "not slow"

# By keyword
pytest -k "detect"  # Runs all tests with "detect" in name

# With verbose output
pytest -vv tests/unit/test_ingestor.py
```

## Debugging Tests

```bash
# Show print statements
pytest -s

# Stop at first failure
pytest -x

# Drop into debugger on failure
pytest --pdb

# Show why tests were selected
pytest --collect-only

# Show fixture setup/teardown
pytest --setup-show
```

## Coverage

```bash
# Generate coverage report
pytest --cov=. --cov-report=term-missing

# HTML coverage report
pytest --cov=. --cov-report=html
open htmlcov/index.html

# Check coverage threshold
pytest --cov=. --cov-fail-under=80
```

## CI/CD Integration

Tests run automatically on:
- **Push to main/develop**
- **Pull requests**
- **Manual trigger** (`workflow_dispatch`)

See [`.github/workflows/test.yml`](.github/workflows/test.yml) for configuration.

## Test Data Management

### Fake Test Data (`test_data/`)

The project maintains a collection of realistic test data for integration and E2E tests:

**Location**: `test_data/` (in `.gitignore`, must be force-added)

**Structure**:
```
test_data/
├── fake_vault/          # Obsidian markdown files
│   ├── knowledge/
│   │   ├── dirty_note.md         # Has wiki-links, HTML, emojis
│   │   ├── project_alpha.md      # Multi-level headings
│   │   └── weaviate_schema.md    # Technical documentation
│   ├── dailies/
│   └── ...
├── fake_emails/         # Email test data
│   ├── spam_001.eml
│   ├── valid_email.eml
│   └── ...
└── fake_pdfs/           # PDF test documents
    ├── research_paper.pdf
    └── ...
```

**Usage in Tests**:
```python
# Use the fake vault in your tests
@pytest.fixture
def test_vault():
    """Use the real fake_vault test data"""
    return Path("test_data/fake_vault")

# Or create programmatic test data
@pytest.fixture
def test_vault(tmp_path):
    """Create vault on the fly"""
    vault = tmp_path / "test_vault"
    vault.mkdir()

    doc = vault / "test_note.md"
    doc.write_text("""---
title: Test Note
---
# Test Content
""")
    return vault
```

**When to Use Each Approach**:
- **Use `test_data/fake_vault`**: For integration/E2E tests that need realistic, complex data
- **Create programmatic data**: For unit tests with specific, controlled test cases

**Adding Test Data to Git**:
```bash
# test_data/ is in .gitignore, so force-add it
git add -f test_data/fake_vault/
git add -f test_data/fake_emails/
git add -f test_data/fake_pdfs/

# Commit
git commit -m "test: Add realistic test data for E2E tests"
```

**Copying Test Data from Other Branches**:
```bash
# If test data exists in another feature branch
git checkout feature/005-semantic-routing -- test_data/fake_vault
git add -f test_data/fake_vault/
git commit -m "test: Copy fake test data from feature/005"
```

### Cleanup Between Test Sessions

**CRITICAL**: E2E tests MUST clean up data between test runs to prevent pollution.

#### Pattern 1: `autouse` Cleanup Fixture (Recommended)

```python
@pytest.fixture(autouse=True)
def cleanup_weaviate(self, weaviate_client):
    """Clean up Weaviate collection BEFORE each test."""
    # Run BEFORE test
    try:
        collection = weaviate_client.collections.get("TheMuses")
        collection.data.delete_many(
            where=Filter.by_property("sourceType").equal("obsidian")
        )
    except Exception:
        # Collection doesn't exist yet - this is fine for first test
        pass
    yield
    # No cleanup after - next test will clean before it runs
```

**Why This Works**:
- Cleans BEFORE each test (ensures isolation)
- Handles missing collection gracefully
- `autouse=True` runs automatically for every test
- No cleanup after test (next test will handle it)

#### Pattern 2: Manual Cleanup in Setup

```python
def setup_method(self):
    """Run before each test method"""
    self.cleanup_database()

def cleanup_database(self):
    """Delete all test data"""
    collection = self.weaviate_client.collections.get("TheMuses")
    collection.data.delete_many(
        where=Filter.by_property("sourceType").equal("obsidian")
    )
```

#### Pattern 3: Unique Test Identifiers

```python
@pytest.fixture
def test_vault(tmp_path):
    """Create unique vault per test"""
    # tmp_path is unique per test automatically
    vault = tmp_path / "test_vault_000"
    vault.mkdir()
    return vault
```

**When to Use Each**:
- **Pattern 1 (autouse)**: E2E tests with shared Weaviate collections
- **Pattern 2 (manual)**: Complex setup/teardown sequences
- **Pattern 3 (unique IDs)**: When you want data from all tests visible at once

### Common Cleanup Mistakes

❌ **WRONG: Only cleanup after tests**
```python
yield
# Cleanup after test - TOO LATE!
collection.data.delete_many(...)
```
**Problem**: Next test sees previous test's data

❌ **WRONG: No exception handling**
```python
collection = client.collections.get("TheMuses")
collection.data.delete_many(...)  # Fails if collection doesn't exist!
```
**Problem**: First test run fails

❌ **WRONG: Delete entire collection**
```python
client.collections.delete("TheMuses")
client.collections.create("TheMuses", ...)
```
**Problem**: Slow! Schema recreation is expensive

✅ **CORRECT: Cleanup before, handle exceptions**
```python
try:
    collection = client.collections.get("TheMuses")
    collection.data.delete_many(where=Filter.by_property("sourceType").equal("test"))
except Exception:
    pass  # Collection doesn't exist yet
yield
# No cleanup after
```

### Testing with Python-Side Filtering

**Context**: Weaviate filters (`.like()`, `.contains_any()`) have unexpected behavior (see [WEAVIATE_GOTCHAS.md](WEAVIATE_GOTCHAS.md)).

**Workaround for E2E Tests**:
```python
from types import SimpleNamespace

# Fetch all, filter in Python
all_results = collection.query.fetch_objects(limit=100)
results_list = [
    obj for obj in all_results.objects
    if obj.properties.get('sourceFile', '').endswith('/test_note.md')
]

# Create mock results object for compatibility
results = SimpleNamespace(objects=results_list)

# Now use results.objects as normal
assert len(results.objects) > 0
```

**When to Use**:
- Small to medium datasets (< 1000 objects)
- E2E/integration tests
- When Weaviate filters don't work as expected

**When to Avoid**:
- Large datasets (> 10k objects)
- Production code
- Performance-critical queries

See [WEAVIATE_GOTCHAS.md](WEAVIATE_GOTCHAS.md) for detailed troubleshooting.

## Docker Services for Testing

Start services locally:

```bash
# Start all services
docker-compose up -d

# Start specific services
docker-compose up weaviate postgres -d

# Check service health
curl http://localhost:8080/v1/.well-known/ready  # Weaviate
pg_isready -h localhost -p 5432 -U postgres      # PostgreSQL

# View logs
docker-compose logs -f weaviate
docker-compose logs -f postgres

# Stop services
docker-compose down
```

## Example: Adding Test for New Feature

### Step 1: Create User Story Test Outline

```python
# tests/unit/test_new_feature.py
"""
Unit tests for New Feature
Tests Story XXX: New Feature Description
"""
import pytest

@pytest.mark.unit
class TestNewFeature:
    """Test suite for new feature"""

    def test_basic_operation(self):
        """Test basic functionality works"""
        # TODO: Implement
        pass

    def test_edge_cases(self):
        """Test edge cases and error handling"""
        # TODO: Implement
        pass

    def test_performance(self):
        """Test meets performance targets"""
        # TODO: Implement
        pass
```

### Step 2: Implement Tests (TDD)

```python
@pytest.mark.unit
def test_basic_operation(temp_vault):
    """Test basic functionality works"""
    from MyModule.new_feature import NewFeature

    feature = NewFeature(vault_path=str(temp_vault))
    result = feature.process()

    assert result is not None
    assert result.status == "success"
```

### Step 3: Add Integration Test if Needed

```python
# tests/integration/test_new_feature_integration.py
@pytest.mark.integration
@pytest.mark.weaviate
def test_with_real_weaviate(weaviate_client, clean_weaviate_collection):
    """Test new feature with real Weaviate"""
    from MyModule.new_feature import NewFeature

    feature = NewFeature(weaviate_client=weaviate_client)
    result = feature.process()

    # Verify data in Weaviate
    collection = weaviate_client.collections.get("TestCollection")
    objects = collection.query.fetch_objects(limit=10)

    assert len(objects.objects) > 0
```

### Step 4: Run Tests

```bash
# Run just your new tests
pytest tests/unit/test_new_feature.py -v

# Run with coverage
pytest tests/unit/test_new_feature.py --cov=MyModule.new_feature

# Run full suite to ensure no regressions
pytest
```

## Common Testing Scenarios

### Testing Gatekeeper Approval

```python
@pytest.mark.unit
def test_gatekeeper_approval(mock_discovery):
    """Test project approval workflow"""
    from Alexandria.sql_gatekeeper import SQLProjectGatekeeper

    db = Mock()
    messenger = Mock()
    gatekeeper = SQLProjectGatekeeper(db, messenger)

    # Request approval
    gatekeeper.request_project_write(mock_discovery)

    # Verify notification sent
    messenger.send_message.assert_called_once()
    assert "Approval Request" in messenger.send_message.call_args[0][0]
```

### Testing Scout Discovery

```python
@pytest.mark.unit
def test_scout_detects_pattern(mock_cluster):
    """Test Scout identifies project candidates"""
    from Argus.scout import LatentScout

    scout = LatentScout(muses_client=Mock())
    patterns = scout.detect_patterns()

    assert "project_candidate" in patterns
    assert len(patterns["project_candidate"]) > 0
```

### Testing Weaviate Ingestion

```python
@pytest.mark.integration
@pytest.mark.weaviate
def test_ingest_to_weaviate(weaviate_client, clean_weaviate_collection, sample_chunks):
    """Test chunk ingestion into Weaviate"""
    # Create collection and insert data
    collection = weaviate_client.collections.create(...)

    # Verify insertion
    response = collection.query.fetch_objects(limit=10)
    assert len(response.objects) == len(sample_chunks)
```

## Resources

- **Full Test Documentation**: [`tests/README.md`](tests/README.md)
- **User Stories**: [`user-stories/STORY_INDEX.md`](user-stories/STORY_INDEX.md)
- **pytest Docs**: https://docs.pytest.org/
- **Weaviate Testing**: https://weaviate.io/developers/weaviate/client-libraries/python
- **PostgreSQL Testing**: https://www.psycopg.org/docs/

## Getting Help

- Check existing tests in `tests/unit/` for examples
- Review `conftest.py` for available fixtures
- See `tests/README.md` for detailed documentation
- GitHub Actions logs show CI test results
