# Test Vault - README

This is a representative test vault for Mnemosyne integration tests.

## Structure

```
test_vault/
├── daily_notes/          # Daily journal entries
├── projects/             # Project ideas and documentation
├── reference/            # Reference materials and book notes
├── quick_notes/          # Short notes and meeting minutes
├── personal/             # Personal reflections and reviews
├── edge_cases/           # Malformed markdown and special characters
└── archived/             # Old projects and abandoned ideas
```

## Content Summary

- **Total files**: 15 markdown files
- **Content types**:
  - Daily notes (2)
  - Project documentation (3)
  - Reference materials (2)
  - Quick notes (2)
  - Personal reflections (2)
  - Edge cases (3)
  - Archived content (1)

## Testing Coverage

This vault tests:

1. **Document Structure**:
   - Various heading levels (# through ###)
   - Code blocks (Python, Bash)
   - Lists (bullet, numbered, tasks)
   - Tables
   - Blockquotes
   - Links and images

2. **Content Types**:
   - Technical documentation
   - Personal reflections
   - Meeting notes
   - Book summaries
   - Project ideas

3. **Edge Cases**:
   - Malformed markdown (unclosed code blocks)
   - Unicode and emoji
   - Very long documents (>5000 chars)
   - Special characters

4. **Realistic Patterns**:
   - Wiki-links: `[[other_note]]`
   - Tags: `#topic #category`
   - Task lists: `- [ ]` and `- [x]`
   - Code snippets

## Usage in Tests

```python
import pytest
from pathlib import Path

@pytest.fixture
def test_vault_path():
    return Path(__file__).parent / "fixtures" / "test_vault"

def test_vault_ingestion(test_vault_path, ingestor):
    result = ingestor.ingest(test_vault_path)

    assert result.files_processed == 15
    assert result.chunks_created > 50  # Approximate
    assert result.errors == 0
```

## Privacy

This vault contains **no real private information**. All content is hand-crafted for testing purposes.
