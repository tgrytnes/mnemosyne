# Linear Integration Guide

Complete guide for Linear integration with Mnemosyne.

## Overview

Mnemosyne uses **Linear as the source of truth for status** while keeping **detailed specifications in local markdown files**.

- **Linear**: Task status, assignments, progress tracking
- **Local Files**: Detailed requirements, technical specs, code examples

## Setup (One-Time)

### 1. Get Linear API Key

1. Visit: https://linear.app/settings/api
2. Click "Create new API key"
3. Name it "Mnemosyne Import"
4. Copy the key (starts with `lin_api_`)

### 2. Add to Environment

```bash
# Add to .env
echo "LINEAR_API_KEY=lin_api_xxxxxxxxxxxxx" >> .env
```

### 3. Import Stories to Linear

```bash
# Run import script
.venv/bin/python scripts/import_to_linear.py
```

**Result**: All 18 user stories created in Linear (PRO-5 through PRO-26)

## Daily Workflow

### Morning: Check Status

```bash
# View current progress
.venv/bin/python scripts/sync_from_linear.py --show-status
```

Output:
```
📊 Mnemosyne Project Status

Phase 0: 2/4 completed, 1 in progress
  ✅ [PRO-5] Story 000: Obsidian Vault Ingestion
  🔄 [PRO-6] Story 001: Email Archive Ingestion
  ⬜ [PRO-7] Story 002: Shadow Copy & Hygiene
  ⬜ [PRO-8] Story 003: PDF & OCR Ingestion

📈 Overall Progress: 8/18 completed (44.4%)
```

### During Development

1. **In Linear**: Move story to "In Progress" (e.g., PRO-5)
2. **Locally**: Read full spec from `user-stories/phase-0-ingestion-hygiene/story-000-*.md`
3. **Code**: Follow TDD workflow from IMPLEMENTATION_PLAN.md
4. **In Linear**: Check off acceptance criteria as you complete them
5. **In Linear**: Mark as "Done" when finished

### Evening: Sync Status

```bash
# Update local files with Linear status
.venv/bin/python scripts/sync_from_linear.py

# Commit progress
git add IMPLEMENTATION_PLAN.md
git commit -m "Sync: Story 000 completed"
git push
```

## Scripts

### Import to Linear

**File**: `scripts/import_to_linear.py`

**Purpose**: One-time import of all 18 user stories to Linear

**Usage**:
```bash
.venv/bin/python scripts/import_to_linear.py
```

**Creates**:
- 18 Linear issues (PRO-5 through PRO-26)
- 11 labels (Phase 0-5, Aletheia, Alexandria, Argus, Iris, Hermes)
- Story relationships (related stories linked)

**⚠️ Warning**: Running again creates **duplicates**. Only run once!

### Sync from Linear

**File**: `scripts/sync_from_linear.py`

**Purpose**: Sync status from Linear to local IMPLEMENTATION_PLAN.md

**Usage**:
```bash
# Show status only (no file changes)
.venv/bin/python scripts/sync_from_linear.py --show-status

# Update IMPLEMENTATION_PLAN.md checkboxes
.venv/bin/python scripts/sync_from_linear.py
```

**Updates**:
- Checkboxes in IMPLEMENTATION_PLAN.md
- Creates automatic backup before changes

## Linear Organization

### Labels

**Phase Labels** (timeline tracking):
- 🔴 Phase 0 - Ingestion & Hygiene
- 🔵 Phase 1 - Semantic Extraction
- 🟦 Phase 2 - Efficiency Engine
- 🟢 Phase 3 - Showcase
- 🟡 Phase 4 - Latent Scout
- ⚪ Phase 5 - Vault Curation

**Component Labels** (architecture):
- 🌿 Aletheia - Input Processing
- 🍊 Alexandria - Storage & Governance
- 🔴 Argus - Subconscious (Scout, Curator)
- 🟣 Iris - Intelligence Services
- 🔵 Hermes - Interaction (Telegram, Project Manager)

### Issue Content

Each Linear issue includes:
- Title: "Story XXX: [Story Name]"
- Description: User story + acceptance criteria + technical notes
- Labels: Phase + relevant component labels
- Relations: Links to related stories

## Status Mapping

| Linear State | Checkbox | Emoji | Meaning |
|--------------|----------|-------|---------|
| Backlog | `[ ]` | ⬜ | Not started |
| Todo | `[ ]` | ⬜ | Ready to work on |
| In Progress | `[ ]` | 🔄 | Currently working |
| In Review | `[ ]` | 🔄 | Under review |
| Done | `[x]` | ✅ | Completed |
| Canceled | `[ ]` | ❌ | Won't do |

**Note**: Only "Done"/"Completed" marks the checkbox as checked in IMPLEMENTATION_PLAN.md

## Recommended Linear Setup

### 1. Create Milestones

- **Milestone 1**: Phase 0 (Week 1-2) - PRO-5, PRO-6, PRO-7, PRO-8
- **Milestone 2**: Phase 1 (Week 3-4) - PRO-9, PRO-10, PRO-11
- **Milestone 3**: Phase 2 (Week 5-6) - PRO-12, PRO-13, PRO-14
- **Milestone 4**: Phase 3 (Week 7) - PRO-15, PRO-16, PRO-17
- **Milestone 5**: Phase 4 (Week 8-10) - PRO-18 through PRO-24
- **Milestone 6**: Phase 5 (Future) - PRO-25, PRO-26

### 2. Set Priorities

Based on critical path:
- **P0 (Highest)**: PRO-5 (Story 000)
- **P0**: PRO-6 (Story 001)
- **P0**: PRO-7 (Story 002)
- **P1**: PRO-18 (Story 010 - Scout)
- **P1**: PRO-22 (Story 014 - SQL Gatekeeper)
- **P1**: PRO-24 (Story 016 - Project Manager)

### 3. Create Views

- **By Phase**: Filter by phase labels
- **By Component**: Filter by component labels
- **Critical Path**: PRO-5 → PRO-6 → PRO-7 → PRO-18 → PRO-22 → PRO-24
- **Current Sprint**: Based on week in IMPLEMENTATION_PLAN.md

### 4. Configure Cycles

Set up 2-week sprint cycles:
- **Cycle 1** (Week 1-2): Phase 0
- **Cycle 2** (Week 3-4): Phase 1
- **Cycle 3** (Week 5-6): Phase 2
- **Cycle 4** (Week 7-8): Phase 3 + start Phase 4
- **Cycle 5** (Week 9-10): Complete Phase 4

## Troubleshooting

### Can't See Stories in Linear

1. **Check team**: Make sure you're viewing "Project_Mnemosyne"
2. **Check filters**: Enable "Backlog" status in filters
3. **Direct link**: Try https://linear.app/project-mnemosyne/issue/PRO-5
4. **Search**: Search for "Story 000" in Linear search bar

### API Key Errors

```bash
# Verify key is set
grep LINEAR_API_KEY .env

# Test connection
.venv/bin/python scripts/sync_from_linear.py --show-status
```

### Sync Not Working

```bash
# Check for backup file
ls -la IMPLEMENTATION_PLAN.md.backup

# Restore if needed
cp IMPLEMENTATION_PLAN.md.backup IMPLEMENTATION_PLAN.md

# Re-run sync
.venv/bin/python scripts/sync_from_linear.py
```

## Best Practices

### ✅ DO

- Update story status in Linear (move to In Progress, Done, etc.)
- Sync regularly to keep local files updated (`make sync` could be added)
- Commit IMPLEMENTATION_PLAN.md changes to track progress over time
- Use `--show-status` to check progress without modifying files
- Read detailed specs from `user-stories/*.md` files

### ❌ DON'T

- Don't manually edit checkboxes in IMPLEMENTATION_PLAN.md (sync from Linear instead)
- Don't delete local `user-stories/` markdown files (detailed specs needed)
- Don't re-run import script (creates duplicates)
- Don't edit Linear issue descriptions (read from markdown files)
- Don't forget to sync before committing

## Automation Ideas

### Git Hook (Auto-sync before commit)

```bash
# Create pre-commit hook
cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
.venv/bin/python scripts/sync_from_linear.py
git add IMPLEMENTATION_PLAN.md
EOF

chmod +x .git/hooks/pre-commit
```

### Cron Job (Daily sync)

```bash
# Edit crontab
crontab -e

# Add daily sync at 9 AM
0 9 * * * cd /home/tgrytnes/projects/Mnemosyne && .venv/bin/python scripts/sync_from_linear.py
```

### Makefile Target

Add to Makefile:
```makefile
sync:
	@echo "Syncing from Linear..."
	.venv/bin/python scripts/sync_from_linear.py
```

Usage: `make sync`

## Quick Reference

| Task | Command |
|------|---------|
| **Check status** | `.venv/bin/python scripts/sync_from_linear.py --show-status` |
| **Sync to local** | `.venv/bin/python scripts/sync_from_linear.py` |
| **View in Linear** | https://linear.app/project-mnemosyne |
| **Read story spec** | `cat user-stories/phase-X/story-XXX-*.md` |
| **Implementation timeline** | `cat IMPLEMENTATION_PLAN.md` |

## Files Overview

```
Mnemosyne/
├── scripts/
│   ├── import_to_linear.py      # One-time import (DONE ✅)
│   └── sync_from_linear.py      # Daily sync (USE THIS)
│
├── user-stories/                 # Detailed specifications
│   ├── phase-0-ingestion-hygiene/
│   │   ├── story-000-*.md
│   │   ├── story-001-*.md
│   │   └── ...
│   └── ...
│
├── IMPLEMENTATION_PLAN.md        # Synced from Linear (checkboxes)
└── .env                          # Contains LINEAR_API_KEY
```

---

## Summary

**Setup**: One-time import creates 18 Linear issues ✅

**Daily Workflow**:
1. Morning: `sync --show-status` to see progress
2. Work: Update Linear as you complete tasks
3. Evening: `sync` to update local files
4. Commit: Track progress in git

**Result**: Linear holds current status, local files hold detailed specs, everyone stays in sync!
