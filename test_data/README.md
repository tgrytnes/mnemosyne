# Test Data for Mnemosyne

This directory contains realistic test data used by integration and E2E tests.

## ⚠️ Important Notes

1. **`.gitignore` Override Required**
   - This directory is in `.gitignore`
   - Test data MUST be force-added: `git add -f test_data/`

2. **Purpose**
   - Integration tests: Realistic, complex data
   - E2E tests: Real-world scenarios
   - NOT for unit tests (use programmatic fixtures)

3. **Size Limits**
   - Keep individual files < 1MB
   - Total test_data/ < 10MB
   - Use `.gitattributes` for binary files

## Directory Structure

```
test_data/
├── fake_vault/          # Obsidian markdown files (Story 000, 020)
│   ├── knowledge/       # Knowledge base notes
│   │   ├── dirty_note.md         # Wiki-links, HTML, emojis
│   │   ├── project_alpha.md      # Multi-level headings
│   │   └── weaviate_schema.md    # Technical docs
│   ├── dailies/         # Daily notes
│   │   └── 2024-01-15.md
│   └── projects/        # Project notes
│       └── mnemosyne.md
├── fake_emails/         # Email test data (Story 008)
│   ├── spam_001.eml
│   ├── valid_email.eml
│   └── thread_001.eml
└── fake_pdfs/           # PDF test documents (Future)
    ├── research_paper.pdf
    └── invoice_sample.pdf
```

## fake_vault/ - Obsidian Test Data

**Purpose**: Test Obsidian ingestion, markdown cleaning, structure preservation

**Key Files**:

### `knowledge/dirty_note.md`
Tests markdown cleaning features:
- Frontmatter (tags, metadata)
- Wiki-links: `[[project_alpha]]`, `[[alpha_notes|Alpha Notes]]`
- Embedded files: `![[diagram.png]]`
- HTML blocks: `<div>`, `<!-- comments -->`
- Obsidian metadata: `priority:: high`, `status:: draft`
- Emoji markers: 📌 🎯 💡 ⚡
- ChatGPT code blocks (custom syntax)

**Used By**:
- `tests/integration/test_markdown_cleaning.py`
- `tests/e2e/test_story_000_e2e.py`

### `knowledge/project_alpha.md`
Tests structure preservation:
- Multi-level headings (6 levels)
- Nested sections
- Heading path generation
- Document outline navigation

**Used By**:
- `tests/integration/test_structure_preservation_*.py`
- `tests/e2e/test_story_020_e2e.py`

### `knowledge/weaviate_schema.md`
Technical documentation with:
- Code blocks
- Lists and tables
- Complex formatting

**Used By**:
- General ingestion tests
- Chunking tests

## fake_emails/ - Email Test Data

**Purpose**: Test email ingestion and processing (Story 008)

**Files**:
- `spam_001.eml` - Spam detection
- `valid_email.eml` - Normal email
- `thread_001.eml` - Email thread

**Format**: Standard `.eml` format with headers + body

## fake_pdfs/ - PDF Test Documents

**Purpose**: Test PDF ingestion (Future story)

**Files**:
- `research_paper.pdf` - Multi-page academic paper
- `invoice_sample.pdf` - Invoice with tables

## Usage in Tests

### Option 1: Use Fake Vault Directly

```python
from pathlib import Path

@pytest.fixture
def test_vault():
    """Use the real fake_vault test data"""
    return Path("test_data/fake_vault")

def test_ingestion(test_vault):
    ingestor = ObsidianIngestor(vault_path=str(test_vault))
    stats = ingestor.ingest_vault()
    assert stats["files_processed"] > 0
```

### Option 2: Create Programmatic Data

```python
@pytest.fixture
def test_vault(tmp_path):
    """Create test vault on the fly"""
    vault = tmp_path / "test_vault"
    vault.mkdir()

    doc = vault / "test_note.md"
    doc.write_text("""---
title: Test Note
tags: [test]
---
# Test Content

This is a [[wiki-link]] with content.
""")
    return vault
```

**When to Use Each**:
- **Fake vault**: Integration/E2E tests needing realistic complexity
- **Programmatic**: Unit tests with specific, controlled scenarios

## Adding New Test Data

### 1. Create the File

```bash
# Add to appropriate directory
echo "# New Test File" > test_data/fake_vault/knowledge/new_file.md
```

### 2. Force-Add to Git

```bash
# test_data/ is in .gitignore
git add -f test_data/fake_vault/knowledge/new_file.md
git commit -m "test: Add new_file.md test data"
```

### 3. Document in This README

Add entry explaining what the file tests and which tests use it.

### 4. Keep Files Small

- Text files: < 100KB
- Binary files: < 1MB
- Total directory: < 10MB

## Copying Test Data Between Branches

If test data exists in another feature branch:

```bash
# Copy from another branch
git checkout feature/005-semantic-routing -- test_data/fake_vault

# Force-add to current branch
git add -f test_data/fake_vault/

# Commit
git commit -m "test: Copy fake test data from feature/005"
```

## Cleaning Test Data from Weaviate

After running E2E tests, clean up Weaviate:

```bash
# Clean all test data
./scripts/clean_test_data.sh

# Clean only Obsidian data
./scripts/clean_test_data.sh --obsidian

# Clean specific collection
./scripts/clean_test_data.sh --collection MyCollection
```

Or use Docker:

```bash
# Nuclear option - restart Weaviate
docker-compose restart weaviate
```

## Best Practices

### ✅ DO

- Use realistic, complex test data for integration/E2E tests
- Create programmatic fixtures for unit tests
- Force-add test data to git: `git add -f test_data/`
- Keep files small and focused
- Document what each file tests
- Clean up between test runs

### ❌ DON'T

- Don't add large files (> 1MB)
- Don't add sensitive/private data
- Don't add generated files (use fixtures)
- Don't forget to force-add to git
- Don't assume test data is in other branches
- Don't leave test data in Weaviate between sessions

## Troubleshooting

### "Test data not found"

```bash
# Check if test_data exists
ls -la test_data/

# If missing, copy from another branch
git checkout feature/005-semantic-routing -- test_data/
git add -f test_data/
```

### "E2E tests fail with unexpected data"

Weaviate has leftover data from previous runs:

```bash
# Clean Weaviate
./scripts/clean_test_data.sh

# Or restart Weaviate
docker-compose restart weaviate
```

### "Git won't add test_data/"

The directory is in `.gitignore`, use force-add:

```bash
git add -f test_data/fake_vault/
```

## Related Documentation

- [TESTING.md](../docs/TESTING.md) - Full testing guide
- [WEAVIATE_GOTCHAS.md](../docs/WEAVIATE_GOTCHAS.md) - Weaviate troubleshooting
- [clean_test_data.sh](../scripts/clean_test_data.sh) - Cleanup script

## Test Data Maintenance

**Review Quarterly**:
- Remove unused test files
- Update files to reflect current features
- Check file sizes
- Update documentation

**When Adding New Stories**:
- Add test data if needed
- Document in this README
- Force-add to git
- Update relevant tests

---

**Last Updated**: 2025-12-29
**Maintainer**: Development Team
