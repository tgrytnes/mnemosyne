# Development Guide

Complete guide for contributing to Mnemosyne development.

---

## Setting Up Pre-commit Hooks

Pre-commit hooks enforce code quality before commits, preventing bad code from being pushed.

### Installation

```bash
# Install pre-commit (already in pyproject.toml dev dependencies)
poetry install --with dev

# Install git hooks
poetry run pre-commit install
```

### What Gets Checked

Every commit will automatically run:

- **Black**: Code formatting (line length 100)
- **Ruff**: Linting (pycodestyle, pyflakes, isort, pep8-naming, pyupgrade)
- **mypy**: Type checking (ignores missing imports)
- **Standard checks**: Trailing whitespace, YAML syntax, large files, merge conflicts, private keys

### Manual Run

```bash
# Run on all files
poetry run pre-commit run --all-files

# Run on staged files only
poetry run pre-commit run

# Run specific hook
poetry run pre-commit run black
```

### Example Output

```bash
$ git commit -m "Add new feature"

black....................................................................Passed
ruff.....................................................................Passed
mypy.....................................................................Passed
Trim Trailing Whitespace.................................................Passed
Fix End of Files.........................................................Passed
Check Yaml...............................................................Passed
Check for added large files..............................................Passed
Check for merge conflicts................................................Passed
Detect Private Key.......................................................Passed

[develop abc1234] Add new feature
 2 files changed, 45 insertions(+), 3 deletions(-)
```

### When Checks Fail

If a hook fails, the commit is blocked:

```bash
$ git commit -m "Add feature with formatting issues"

black....................................................................Failed
- hook id: black
- files were modified by this hook

reformatted src/mnemosyne/feature.py

All done! ✨ 🍰 ✨
1 file reformatted.

# Fix issues and try again
$ git add .
$ git commit -m "Add feature with formatting issues"
[develop abc1234] Add feature with formatting issues
```

### Bypassing Hooks (Discouraged)

```bash
# Only use in emergencies
git commit --no-verify -m "Emergency fix"
```

**Warning**: Bypassing hooks will cause CI to fail if code doesn't pass quality checks.

---

## Testing Workflow

See [TESTING.md](TESTING.md) for complete TDD workflow and testing guide.

### Quick Reference

```bash
# Unit tests (fast, no Docker required)
poetry run pytest tests/unit -m unit

# Integration tests (requires Docker services)
./scripts/run_integration_tests.sh

# All tests
poetry run pytest

# With coverage
poetry run pytest --cov=src/mnemosyne --cov-report=html
```

---

## CI/CD Pipeline

GitHub Actions runs automatically on every push and pull request.

### Workflow Jobs

1. **Unit Tests** (Python 3.11, 3.12)
   - Runs all unit tests
   - Generates coverage report
   - Fast (~3-5 minutes)

2. **Integration Tests** (Python 3.11)
   - Starts Docker services (Weaviate, Postgres, Ollama)
   - Pulls qwen3-embedding:0.6b model
   - Runs integration tests
   - Slower (~8-10 minutes first run, ~5-7 cached)

3. **Code Quality**
   - Black formatting check
   - Ruff linting
   - mypy type checking

4. **Test Summary**
   - Aggregates all results
   - Fails if any job fails

### Viewing Results

1. Go to your repository on GitHub
2. Click "Actions" tab
3. Select your workflow run
4. View logs for each job

### Local CI Simulation

```bash
# Run all checks that CI runs
poetry run black --check .
poetry run ruff check .
poetry run mypy . --ignore-missing-imports

# Run all tests
poetry run pytest tests/unit -m unit
./scripts/run_integration_tests.sh
```

---

## Code Quality Standards

### Formatting (Black)

- Line length: 100 characters
- Target Python version: 3.11
- Auto-formats on pre-commit

### Linting (Ruff)

Selected rules:
- **E**: pycodestyle errors
- **F**: pyflakes (unused imports, undefined variables)
- **I**: isort (import sorting)
- **N**: pep8-naming (naming conventions)
- **UP**: pyupgrade (modern Python syntax)

### Type Checking (mypy)

- Python version: 3.11
- Ignore missing imports (for now)
- Warn on unused configs
- `disallow_untyped_defs = false` (can be tightened later)

---

## Development Environment Setup

### Prerequisites

- Python 3.11+
- Poetry
- Docker Desktop (for integration tests)
- Git

### Initial Setup

```bash
# Clone repository
git clone <repository-url>
cd Mnemosyne

# Install dependencies
poetry install --with dev

# Set up pre-commit hooks
poetry run pre-commit install

# Copy environment template
cp .env.development .env

# Edit .env with your settings
nano .env
```

### Environment Variables

See [GETTING_STARTED.md](GETTING_STARTED.md) for complete environment configuration.

Key variables for development:
```bash
# Required
OBSIDIAN_VAULT_PATH="/path/to/your/vault"

# Optional (defaults shown)
WEAVIATE_HTTP_HOST="localhost"
WEAVIATE_HTTP_PORT="8080"
OLLAMA_BASE_URL="http://localhost:11434"
```

---

## Project Structure

```
mnemosyne/
├── src/mnemosyne/          # Source code
│   ├── aletheia/           # Input processing (ingestion)
│   ├── alexandria/         # Vector storage (Weaviate)
│   ├── argus/              # Pattern detection (clustering)
│   ├── iris/               # API/orchestration
│   ├── hermes/             # Notifications (Telegram)
│   ├── prometheus/         # Metrics/monitoring
│   ├── cli/                # CLI commands
│   └── common/             # Shared utilities
├── tests/
│   ├── unit/               # Unit tests (fast, isolated)
│   ├── integration/        # Integration tests (Docker required)
│   └── e2e/                # End-to-end tests (full workflows)
├── docs/                   # Documentation
├── scripts/                # Helper scripts
└── user-stories/           # User story specifications
```

---

## Making Changes

### Workflow

1. **Create feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Write tests first (TDD)**
   - See [TESTING.md](TESTING.md) for TDD workflow
   - RED → GREEN → REFACTOR cycle

3. **Implement feature**
   - Follow code quality standards
   - Add docstrings for public APIs

4. **Run tests**
   ```bash
   # Unit tests
   poetry run pytest tests/unit -m unit

   # Integration tests (if needed)
   ./scripts/run_integration_tests.sh
   ```

5. **Commit changes**
   ```bash
   git add .
   git commit -m "Add feature: brief description"
   # Pre-commit hooks run automatically
   ```

6. **Push and create PR**
   ```bash
   git push origin feature/your-feature-name
   # Create PR on GitHub
   ```

### Commit Message Format

```
<type>: <brief description>

<detailed description (optional)>

<footer (optional)>

🤖 Generated with Claude Code
Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `test`: Test changes
- `refactor`: Code refactoring
- `chore`: Build/tooling changes

---

## Troubleshooting

### Pre-commit Hooks Not Running

```bash
# Reinstall hooks
poetry run pre-commit uninstall
poetry run pre-commit install

# Verify installation
poetry run pre-commit run --all-files
```

### Black/Ruff/mypy Errors

```bash
# Auto-fix formatting
poetry run black .

# Auto-fix some linting issues
poetry run ruff check --fix .

# Check type issues
poetry run mypy . --ignore-missing-imports
```

### Integration Tests Failing

```bash
# Stop all containers
docker compose -f docker-compose.test.yml down

# Remove volumes
docker compose -f docker-compose.test.yml down -v

# Restart fresh
./scripts/run_integration_tests.sh
```

---

## Resources

- [GETTING_STARTED.md](GETTING_STARTED.md) - First-time setup
- [TESTING.md](TESTING.md) - TDD workflow and test guide
- [INTEGRATION_TESTING.md](INTEGRATION_TESTING.md) - Integration test setup
- [OBSIDIAN_INGESTION.md](OBSIDIAN_INGESTION.md) - Vault ingestion guide
- [DEPLOYMENT.md](DEPLOYMENT.md) - Deployment to Raspberry Pi

---

**Last Updated**: 2025-12-27
