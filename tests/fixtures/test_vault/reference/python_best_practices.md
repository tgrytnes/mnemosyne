# Python Best Practices

## Code Quality Tools

### Black (Formatting)
```bash
# Format all files
black src/

# Check without modifying
black --check src/
```

### Ruff (Linting)
```bash
# Lint and auto-fix
ruff check --fix src/

# Check specific rules
ruff check --select E501,F401 src/
```

### mypy (Type Checking)
```bash
# Type check with strict mode
mypy --strict src/

# Ignore missing imports
mypy --ignore-missing-imports src/
```

## Testing Patterns

### Fixtures
```python
import pytest

@pytest.fixture
def sample_data():
    return {"key": "value"}

def test_example(sample_data):
    assert sample_data["key"] == "value"
```

### Parametrize
```python
@pytest.mark.parametrize("input,expected", [
    (1, 2),
    (2, 4),
    (3, 6),
])
def test_double(input, expected):
    assert input * 2 == expected
```

## Project Structure

```
project/
├── src/
│   └── package/
│       ├── __init__.py
│       └── module.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── pyproject.toml
└── README.md
```

## Dependencies

Use Poetry for dependency management:
```bash
poetry add requests
poetry add --group dev pytest black ruff
poetry install
```

#python #reference #development
