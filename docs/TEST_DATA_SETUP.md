# Test Data Setup Guide

**For Feature Branch Developers**: How to get test data into your branch

## Quick Start

If you're on a feature branch and need test data:

```bash
# 1. Copy test data from feature/020 (has all the latest test data)
git checkout feature/020-hierarchical-structure-preservation -- test_data/

# 2. Force-add (test_data/ is in .gitignore)
git add -f test_data/

# 3. Commit
git commit -m "test: Copy test data for E2E/integration tests"

# 4. Verify
ls -la test_data/fake_vault/
```

**That's it!** Your feature branch now has all test data.

## Why Do We Need This?

**Problem**: `test_data/` is in `.gitignore` (to avoid committing large binary files by default)

**Solution**: Each feature branch that needs test data must explicitly force-add it

**Benefit**: Only branches that run E2E/integration tests include test data

## Which Branches Need Test Data?

✅ **YES - Add test data if your branch has**:
- E2E tests (`tests/e2e/`)
- Integration tests using real Obsidian vault
- Integration tests with real emails/PDFs
- Tests using `test_data/fake_vault/` fixtures

❌ **NO - Skip test data if your branch only has**:
- Unit tests (use programmatic fixtures)
- Tests using `tmp_path` fixtures
- Tests with mocked data

## Source of Truth

**Primary Branch**: `feature/020-hierarchical-structure-preservation`
- Has the most complete and up-to-date test data
- Includes all fake_vault, fake_emails, fake_pdfs
- All documentation for test data structure

**When to Update**:
- When adding new test files to `test_data/`
- When modifying existing test data
- Periodically (quarterly) to get latest updates

## Step-by-Step Setup

### Option 1: Copy from feature/020 (Recommended)

```bash
# Make sure you're on your feature branch
git checkout feature/your-feature-name

# Copy test data from feature/020
git checkout feature/020-hierarchical-structure-preservation -- test_data/

# Force-add (because test_data/ is in .gitignore)
git add -f test_data/

# Commit with descriptive message
git commit -m "test: Copy test data from feature/020 for E2E tests

Includes:
- fake_vault/ for Obsidian ingestion tests
- fake_emails/ for email processing tests
- fake_pdfs/ for PDF ingestion tests"

# Push to remote
git push origin feature/your-feature-name
```

### Option 2: Copy Specific Directories Only

If you only need certain test data:

```bash
# Copy only fake_vault
git checkout feature/020-hierarchical-structure-preservation -- test_data/fake_vault
git add -f test_data/fake_vault/
git commit -m "test: Copy fake_vault test data from feature/020"

# Or only fake_emails
git checkout feature/020-hierarchical-structure-preparation -- test_data/fake_emails
git add -f test_data/fake_emails/
git commit -m "test: Copy fake_emails test data from feature/020"
```

### Option 3: Create Minimal Test Data (Advanced)

If you only need a few files for specific tests:

```bash
# Create minimal structure
mkdir -p test_data/fake_vault/knowledge
echo "# Test Note" > test_data/fake_vault/knowledge/test.md

# Force-add
git add -f test_data/fake_vault/knowledge/test.md

# Commit
git commit -m "test: Add minimal test data for unit tests"
```

## Verifying Test Data

After copying, verify the structure:

```bash
# Check what was added
ls -la test_data/

# Expected structure:
# test_data/
# ├── README.md
# ├── fake_vault/
# │   ├── knowledge/
# │   ├── projects/
# │   └── journal/
# ├── fake_emails/
# └── fake_pdfs/

# Count files
find test_data -type f | wc -l
# Expected: ~138 files

# Check key files exist
test -f test_data/fake_vault/knowledge/dirty_note.md && echo "✓ dirty_note.md exists"
test -f test_data/README.md && echo "✓ README.md exists"
```

## Common Issues

### Issue 1: "test_data not found"

```bash
# Error: pathspec 'test_data/' did not match any file(s)
# Solution: Copy from feature/020 first

git checkout feature/020-hierarchical-structure-preservation -- test_data/
git add -f test_data/
```

### Issue 2: "Git refuses to add test_data/"

```bash
# Error: The following paths are ignored by one of your .gitignore files
# Solution: Use force-add (-f flag)

git add -f test_data/  # NOT: git add test_data/
```

### Issue 3: "Tests fail with FileNotFoundError"

Your tests are looking for test data that doesn't exist in your branch:

```bash
# Check if test data exists
ls test_data/fake_vault/

# If empty, copy from feature/020
git checkout feature/020-hierarchical-structure-preservation -- test_data/
git add -f test_data/
git commit -m "test: Copy missing test data"
```

### Issue 4: "Too many files in commit"

You accidentally committed the entire test_vault instead of fake_vault:

```bash
# Remove test_vault (keep only fake_vault)
git rm -r --cached test_data/test_vault/
git commit -m "test: Remove test_vault, keep only fake_vault"

# Re-add only fake_vault
git add -f test_data/fake_vault/
git commit --amend -m "test: Add fake_vault test data"
```

## Updating Test Data in Your Branch

If test data changes in feature/020 after you've already copied it:

```bash
# Get latest changes from feature/020
git fetch origin feature/020-hierarchical-structure-preservation

# Copy updated test data
git checkout origin/feature/020-hierarchical-structure-preservation -- test_data/

# Force-add updates
git add -f test_data/

# Commit
git commit -m "test: Update test data from feature/020"
```

## Adding New Test Data

If you create new test files for your feature:

### 1. Add to Your Branch

```bash
# Create new test file
echo "# New Test Data" > test_data/fake_vault/knowledge/new_feature.md

# Force-add
git add -f test_data/fake_vault/knowledge/new_feature.md

# Commit
git commit -m "test: Add test data for new feature"
```

### 2. Contribute Back to feature/020

After your feature is merged:

```bash
# Switch to feature/020
git checkout feature/020-hierarchical-structure-preservation

# Cherry-pick your test data commit
git cherry-pick <your-commit-hash>

# Or manually copy the file
git checkout feature/your-feature -- test_data/fake_vault/knowledge/new_feature.md
git add -f test_data/fake_vault/knowledge/new_feature.md
git commit -m "test: Add new_feature.md test data from feature/your-feature"

# Push to update feature/020
git push origin feature/020-hierarchical-structure-preservation
```

## Test Data Workflow

```
feature/020 (Source of Truth)
    ↓
    | git checkout feature/020 -- test_data/
    ↓
feature/your-feature (Copy)
    ↓
    | Make changes, add new test files
    ↓
feature/your-feature (Updated)
    ↓
    | After merge, contribute back
    ↓
feature/020 (Updated)
```

## Automation Script

Create this script to automate copying test data:

```bash
#!/bin/bash
# scripts/setup_test_data.sh

echo "Copying test data from feature/020..."

git checkout feature/020-hierarchical-structure-preservation -- test_data/

if [ $? -eq 0 ]; then
    echo "✓ Test data copied"
    git add -f test_data/
    echo "✓ Test data staged"
    echo ""
    echo "Next: git commit -m 'test: Copy test data from feature/020'"
else
    echo "✗ Failed to copy test data"
    exit 1
fi
```

Usage:
```bash
chmod +x scripts/setup_test_data.sh
./scripts/setup_test_data.sh
git commit -m "test: Copy test data from feature/020"
```

## CI/CD Considerations

**GitHub Actions**: Test data is automatically available in CI because the entire repository is checked out.

**Local Development**: You must manually copy test data to your branch.

**Docker Volumes**: When using Docker for tests, test_data/ is mounted as a volume automatically.

## Related Documentation

- [test_data/README.md](../test_data/README.md) - Detailed test data documentation
- [TESTING.md](TESTING.md) - Full testing guide
- [WEAVIATE_GOTCHAS.md](WEAVIATE_GOTCHAS.md) - Weaviate troubleshooting

## Summary

**One Command to Rule Them All**:
```bash
git checkout feature/020-hierarchical-structure-preservation -- test_data/ && \
git add -f test_data/ && \
git commit -m "test: Copy test data from feature/020"
```

Copy this to your feature branch, commit, and you're ready to run E2E tests!

---

**Last Updated**: 2025-12-29
**Source Branch**: feature/020-hierarchical-structure-preservation
**Maintainer**: Development Team
