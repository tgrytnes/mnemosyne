# Project Structure Proposal

## Current Structure (Unusual)

```
Mnemosyne/
├── Aletheia/           # Layer 1
├── Alexandria/         # Layer 2
├── Argus/              # Layer 3
├── Iris/               # Layer 4
├── Hermes/             # Layer 5
├── Prometheus/         # Layer 6
├── tests/
├── docs/
└── scripts/
```

**Problems**:
- ❌ Each layer is a separate top-level package
- ❌ No clear "source code" location
- ❌ Unusual for Python projects
- ❌ Hard to install as single package
- ❌ Confusing import paths (`from Aletheia import ...` vs `from mnemosyne.aletheia import ...`)

## Proposed Structure (Standard Python)

### Option 1: Single Package (Recommended)

```
Mnemosyne/
├── src/
│   └── mnemosyne/
│       ├── __init__.py
│       ├── aletheia/           # Layer 1: Input Processing
│       │   ├── __init__.py
│       │   ├── ingestor.py
│       │   ├── obsidian.py
│       │   ├── email.py
│       │   └── pdf.py
│       │
│       ├── alexandria/         # Layer 2: Storage & Governance
│       │   ├── __init__.py
│       │   ├── gates/
│       │   │   ├── __init__.py
│       │   │   ├── obsidian_gatekeeper.py
│       │   │   └── sql_gatekeeper.py
│       │   └── database/
│       │       ├── __init__.py
│       │       ├── weaviate.py
│       │       └── postgres.py
│       │
│       ├── argus/              # Layer 3: Subconscious
│       │   ├── __init__.py
│       │   ├── scout.py
│       │   └── curator.py
│       │
│       ├── iris/               # Layer 4: Intelligence Services
│       │   ├── __init__.py
│       │   └── router.py
│       │
│       ├── hermes/             # Layer 5: Interaction
│       │   ├── __init__.py
│       │   ├── telegram_bot.py
│       │   └── project_manager.py
│       │
│       ├── prometheus/         # Layer 6: Execution
│       │   ├── __init__.py
│       │   └── executor.py
│       │
│       ├── common/             # Shared utilities
│       │   ├── __init__.py
│       │   ├── config.py
│       │   ├── logging.py
│       │   └── utils.py
│       │
│       └── cli/                # Command-line interface
│           ├── __init__.py
│           └── main.py
│
├── tests/
│   ├── unit/
│   │   ├── test_aletheia/
│   │   ├── test_alexandria/
│   │   ├── test_argus/
│   │   └── ...
│   ├── integration/
│   └── e2e/
│
├── docs/
├── scripts/
├── user-stories/
├── pyproject.toml
├── README.md
└── IMPLEMENTATION_PLAN.md
```

**Benefits**:
- ✅ Standard Python package structure
- ✅ Clear imports: `from mnemosyne.aletheia import ObsidianIngestor`
- ✅ Easy to install: `pip install -e .`
- ✅ All code in one place (`src/mnemosyne/`)
- ✅ Follows PEP standards

### Option 2: Flat Structure (Simpler)

```
Mnemosyne/
├── mnemosyne/
│   ├── __init__.py
│   ├── aletheia/           # Layer 1
│   ├── alexandria/         # Layer 2
│   ├── argus/              # Layer 3
│   ├── iris/               # Layer 4
│   ├── hermes/             # Layer 5
│   ├── prometheus/         # Layer 6
│   └── common/
│
├── tests/
├── docs/
├── scripts/
├── pyproject.toml
└── README.md
```

**Benefits**:
- ✅ Simpler than src/ layout
- ✅ Still proper package structure
- ✅ Standard imports

**Drawbacks**:
- ⚠️ Package name conflicts with project name
- ⚠️ Less isolation than src/ layout

## Recommended: Option 1 (src/ layout)

### Why src/ layout?

1. **Industry standard** for modern Python projects
2. **Prevents accidental imports** from development directory
3. **Forces proper installation** before testing
4. **Clear separation** between source and other files
5. **Better for packaging** and distribution

### Import Examples

```python
# Current (confusing)
from Aletheia.ingestor import ObsidianIngestor

# Proposed (clear)
from mnemosyne.aletheia.ingestor import ObsidianIngestor
from mnemosyne.argus.scout import LatentScout
from mnemosyne.hermes.telegram_bot import TelegramBot
```

### Installation

```bash
# Install in development mode
pip install -e .

# Import anywhere
from mnemosyne.aletheia import ObsidianIngestor
```

## Migration Plan

### Step 1: Create new structure
```bash
mkdir -p src/mnemosyne
```

### Step 2: Move existing packages
```bash
mv Aletheia src/mnemosyne/aletheia
mv Alexandria src/mnemosyne/alexandria
mv Argus src/mnemosyne/argus
mv Iris src/mnemosyne/iris
mv Hermes src/mnemosyne/hermes
mv Prometheus src/mnemosyne/prometheus
```

### Step 3: Create package __init__.py
```bash
touch src/mnemosyne/__init__.py
```

### Step 4: Update pyproject.toml
```toml
[project]
name = "mnemosyne"
version = "0.1.0"

[tool.poetry]
packages = [{include = "mnemosyne", from = "src"}]
```

### Step 5: Update imports in tests
```python
# Old
from Aletheia.ingestor import ObsidianIngestor

# New
from mnemosyne.aletheia.ingestor import ObsidianIngestor
```

### Step 6: Update IMPLEMENTATION_PLAN.md references

## Alternative: Keep Current but Fix Naming

If you prefer the current structure, at least make it lowercase:

```
Mnemosyne/
├── aletheia/           # Lowercase (Python convention)
├── alexandria/
├── argus/
├── iris/
├── hermes/
├── prometheus/
├── tests/
└── docs/
```

**Benefit**: Less migration work
**Drawback**: Still unusual structure

## Recommendation

**Use Option 1 (src/ layout)** because:
1. You're just starting (no existing code to migrate)
2. Industry standard
3. Better for long-term maintenance
4. Easier to package and distribute later
5. Clear separation of source code

## Next Steps

1. **Decide**: src/ layout (Option 1) or flat layout (Option 2)?
2. **Create structure**: `mkdir -p src/mnemosyne/{aletheia,alexandria,argus,iris,hermes,prometheus,common}`
3. **Add __init__.py**: To each package
4. **Update pyproject.toml**: Package configuration
5. **Install**: `pip install -e .`
6. **Start coding**: Story 000 in `src/mnemosyne/aletheia/ingestor.py`

What do you prefer?
