# Testing Quick Reference

## Common Commands

```bash
# Quick test (unit tests only)
make test

# All tests with coverage
make test-all

# Start Docker services
make services-up

# Stop Docker services
make services-down

# Format and lint
make check
```

## Test File Template

```python
"""
Unit tests for ComponentName
Tests Story XXX: Story Title
"""
import pytest

@pytest.mark.unit
class TestComponentName:
    """Test suite for ComponentName"""

    def test_basic_functionality(self):
        """Test description in present tense"""
        # Arrange
        component = ComponentName()

        # Act
        result = component.do_something()

        # Assert
        assert result == expected
```

## Useful Fixtures

```python
# File system
temp_vault              # Temporary Obsidian vault
temp_shadow_vault       # Temporary shadow vault
sample_markdown_file    # Sample .md file

# Real services
weaviate_client         # Real Weaviate connection
ananke_test_db          # PostgreSQL test DB
ollama_client           # Real Ollama client

# Data
sample_chunks           # Sample text chunks
sample_email            # Sample email data
fake_vault_path         # Synthetic Obsidian vault
```

## Test Markers

```python
@pytest.mark.unit          # Unit test
@pytest.mark.integration   # Integration test
@pytest.mark.weaviate      # Needs Weaviate
@pytest.mark.postgres      # Needs PostgreSQL
@pytest.mark.slow          # >5 seconds
@pytest.mark.e2e           # End-to-end
```

## Run Specific Tests

```bash
# By marker
pytest -m unit
pytest -m integration
pytest -m "weaviate and integration"

# By file
pytest tests/unit/test_scout.py

# By class
pytest tests/unit/test_scout.py::TestPatternDetection

# By function
pytest tests/unit/test_scout.py::TestPatternDetection::test_detect_project_candidate

# By keyword
pytest -k "detect"

# Verbose
pytest -vv

# With coverage
pytest --cov=.
```

## Common Patterns

### Test File Operations

```python
def test_file_ops(temp_vault):
    test_file = temp_vault / "test.md"
    test_file.write_text("Content")
    assert test_file.read_text() == "Content"
```

### Test Exceptions

```python
with pytest.raises(ValueError) as exc:
    invalid_operation()

assert "error message" in str(exc.value)
```

## Coverage

```bash
# Terminal report
pytest --cov=. --cov-report=term-missing

# HTML report
pytest --cov=. --cov-report=html
open htmlcov/index.html
```

## Debugging

```bash
pytest -s          # Show print()
pytest -x          # Stop on first failure
pytest --pdb       # Drop into debugger
pytest --lf        # Run last failed tests
pytest --setup-show  # Show fixture setup
```

## Docker Services

```bash
# Start
docker-compose up weaviate postgres -d

# Check health
curl http://localhost:8080/v1/.well-known/ready
pg_isready -h localhost -p 5432 -U postgres

# Logs
docker-compose logs -f weaviate

# Stop
docker-compose down
```

## Story → Test Mapping

| Story | File | Focus |
|-------|------|-------|
| 000 | `test_ingestor.py` | Vault ingestion |
| 002 | `test_gatekeeper.py` | Obsidian gatekeeper |
| 005 | `test_router.py` | Semantic routing |
| 010 | `test_scout.py` | Pattern detection |
| 014 | `test_gatekeeper.py` | SQL gatekeeper |
| 016 | `test_project_manager.py` | Project management |

## CI Checks

What runs in GitHub Actions:
1. Unit tests (Python 3.11, 3.12)
2. Integration tests (with Docker)
3. Code quality (Black, Ruff, mypy)
4. Coverage report

## Environment Variables

For integration tests:

```bash
export TEST_WEAVIATE_HOST=localhost
export TEST_WEAVIATE_PORT=8080
export TEST_POSTGRES_HOST=localhost
export TEST_POSTGRES_PORT=5432
export TEST_POSTGRES_DB=ananke_test
```
