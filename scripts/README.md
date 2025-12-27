# Mnemosyne Scripts

Utility scripts for Mnemosyne project management.

## Available Scripts

### Linear Integration

#### `import_to_linear.py`
**Purpose**: One-time import of all user stories to Linear

```bash
.venv/bin/python scripts/import_to_linear.py
```

**Creates**:
- 18 Linear issues (PRO-5 through PRO-26)
- Phase and component labels
- Story relationships

**⚠️ Note**: Only run once! Re-running creates duplicates.

#### `sync_from_linear.py`
**Purpose**: Sync issue status from Linear to local files

```bash
# Show status only
.venv/bin/python scripts/sync_from_linear.py --show-status

# Update IMPLEMENTATION_PLAN.md
.venv/bin/python scripts/sync_from_linear.py
```

**Updates**: Checkboxes in IMPLEMENTATION_PLAN.md based on Linear status

### Test Data Setup

#### `setup_test_data.sh`
**Purpose**: Create test data subset for rapid development

```bash
./setup_test_data.sh
```

**Creates**:
- `test_data/test_vault/` - 50 markdown files
- `test_data/cleaned_emails_sample.tsv` - 1,000 emails

---

## Documentation

For detailed usage, see:
- **Linear Integration**: [../docs/LINEAR_INTEGRATION.md](../docs/LINEAR_INTEGRATION.md)
- **Testing**: [../docs/TESTING.md](../docs/TESTING.md)
- **Deployment**: [../docs/DEPLOYMENT.md](../docs/DEPLOYMENT.md)
