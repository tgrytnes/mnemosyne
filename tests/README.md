# Mnemosyne Test Suite

Comprehensive testing infrastructure for the Mnemosyne knowledge management system.

## Test Structure

```
tests/
├── unit/                    # Fast, isolated unit tests
│   ├── test_ingestor.py    # Layer 1: Input Processing
│   ├── test_gatekeeper.py  # Layer 2: The Gates
│   ├── test_scout.py       # Layer 3: Argus
│   └── test_project_manager.py  # Layer 5: Hermes
├── integration/             # Tests requiring external services
│   ├── test_weaviate_integration.py
│   └── test_postgres_integration.py
├── e2e/                     # End-to-end workflow tests
├── fixtures/                # Shared test data
└── conftest.py              # Pytest fixtures and configuration
```

## Running Tests

### Prerequisites

1. **Install dependencies:**
   ```bash
   poetry install --with dev
   ```

2. **For integration tests, start services:**
   ```bash
   docker-compose up weaviate postgres -d
   ```

### Run All Tests

```bash
# All tests (unit + integration)
poetry run pytest

# With coverage report
poetry run pytest --cov=. --cov-report=html
```

### Run by Category

```bash
# Unit tests only (no external dependencies)
poetry run pytest -m unit

# Integration tests (requires Docker services)
poetry run pytest -m integration

# Exclude slow tests
poetry run pytest -m "not slow"

# Specific layer tests
poetry run pytest tests/unit/test_ingestor.py -v
```

### Run by Story

Tests are organized by user story implementation:

```bash
# Story 000: Obsidian Vault Ingestion
pytest tests/unit/test_ingestor.py -v

# Story 002 & 014: Gatekeepers
pytest tests/unit/test_gatekeeper.py -v

# Story 010: Scout Pattern Detection
pytest tests/unit/test_scout.py -v

# Story 016: Project Manager
pytest tests/unit/test_project_manager.py -v
```

## Test Markers

Tests are tagged with markers for selective execution:

- `@pytest.mark.unit` - Fast unit tests, no external dependencies
- `@pytest.mark.integration` - Requires Docker services (Weaviate, PostgreSQL)
- `@pytest.mark.e2e` - End-to-end workflow tests
- `@pytest.mark.slow` - Long-running tests (>5 seconds)
- `@pytest.mark.weaviate` - Requires Weaviate
- `@pytest.mark.postgres` - Requires PostgreSQL
- `@pytest.mark.telegram` - Requires Telegram API

Note: Tests should use real services (Ollama, Weaviate, PostgreSQL) where applicable. Avoid mocks.

## Writing Tests

### Integration Test Example

```python
import pytest

@pytest.mark.integration
@pytest.mark.weaviate
def test_insert_chunks(weaviate_client, clean_weaviate_collection):
    """Test inserting chunks into Weaviate"""
    collection = weaviate_client.collections.create(
        name="TestCollection",
        vectorizer_config=wvc.config.Configure.Vectorizer.none()
    )

    # Test implementation...
```

### Using Fixtures

Common fixtures from `conftest.py`:

```python
def test_with_vault(temp_vault):
    """Use temporary Obsidian vault"""
    # temp_vault is a Path object with sample notes

def test_with_database(ananke_test_db):
    """Use test PostgreSQL database"""
    # Database with projects and audit tables
```

## Coverage

Generate coverage reports:

```bash
# Terminal report
poetry run pytest --cov=. --cov-report=term-missing

# HTML report (opens in browser)
poetry run pytest --cov=. --cov-report=html
open htmlcov/index.html

# XML report (for CI)
poetry run pytest --cov=. --cov-report=xml
```

## Continuous Integration

Tests run automatically on GitHub Actions:

- **Unit Tests**: Python 3.11 and 3.12
- **Integration Tests**: With Weaviate and PostgreSQL services
- **Code Quality**: Black, Ruff, mypy

View results at: `.github/workflows/test.yml`

## Test Data

### Fake Test Data

```
test_data/fake_vault/   # Synthetic Obsidian vault
test_data/fake_emails/  # Synthetic email fixtures
test_data/fake_pdfs/    # Synthetic PDFs for OCR tests
```

### Creating Test Data

```python
# Temporary vault (auto-cleaned)
def test_with_temp_vault(temp_vault):
    note = temp_vault / "test.md"
    note.write_text("# Test Note")

# Sample markdown
def test_with_markdown(sample_markdown_file):
    content = sample_markdown_file.read_text()
```

## Performance Testing

Benchmark tests ensure performance targets:

```python
@pytest.mark.slow
def test_ingestion_performance(temp_vault):
    """Test ingestion meets 3-4 files/min target"""
    import time

    start = time.time()
    ingestor.ingest_vault()
    duration = time.time() - start

    rate = file_count / (duration / 60)
    assert rate >= 3.0, f"Too slow: {rate:.2f} files/min"
```

## Debugging Tests

```bash
# Verbose output
pytest -vv

# Show print statements
pytest -s

# Drop into debugger on failure
pytest --pdb

# Run specific test
pytest tests/unit/test_scout.py::TestPatternDetection::test_detect_project_candidate -v

# Show fixture setup
pytest --setup-show
```

## Common Issues

### Weaviate Connection Failed

```bash
# Start Weaviate
docker-compose up weaviate -d

# Check status
curl http://localhost:8080/v1/.well-known/ready

# View logs
docker-compose logs weaviate
```

### PostgreSQL Connection Failed

```bash
# Start PostgreSQL
docker-compose up postgres -d

# Check connection
psql -h localhost -U postgres -d ananke_test

# Reset database
docker-compose down postgres
docker-compose up postgres -d
```

### Import Errors

```bash
# Ensure packages are installed
poetry install --with dev

# Check PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

## Best Practices

1. **Test Organization**
   - One test file per component
   - Group related tests in classes
   - Use descriptive test names

2. **Test Independence**
   - Each test should be independent
   - Use fixtures for setup/teardown
   - Clean up resources

3. **Services**
   - Use real Ollama and Weaviate for integration/e2e coverage
   - Seed with `test_data/fake_vault` before workflows that depend on retrieval
   - Keep tests explicit about fresh vs. existing collections

4. **Assertions**
   - One logical assertion per test
   - Use descriptive failure messages
   - Test both success and failure paths

5. **Performance**
   - Keep unit tests fast (<1s each)
   - Mark slow tests with `@pytest.mark.slow`
   - Use caching for expensive setup

## Related Documentation

- [User Stories](../user-stories/STORY_INDEX.md) - Requirements for each feature
- [Architecture](../user-stories/SYSTEM_ARCHITECTURE.md) - System design
- [pytest Documentation](https://docs.pytest.org/) - Testing framework
- [GitHub Actions](../.github/workflows/test.yml) - CI configuration
