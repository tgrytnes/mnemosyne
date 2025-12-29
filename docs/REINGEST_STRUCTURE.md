# Re-Ingestion Guide: Adding Structure Metadata

This guide explains how to add structure metadata (headingPath, headingLevel, sectionTitle) to existing chunks that were ingested before Story 020.

## When Do You Need This?

**Use this script if**:
- You have existing chunks in Weaviate from before Story 020
- Those chunks lack structure metadata (headingPath is null)
- You want to query by heading path without re-embedding

**Skip this script if**:
- All your chunks were ingested after Story 020
- You're okay with re-ingesting from scratch
- You don't need backward compatibility

## Prerequisites

1. **Weaviate Running**
   ```bash
   docker-compose up weaviate -d
   ```

2. **Original Files Available**
   - The script needs to read original markdown files
   - Files must be at the paths stored in `sourceFile` property

3. **Backup Recommended**
   ```bash
   # Export current Weaviate data (optional but recommended)
   python scripts/backup_weaviate.py --collection TheMuses
   ```

## Quick Start

### Dry Run (Preview Changes)

Always start with a dry run to see what will be changed:

```bash
python scripts/reingest_with_structure.py --dry-run
```

**Expected Output**:
```
2025-12-29 10:00:00 - INFO - Connecting to Weaviate...
2025-12-29 10:00:00 - INFO - ✓ Connected to Weaviate
2025-12-29 10:00:01 - INFO - Fetching chunks with sourceType=obsidian...
2025-12-29 10:00:02 - INFO - Fetched 150 chunks
2025-12-29 10:00:02 - INFO - Processing 25 unique files
2025-12-29 10:00:03 - INFO - Processing /vault/knowledge/note1.md (6 chunks)...
2025-12-29 10:00:03 - INFO - [DRY RUN] Would update 6 chunks
...
============================================================
Re-Ingestion Summary
============================================================
Files processed: 25
Chunks updated: 150
Chunks failed: 0
Files not found: 0
============================================================

⚠️  DRY RUN - No changes were made to Weaviate
```

### Run Re-Ingestion

If the dry run looks good, run the actual re-ingestion:

```bash
python scripts/reingest_with_structure.py
```

**What Happens**:
1. Fetches all chunks with `sourceType=obsidian`
2. Groups chunks by `sourceFile`
3. For each file:
   - Reads original markdown
   - Extracts document structure
   - Assigns headingPath, headingLevel, sectionTitle to chunks
   - Updates chunks in Weaviate (preserves embeddings!)

## Options

### Source Type

Re-ingest specific source types:

```bash
# Obsidian only (default)
python scripts/reingest_with_structure.py --source-type obsidian

# Emails (if you add email structure extraction later)
python scripts/reingest_with_structure.py --source-type email

# PDFs
python scripts/reingest_with_structure.py --source-type pdf
```

### Collection Name

Specify a different Weaviate collection:

```bash
python scripts/reingest_with_structure.py --collection MyCollection
```

### Verbose Logging

Get detailed logging for debugging:

```bash
python scripts/reingest_with_structure.py --verbose
```

### Weaviate URL

Connect to a different Weaviate instance:

```bash
python scripts/reingest_with_structure.py --weaviate-url http://weaviate.prod:8080
```

## Verification

After re-ingestion, verify the structure metadata was added:

```python
import weaviate
from weaviate.classes.query import Filter

# Connect
client = weaviate.connect_to_local(host="localhost", port=8080)
collection = client.collections.get("TheMuses")

# Query chunks with structure
results = collection.query.fetch_objects(
    filters=Filter.by_property("headingLevel").greater_than(0),
    limit=10
)

# Check structure metadata
for obj in results.objects:
    props = obj.properties
    print(f"sourceFile: {props['sourceFile']}")
    print(f"headingPath: {props['headingPath']}")
    print(f"headingLevel: {props['headingLevel']}")
    print(f"sectionTitle: {props['sectionTitle']}")
    print("---")

client.close()
```

**Expected Output**:
```
sourceFile: /vault/knowledge/project_alpha.md
headingPath: # Project Alpha > ## Setup > ### Installation
headingLevel: 3
sectionTitle: Installation
---
sourceFile: /vault/knowledge/project_alpha.md
headingPath: # Project Alpha > ## Usage
headingLevel: 2
sectionTitle: Usage
---
```

## What Gets Updated

**Updated Properties**:
- `headingPath` - Full heading path (e.g., "# Docs > ## API > ### Auth")
- `headingLevel` - Heading level 1-6 (0 if no heading)
- `sectionTitle` - Immediate parent heading title

**Preserved Properties**:
- `text` - Chunk text (unchanged)
- `sourceFile` - Original file path (unchanged)
- `chunkIndex` - Chunk position (unchanged)
- `ingestedAt` - Original ingestion timestamp (unchanged)
- **Vector/Embedding** - Preserved! No re-embedding needed

## Troubleshooting

### "File not found" Errors

**Problem**: Original markdown files moved or deleted

**Solution**:
```bash
# Check which files are missing
python scripts/reingest_with_structure.py --verbose --dry-run 2>&1 | grep "not found"

# Option 1: Move files back to original locations
# Option 2: Update sourceFile property in Weaviate
# Option 3: Re-ingest those files from scratch
```

### "Could not locate chunk in original text"

**Problem**: Chunk text doesn't match original file (file was modified)

**Impact**: Chunk will be updated but structure might be incorrect

**Solution**:
```bash
# For modified files, re-ingest from scratch
python -m mnemosyne.cli.ingest /path/to/vault --force
```

### "Failed to update chunk" Errors

**Problem**: Weaviate connection issues or schema problems

**Solution**:
```bash
# Check Weaviate is running
curl http://localhost:8080/v1/.well-known/ready

# Check schema has structure fields
python -c "
import weaviate
client = weaviate.connect_to_local()
schema = client.collections.get('TheMuses').config.get()
print([p.name for p in schema.properties])
client.close()
"
# Should include: headingPath, headingLevel, sectionTitle
```

### Partial Completion

If the script is interrupted:

```bash
# Check how many chunks already have structure
python -c "
import weaviate
from weaviate.classes.query import Filter

client = weaviate.connect_to_local()
collection = client.collections.get('TheMuses')

# Count chunks with structure
with_structure = collection.query.fetch_objects(
    filters=Filter.by_property('headingPath').is_none(False),
    limit=1
).total_count

# Count chunks without structure
without_structure = collection.query.fetch_objects(
    filters=Filter.by_property('headingPath').is_none(True),
    limit=1
).total_count

print(f'With structure: {with_structure}')
print(f'Without structure: {without_structure}')
client.close()
"

# Re-run the script - it will update all chunks including already-updated ones
python scripts/reingest_with_structure.py
```

## Performance

**Typical Performance**:
- ~10 files/second
- ~50 chunks/second
- 1000 chunks ≈ 20 seconds

**Factors**:
- File I/O (reading original markdown)
- Structure extraction (parsing headings)
- Weaviate updates (network)

**No Re-Embedding**: The script ONLY updates metadata, embeddings are preserved. This makes it much faster than full re-ingestion.

## Comparison: Re-Ingest vs Full Re-Ingestion

| Aspect | Re-Ingest Script | Full Re-Ingestion |
|--------|------------------|-------------------|
| Speed | Fast (~50 chunks/sec) | Slow (~2 chunks/sec) |
| Embeddings | Preserved | Re-generated |
| Chunk Text | Preserved | Re-created |
| Chunk Index | Preserved | Re-created |
| Use Case | Add structure to existing | Start from scratch |

**When to use Full Re-Ingestion**:
- Original files were significantly modified
- Chunking strategy changed
- Embedding model changed
- Want fresh embeddings

**When to use Re-Ingest Script**:
- Just adding structure metadata
- Files haven't changed
- Want to preserve embeddings
- Faster turnaround

## Integration with CI/CD

Add to deployment pipeline:

```bash
# In your deployment script
echo "Checking if re-ingestion needed..."

# Check if any chunks lack structure
MISSING_STRUCTURE=$(python -c "
import weaviate
from weaviate.classes.query import Filter

client = weaviate.connect_to_local()
collection = client.collections.get('TheMuses')

count = collection.query.fetch_objects(
    filters=Filter.by_property('headingPath').is_none(True),
    limit=1
).total_count

print(count)
client.close()
")

if [ "$MISSING_STRUCTURE" -gt 0 ]; then
    echo "Found $MISSING_STRUCTURE chunks without structure"
    echo "Running re-ingestion..."
    python scripts/reingest_with_structure.py
else
    echo "All chunks have structure metadata"
fi
```

## Related Scripts

- [scripts/seed_test_data.py](../scripts/seed_test_data.py) - Seed Weaviate with test data
- [scripts/clean_test_data.sh](../scripts/clean_test_data.sh) - Clean test data
- [src/mnemosyne/cli/ingest.py](../src/mnemosyne/cli/ingest.py) - Full ingestion

## Related Documentation

- [Story 020](../user-stories/phase-1-semantic-extraction/story-020-hierarchical-structure-preservation.md) - Hierarchical Structure Preservation
- [WEAVIATE_GOTCHAS.md](WEAVIATE_GOTCHAS.md) - Weaviate troubleshooting
- [TESTING.md](TESTING.md) - Testing guide

---

**Last Updated**: 2025-12-29
**Story**: 020 - Hierarchical Structure Preservation
**Acceptance Criterion**: Re-ingestion script to add structure to existing chunks
